#!/usr/bin/env python3
"""Private, Air-first native acceptance staging. Never invoke the personal installer.

The detached watchdog and controller share an idempotent, locked cleanup journal.
This tool prepares evidence; it cannot declare a visible UI or permission test passed.
"""
import argparse
import ast
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import plistlib
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.request
import uuid

MARKER = "repohub-reliability-acceptance-v1"
PREFIX = "repohub-acceptance-"
RUN_PARENT = Path("/private/tmp") if platform.system() == "Darwin" else Path(tempfile.gettempdir()).resolve()
DAILY_LABELS = {
    "com.leogoldberg.repohub.service", "com.leogoldberg.repohub.app",
    "com.leogoldberg.repohub.airtest.service", "com.leogoldberg.repohub.airtest.app",
}


def run(argv, check=True):
    return subprocess.run(argv, check=check, capture_output=True, text=True, timeout=30)


def write_json(path, value):
    temporary = path.with_name(path.name + ".new")
    with temporary.open("w") as target:
        json.dump(value, target, indent=2)
        target.flush()
        os.fsync(target.fileno())
    os.replace(temporary, path)


def read_json(path):
    return json.loads(path.read_text())


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def tree_hashes(root):
    result = {}
    if not root.exists():
        return result
    for path in sorted(root.rglob("*")):
        name = str(path.relative_to(root))
        if path.is_symlink():
            result[name] = {"link": os.readlink(path)}
        elif path.is_file():
            result[name] = {"sha256": digest(path), "mode": path.stat().st_mode & 0o777}
        elif path.is_dir():
            result[name] = {"directory": True}
    return result


def validate_payload(payload):
    payload = payload.resolve(strict=True)
    manifest = read_json(payload / "payload.json")
    if manifest.get("marker") != MARKER:
        raise ValueError("Not an acceptance payload")
    expected = manifest["files"]
    actual = tree_hashes(payload)
    actual.pop("payload.json", None)
    if actual != expected:
        raise ValueError("Transferred payload differs from its manifest")
    return manifest


def guarded_run(path):
    path = Path(path)
    # Resolve only after checking for symlink ancestors; fault operations must stay owned.
    if not path.is_absolute() or path.parent != RUN_PARENT or not path.name.startswith(PREFIX):
        raise ValueError("Run must be a direct private temporary acceptance directory")
    if path.is_symlink() or path.stat().st_uid != os.getuid():
        raise ValueError("Foreign or redirected run")
    marker = read_json(path / "run.json")
    if marker.get("marker") != MARKER or marker.get("run") != str(path) or not re.fullmatch(r"[0-9a-f]{32}", marker.get("id", "")):
        raise ValueError("Invalid owned run marker")
    return path, marker


def validate_labels(labels):
    if len(labels) != 2 or len(set(labels)) != 2 or not set(labels) <= DAILY_LABELS:
        raise ValueError("Exactly the known daily helper and app labels are required")
    families = {label.rsplit(".", 1)[0] for label in labels}
    if len(families) != 1 or {label.rsplit(".", 1)[1] for label in labels} != {"service", "app"}:
        raise ValueError("Mixed daily installation labels")


