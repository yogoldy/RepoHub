#!/usr/bin/env python3
"""Install this local app and replace Leo's existing repo-only backup schedule."""
import json
import os
from pathlib import Path
import plistlib
import platform
import shutil
import subprocess
import sys
from datetime import datetime

SOURCE = Path(__file__).resolve().parent
HOME_DIR = Path.home()
STATE = HOME_DIR / "Library/Application Support/RepoHub"
CLOUD = HOME_DIR / "Library/Mobile Documents/com~apple~CloudDocs"
AGENTS = HOME_DIR / "Library/LaunchAgents"
APP = HOME_DIR / "Applications/Repo Hub.app"
OLD_LABEL = "com.leogoldberg.desktop-repos-icloud-backup"
LABEL = "com.leogoldberg.repohub.service"
APP_LABEL = "com.leogoldberg.repohub.app"


def run(*args, check=True):
    result = subprocess.run(args, capture_output=True, text=True)
    if check and result.returncode:
        raise RuntimeError(f"{args[0]} failed: {result.stderr.strip()}")
    return result


def inventory(root):
    files = total = links = 0
    for dp, ds, fs in os.walk(root, followlinks=False):
        for name in ds + fs:
            p = Path(dp) / name
            if p.is_symlink():
                links += 1
            elif p.is_file():
                files += 1
                total += p.stat().st_size
    return {"regular_files": files, "bytes": total, "symlinks": links}