def package(source, gate_path, output):
    source = source.resolve(strict=True)
    gate = read_json(gate_path)
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
    if subprocess.check_output(["git", "status", "--porcelain"], cwd=source) or gate.get("source_commit") != head:
        raise ValueError("Payload requires the exact clean committed gate source")
    from tools.release_gate import source_fingerprint
    if (gate.get("result") != "passed" or gate.get("profile") != "macos" or gate.get("dirty_source")
            or not gate.get("source_unchanged") or gate.get("source_digest") != source_fingerprint(source)):
        raise ValueError("A matching clean macOS Golden Gate is required")
    if output.exists() or output.is_symlink():
        raise ValueError("Payload output must be new")
    output.mkdir(mode=0o700)
    runtime = output / "runtime"
    runtime.mkdir()
    groups = [ast.literal_eval(node.iter) for node in ast.walk(ast.parse((source / "install.py").read_text()))
              if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == "name"
              and isinstance(node.iter, (ast.Tuple, ast.List))]
    modules = next(group for group in groups if "repohub.py" in group)
    for name in modules:
        shutil.copy2(source / name, runtime / name)
    shutil.copytree(source / "web", runtime / "web")
    build = Path(next(item["log"] for item in gate["commands"] if item["check"] == "native-app-build")).parent
    app = output / "RepoHub Reliability.app"
    binary = app / "Contents/MacOS/RepoHub"
    binary.parent.mkdir(parents=True)
    shutil.copy2(build / "RepoHub", binary)
    shutil.copy2(build / "cloud-status", runtime / "cloud-status")
    identity = "com.leogoldberg.repohub.acceptance." + uuid.uuid4().hex
    info = {"CFBundleIdentifier": identity, "CFBundleName": "RepoHub Reliability",
            "CFBundleDisplayName": "RepoHub Reliability", "CFBundleExecutable": "RepoHub",
            "CFBundlePackageType": "APPL", "CFBundleShortVersionString": "0.1.0",
            "CFBundleVersion": "1", "LSUIElement": True, "LSMinimumSystemVersion": "13.0",
            "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
            "NSDesktopFolderUsageDescription": "Access only the synthetic folders selected for reliability testing."}
    (app / "Contents/Info.plist").write_bytes(plistlib.dumps(info))
    run(["/usr/bin/codesign", "--force", "--sign", "-", str(app)])
    run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)])
    signing = run(["/usr/bin/codesign", "-dv", "--verbose=4", str(app)]).stderr
    for name in ["reliability_acceptance.py", "reliability_account_guard.py"]:
        shutil.copy2(source / "tools" / name, output / name)
    shutil.copy2(source / "docs/quality/reliability-matrix.json", output / "matrix.json")
    shutil.copy2(gate_path, output / "golden-gate.json")
    for index, name in enumerate(["home/Project", "manual/Project", "home/Accessible"]):
        repo = output / "fixtures" / name
        repo.mkdir(parents=True)
        (repo / "README.txt").write_text("Synthetic repository " + str(index) + "\n")
        (repo / ".gitignore").write_text("ignored.txt\n")
        (repo / "ignored.txt").write_text("Ignored but backed up\n")
        (repo / "empty").mkdir()
        env = {**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
               "GIT_AUTHOR_DATE": "2000-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2000-01-01T00:00:00Z"}
        for argv in [["git", "init", "-q", str(repo)], ["git", "-C", str(repo), "add", "."],
                     ["git", "-C", str(repo), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid", "commit", "-qm", "Known fixture"]]:
            subprocess.run(argv, env=env, check=True, capture_output=True)
        (repo / "uncommitted.txt").write_text("Uncommitted but backed up\n")
    manifest = {"marker": MARKER, "source_commit": head, "gate_digest": digest(gate_path),
                "bundle_id": identity, "signing": signing,
                "builder": {"macos": run(["sw_vers", "-productVersion"]).stdout.strip(), "architecture": platform.machine(), "python": platform.python_version()},
                "files": tree_hashes(output)}
    write_json(output / "payload.json", manifest)
    return {"payload": str(output), "source_commit": head, "manifest_sha256": digest(output / "payload.json")}


def prepare(payload):
    manifest = validate_payload(payload)
    base = Path(tempfile.mkdtemp(prefix=PREFIX, dir=str(RUN_PARENT)))
    for name in ["runtime", "fixtures", "RepoHub Reliability.app"]:
        shutil.copytree(payload / name, base / name, symlinks=True)
    shutil.copy2(payload / "reliability_acceptance.py", base / "harness.py")
    shutil.copy2(payload / "matrix.json", base / "matrix.json")
    home = base / "home"
    state = home / "Library/Application Support/RepoHub"
    (state / "data").mkdir(parents=True)
    (base / "destination").mkdir()
    (base / "choices").mkdir()
    for name, target in [("Project A", "home/Project"), ("Project B", "manual/Project"), ("Duplicate A", "home/Project")]:
        (base / "choices" / name).symlink_to(base / "fixtures" / target, target_is_directory=True)
    # Load the actual defaults, then explicitly make both power policies manual.
    sys.path.insert(0, str(base / "runtime"))
    from backup_policy import default_settings
    settings = default_settings()
    for policy in settings.values():
        policy.update(frequency_minutes=0, after_edits=False)
    write_json(state / "data/settings.json", settings)
    config = {"repos_root": str(base / "fixtures/home"), "backup_root": str(base / "destination/Snapshots"),
              "state_dir": str(state), "port": 8767, "scan_seconds": 5, "cloud_seconds": 5,
              "verification_seconds": 10, "retention": "all", "cloud_helper": "/usr/bin/false"}
    write_json(base / "config.json", config)
    marker = {"marker": MARKER, "run": str(base), "id": uuid.uuid4().hex,
              "source_commit": manifest["source_commit"], "bundle_id": manifest["bundle_id"],
              "payload_manifest_sha256": digest(payload / "payload.json"), "fixture_hashes": tree_hashes(base / "fixtures"),
              "environment": {"macos": run(["sw_vers", "-productVersion"]).stdout.strip(), "architecture": platform.machine(), "python": platform.python_version()},
              "provider": "disabled; upload status must remain unknown"}
    write_json(base / "run.json", marker)
    return marker


def get_status():
    with urllib.request.urlopen("http://127.0.0.1:8767/api/status", timeout=3) as reply:
        return json.load(reply)


def protected_paths(home, labels):
    state = home / "Library/Application Support/RepoHub"
    return [state / "config.json", state / "data", state / "backups.json", state / "schedule-clock.json",
            state / "notifications.json", state / "runtime", home / "Applications/Repo Hub.app"] + [
                home / "Library/LaunchAgents" / (label + ".plist") for label in labels]


def capture(paths):
    return {str(path): (tree_hashes(path) if path.is_dir() else {"sha256": digest(path)} if path.is_file() else None) for path in paths}


def domain():
    return "gui/" + str(os.getuid())


def job_loaded(label):
    return run(["/bin/launchctl", "print", domain() + "/" + label], check=False).returncode == 0


LSREGISTER = "/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"


def registered_app_path(home, marker):
    return home / "Applications" / ("RepoHub Reliability " + marker["id"] + ".app")


def register_native(base, marker, home):
    app = registered_app_path(home, marker)
    if app.parent.is_symlink() or app.exists() or app.is_symlink():
        raise ValueError("Refusing existing or redirected staging application")
    app.parent.mkdir(exist_ok=True)
    # Durable ownership before copying. Partial copies are preserved for inspection.
    write_json(base / "native-registration.json", {"path": str(app),
               "files": tree_hashes(base / "RepoHub Reliability.app")})
    shutil.copytree(base / "RepoHub Reliability.app", app, symlinks=True)
    run([LSREGISTER, "-f", str(app)])
    return app


def unregister_native(base, marker, home):
    receipt = base / "native-registration.json"
    if not receipt.exists():
        return None
    owned = read_json(receipt)
    app = registered_app_path(home, marker)
    if owned.get("path") != str(app) or app.parent.is_symlink() or app.is_symlink():
        return "unowned_registration"
    if not app.exists():
        return None
    if app.stat().st_uid != os.getuid() or tree_hashes(app) != owned.get("files"):
        return "registered_assets_changed"
    run([LSREGISTER, "-u", str(app)])
    shutil.rmtree(app)
    return None


def cleanup(base):
    base, marker = guarded_run(base)
    with (base / "cleanup.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if (base / "cleanup.json").exists():
            previous = read_json(base / "cleanup.json")
            if previous.get("daily_jobs_restored"):
                return previous
        if not (base / "journal.json").exists():
            return {"not_started": True}
        journal = read_json(base / "journal.json")
        validate_labels(journal["daily_labels"])
        expected_prefix = "com.leogoldberg.repohub.acceptance." + marker["id"]
        if journal["test_labels"] != [expected_prefix + ".service", expected_prefix + ".app"]:
            raise ValueError("Unowned staging labels")
        for label in reversed(journal["test_labels"]):
            # Resume a suspended helper before bootout; only this run's exact label.
            run(["/bin/launchctl", "kill", "SIGCONT", domain() + "/" + label], check=False)
            run(["/bin/launchctl", "bootout", domain() + "/" + label], check=False)
        try:
            registration_error = unregister_native(base, marker, Path(journal["daily_home"]))
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            registration_error = type(error).__name__
        paths = [Path(p) for p in journal["protected_before"]]
        try:
            observed = capture(paths)
            preserved = observed == journal["protected_before"]
            capture_error = None
        except OSError as error:
            observed = {}
            preserved = False
            capture_error = type(error).__name__
        errors = []
        for label in reversed(journal["restore_intents"]):
            if not job_loaded(label):
                plist = Path(journal["daily_home"]) / "Library/LaunchAgents" / (label + ".plist")
                result = run(["/bin/launchctl", "bootstrap", domain(), str(plist)], check=False)
                if result.returncode:
                    errors.append(label)
        restored = all(job_loaded(label) for label in journal["restore_intents"])
        result = {"protected_preserved": preserved, "protected_after": observed,
                  "daily_jobs_restored": restored, "restore_errors": errors, "native_registration_error": registration_error, "capture_error": capture_error, "finished_at": time.time()}
        write_json(base / "cleanup.json", result)
        return result


def watchdog(base):
    base, _ = guarded_run(base)
    write_json(base / "watchdog-ready.json", {"pid": os.getpid()})
    while True:
        journal = read_json(base / "journal.json")
        try:
            os.kill(journal["controller_pid"], 0)
            alive = True
        except ProcessLookupError:
            alive = False
        if not alive or time.time() > journal["deadline"] or (base / "stop").exists():
            cleanup(base)
            return
        time.sleep(0.5)


def stage(base, python, labels, control_evidence, seconds=1800):
    base, marker = guarded_run(base)
    validate_labels(labels)
    labels = sorted(labels, key=lambda label: label.endswith("service"))
    if not 30 <= seconds <= 3600:
        raise ValueError("Staging watchdog deadline out of bounds")
    if (base / "journal.json").exists():
        raise ValueError("Run already started; create fresh staging")
    if not control_evidence.is_file() or not control_evidence.read_text().strip():
        raise ValueError("Record actual native-control evidence before pausing services")
    home = Path.home()
    for label in labels:
        plist = home / "Library/LaunchAgents" / (label + ".plist")
        if not plist.is_file() or plistlib.loads(plist.read_bytes()).get("Label") != label or not job_loaded(label):
            raise ValueError("Expected daily registration is not loaded")
    status = get_status()
    if status.get("backup", {}).get("running") is not False:
        raise ValueError("Cannot pause an active or unknown daily backup")
    # Verify Python and assets without executing the helper or touching daily settings.
    run([str(python), "-c", "import ast,pathlib,sys; [ast.parse(p.read_text()) for p in pathlib.Path(sys.argv[1]).glob('*.py')]", str(base / "runtime")])
    app = base / "RepoHub Reliability.app"
    run(["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)])
    protected = protected_paths(home, labels)
    before = capture(protected)
    rollback = base / "rollback"
    rollback.mkdir()
    for number, path in enumerate(protected):
        if path.is_dir():
            shutil.copytree(path, rollback / str(number), symlinks=True)
        elif path.is_file():
            shutil.copy2(path, rollback / str(number))
    shutil.copy2(control_evidence, base / "native-control.txt")
    prefix = "com.leogoldberg.repohub.acceptance." + marker["id"]
    test_labels = [prefix + ".service", prefix + ".app"]
    env = {"HOME": str(base / "home"), "CFFIXED_USER_HOME": str(base / "home"), "PYTHONDONTWRITEBYTECODE": "1"}
    for label, argv in zip(test_labels, [[str(python), str(base / "runtime/repohub.py"), "--config", str(base / "config.json")], [str(registered_app_path(home, marker) / "Contents/MacOS/RepoHub")]]):
        value = {"Label": label, "ProgramArguments": argv, "RunAtLoad": True, "EnvironmentVariables": env,
                 "StandardOutPath": str(base / (label.rsplit(".", 1)[-1] + ".log")),
                 "StandardErrorPath": str(base / (label.rsplit(".", 1)[-1] + ".log"))}
        (base / (label.rsplit(".", 1)[-1] + ".plist")).write_bytes(plistlib.dumps(value))
    journal = {"controller_pid": os.getpid(), "deadline": time.time() + seconds,
               "daily_labels": labels, "daily_home": str(home), "restore_intents": [], "test_labels": test_labels,
               "protected_before": before, "python": str(python)}
    write_json(base / "journal.json", journal)
    log = (base / "watchdog.log").open("a")
    subprocess.Popen([str(python), str(base / "harness.py"), "watchdog", "--run", str(base)],
                     stdin=subprocess.DEVNULL, stdout=log, stderr=log, start_new_session=True)
    try:
        for _ in range(100):
            if (base / "watchdog-ready.json").exists():
                break
            time.sleep(0.05)
        else:
            raise RuntimeError("Independent watchdog did not start; no pause performed")
        register_native(base, marker, home)
        for label in labels:
            journal["restore_intents"].append(label)
            write_json(base / "journal.json", journal)  # durable restore intent BEFORE bootout
            run(["/bin/launchctl", "bootout", domain() + "/" + label])
        if capture(protected) != before:
            raise RuntimeError("Protected data changed while stopping; refusing staging")
        for label in test_labels:
            run(["/bin/launchctl", "bootstrap", domain(), str(base / (label.rsplit(".", 1)[-1] + ".plist"))])
        for _ in range(100):
            try:
                observed = get_status()
                if observed.get("repos_root") == str(base / "fixtures/home"):
                    break
            except OSError:
                pass
            time.sleep(0.1)
        else:
            raise RuntimeError("Isolated helper did not become available")
        write_json(base / "ready.json", {"source_commit": marker["source_commit"], "status": observed, "started_at": time.time()})
        print(json.dumps({"ready": str(base), "source_commit": marker["source_commit"]}), flush=True)
        while not (base / "stop").exists() and not (base / "cleanup.json").exists() and time.time() < journal["deadline"]:
            time.sleep(0.25)
    finally:
        print(json.dumps(cleanup(base)), flush=True)
        log.close()


def control(base, action):
    base, marker = guarded_run(base)
    journal = read_json(base / "journal.json")
    prefix = "com.leogoldberg.repohub.acceptance." + marker["id"]
    if journal["test_labels"] != [prefix + ".service", prefix + ".app"] or (base / "cleanup.json").exists():
        raise ValueError("No active owned staging run")
    if action == "stop":
        (base / "stop").touch()
    elif action in ["pause-helper", "resume-helper"]:
        run(["/bin/launchctl", "kill", "SIGSTOP" if action == "pause-helper" else "SIGCONT", domain() + "/" + prefix + ".service"])
    else:
        suffix = "service" if action == "restart-helper" else "app"
        run(["/bin/launchctl", "kickstart", "-k", domain() + "/" + prefix + "." + suffix])


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    p = commands.add_parser("package")
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--gate", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p = commands.add_parser("prepare")
    p.add_argument("--payload", type=Path, required=True)
    for name in ["stage", "watchdog", "cleanup", "control"]:
        p = commands.add_parser(name)
        p.add_argument("--run", type=Path, required=True)
        if name == "stage":
            p.add_argument("--python", type=Path, required=True)
            p.add_argument("--daily-label", action="append", required=True)
            p.add_argument("--control-evidence", type=Path, required=True)
            p.add_argument("--seconds", type=int, default=1800)
        if name == "control":
            p.add_argument("action", choices=["stop", "pause-helper", "resume-helper", "restart-helper", "restart-native"])
    args = parser.parse_args()
    if args.command == "package":
        print(json.dumps(package(args.source, args.gate, args.output)))
    elif args.command == "prepare":
        print(json.dumps(prepare(args.payload)))
    elif args.command == "stage":
        stage(args.run, args.python, args.daily_label, args.control_evidence, args.seconds)
    elif args.command == "watchdog":
        watchdog(args.run)
    elif args.command == "cleanup":
        print(json.dumps(cleanup(args.run)))
    else:
        control(args.run, args.action)


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    main()