def main():
    old_desktop = CLOUD / "Desktop"
    mirror = old_desktop / "repos"
    backup_root = CLOUD / "Repository Backups"
    preserved_mirror = backup_root / "Legacy Current repos"
    if not backup_root.is_dir() or not (HOME_DIR / "Desktop/repos").is_dir():
        raise SystemExit("Expected source repos and Repository Backups folder are required")
    if old_desktop.exists() and os.path.samefile(old_desktop, HOME_DIR / "Desktop"):
        raise SystemExit("Refusing migration: cloud Desktop is the local Desktop")
    if mirror.exists() and preserved_mirror.exists():
        raise SystemExit("Refusing to overwrite the preserved old mirror")
    STATE.mkdir(parents=True, exist_ok=True)
    os.chmod(STATE, 0o700)
    legacy = STATE / "legacy"
    legacy.mkdir(exist_ok=True)
    old_plist = AGENTS / (OLD_LABEL + ".plist")
    original_script = HOME_DIR / "Library/Scripts/desktop-repos-backup/backup_to_icloud.sh"
    migration_file = legacy / "migration.json"
    migration = json.loads(migration_file.read_text()) if migration_file.exists() else {}
    if old_plist.exists():
        if not (legacy / old_plist.name).exists():
            shutil.copy2(old_plist, legacy / old_plist.name)
        run("/bin/launchctl", "bootout", f"gui/{os.getuid()}/{OLD_LABEL}", check=False)
        old_plist.unlink()
    # Stop future manual runs of the old helper from recreating cloud Desktop.
    if original_script.exists():
        if not (legacy / original_script.name).exists():
            shutil.copy2(original_script, legacy / original_script.name)
        script = original_script.read_text()
        script = script.replace('BACKUP_ROOT="$ICLOUD_ROOT/Desktop/repos"',
                                'BACKUP_ROOT="$ICLOUD_ROOT/Repository Backups/Legacy Current repos"')
        original_script.write_text(script)
    if mirror.exists():
        before = inventory(mirror)
        os.rename(mirror, preserved_mirror)
        after = inventory(preserved_mirror)
        if before != after:
            raise RuntimeError("Mirror metadata verification failed; cloud Desktop was not removed")
        migration["preserved_mirror"] = str(preserved_mirror)
        migration["mirror_inventory"] = after
    if old_desktop.exists():
        trash = HOME_DIR / ".Trash"
        trash.mkdir(exist_ok=True)
        removed = trash / ("iCloud Desktop removed " + datetime.now().strftime("%Y-%m-%d %H-%M-%S"))
        os.rename(old_desktop, removed)
        migration["old_cloud_desktop_in_trash"] = str(removed)
    migration_file.write_text(json.dumps(migration, indent=2) + "\n")
    print("MIGRATION", json.dumps(migration), flush=True)

    runtime = STATE / "runtime"
    runtime.mkdir(exist_ok=True)
    for name in ("repohub.py", "backup_changes.py", "backup_lifecycle.py", "backup_policy.py", "status_health.py", "diagnostics.py", "change_evidence.py", "diagnostics_report.py", "diagnostic_export.py", "report_preview.py", "report_delivery.py"):
        shutil.copy2(SOURCE / name, runtime / name)
    shutil.copytree(SOURCE / "web", runtime / "web", dirs_exist_ok=True)
    config = {"repos_root": str(HOME_DIR / "Desktop/repos"),
              "backup_root": str(backup_root / "Snapshots"), "state_dir": str(STATE),
              "port": 8767, "scan_seconds": 30, "backup_seconds": 3600, "retention": "latest",
              "verification_seconds": 900, "cloud_seconds": 5, "require_upload_before_prune": True,
              "cloud_helper": str(runtime / "cloud-status")}
    config_path = STATE / "config.json"
    if config_path.exists():
        config.update(json.loads(config_path.read_text()))
        config["cloud_helper"] = str(runtime / "cloud-status")
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    os.chmod(STATE / "config.json", 0o600)

    app_binary = Path("/private/tmp/repohub-native-build")
    cloud_binary = Path("/private/tmp/repohub-cloud-build")
    run("/usr/bin/xcrun", "swiftc", str(SOURCE / "native/CloudStatus.swift"), "-o", str(cloud_binary),
        "-module-cache-path", "/private/tmp/repohub-swift-cache", "-target", platform.machine() + "-apple-macos13.0")
    shutil.copy2(cloud_binary, runtime / "cloud-status")
    run("/usr/bin/xcrun", "swiftc", str(SOURCE / "native/RepoHub.swift"), str(SOURCE / "native/BackupReadiness.swift"), str(SOURCE / "native/ProblemAlerts.swift"), str(SOURCE / "native/MenuBridge.swift"), str(SOURCE / "native/GitHubConnection.swift"), "-o", str(app_binary),
        "-module-cache-path", "/private/tmp/repohub-swift-cache", "-target", platform.machine() + "-apple-macos13.0",
        "-framework", "AppKit", "-framework", "WebKit", "-framework", "UserNotifications")
    (APP / "Contents/MacOS").mkdir(parents=True, exist_ok=True)
    shutil.copy2(app_binary, APP / "Contents/MacOS/RepoHub")
    info = {"CFBundleIdentifier": "com.leogoldberg.repohub", "CFBundleName": "Repo Hub",
            "CFBundleDisplayName": "Repo Hub", "CFBundleExecutable": "RepoHub", "CFBundlePackageType": "APPL",
            "CFBundleShortVersionString": "0.1.0", "CFBundleVersion": "1", "LSUIElement": True,
            "LSMinimumSystemVersion": "13.0", "CFBundleSupportedPlatforms": ["MacOSX"],
            "NSHighResolutionCapable": True, "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True}}
    with (APP / "Contents/Info.plist").open("wb") as f:
        plistlib.dump(info, f)
    run("/usr/bin/codesign", "--force", "--sign", "-", str(APP))

    logs = STATE / "logs"
    logs.mkdir(exist_ok=True)
    service = {"Label": LABEL, "ProgramArguments": [shutil.which("python3"), str(runtime / "repohub.py"), "--config", str(STATE / "config.json")],
               "RunAtLoad": True, "KeepAlive": True, "ThrottleInterval": 30,
               "StandardOutPath": str(logs / "helper.out.log"), "StandardErrorPath": str(logs / "helper.err.log")}
    frontend = {"Label": APP_LABEL, "ProgramArguments": [str(APP / "Contents/MacOS/RepoHub"), "--background"], "RunAtLoad": True,
                "StandardOutPath": str(logs / "app.out.log"), "StandardErrorPath": str(logs / "app.err.log")}
    for label, contents in [(LABEL, service), (APP_LABEL, frontend)]:
        run("/bin/launchctl", "bootout", f"gui/{os.getuid()}/{label}", check=False)
        plist = AGENTS / (label + ".plist")
        with plist.open("wb") as f:
            plistlib.dump(contents, f)
        run("/bin/launchctl", "bootstrap", f"gui/{os.getuid()}", str(plist))
    print("INSTALLED", str(APP), flush=True)
    print("STATUS", str(STATE / "status.json"), flush=True)


if __name__ == "__main__":
    main()
