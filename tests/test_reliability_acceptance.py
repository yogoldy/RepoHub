import ast
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import reliability_acceptance as harness


class AcceptanceHarnessTests(unittest.TestCase):
    def test_only_known_matching_daily_labels_can_be_paused(self):
        harness.validate_labels(["com.leogoldberg.repohub.app", "com.leogoldberg.repohub.service"])
        for labels in [["foreign.app", "foreign.service"], ["com.leogoldberg.repohub.app"] * 2,
                       ["com.leogoldberg.repohub.app", "com.leogoldberg.repohub.airtest.service"]]:
            with self.assertRaises(ValueError):
                harness.validate_labels(labels)

    def test_arbitrary_directory_and_redirected_run_are_rejected(self):
        with tempfile.TemporaryDirectory(dir=str(harness.RUN_PARENT)) as temp:
            root = Path(temp)
            with self.assertRaises(ValueError):
                harness.guarded_run(root)
            link = harness.RUN_PARENT / ("repohub-acceptance-link-" + root.name)
            try:
                link.symlink_to(root, target_is_directory=True)
                with self.assertRaises(ValueError):
                    harness.guarded_run(link)
            finally:
                link.unlink()

    def test_payload_transfer_change_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "asset").write_text("known")
            manifest = {"marker": harness.MARKER, "files": harness.tree_hashes(root)}
            harness.write_json(root / "payload.json", manifest)
            harness.validate_payload(root)
            (root / "asset").write_text("changed")
            with self.assertRaisesRegex(ValueError, "differs"):
                harness.validate_payload(root)

    def test_baseline_contains_actual_registry_and_schedule_files(self):
        paths = harness.protected_paths(Path("/synthetic"), ["com.leogoldberg.repohub.service", "com.leogoldberg.repohub.app"])
        data = next(p for p in paths if p.name == "data")
        with tempfile.TemporaryDirectory() as temp:
            data = Path(temp) / data.name
            data.mkdir()
            (data / "workspace-registry.json").write_text("known registry")
            before = harness.capture([data])
            (data / "workspace-registry.json").write_text("unexpected mutation")
            self.assertNotEqual(before, harness.capture([data]))
        self.assertTrue(any(p.name == "schedule-clock.json" for p in paths))

    def test_cleanup_restores_intents_even_when_protected_state_changed(self):
        with tempfile.TemporaryDirectory(prefix=harness.PREFIX, dir=str(harness.RUN_PARENT)) as temp:
            base = Path(temp)
            marker = {"marker": harness.MARKER, "run": str(base), "id": "a" * 32}
            harness.write_json(base / "run.json", marker)
            protected = base / "protected.json"
            protected.write_text("original")
            labels = ["com.leogoldberg.repohub.app", "com.leogoldberg.repohub.service"]
            prefix = "com.leogoldberg.repohub.acceptance." + marker["id"]
            journal = {"daily_labels": labels, "restore_intents": labels, "daily_home": "/synthetic",
                       "test_labels": [prefix + ".service", prefix + ".app"],
                       "protected_before": harness.capture([protected])}
            harness.write_json(base / "journal.json", journal)
            protected.write_text("unexpected")
            loaded = set()
            calls = []
            def fake_run(argv, check=True):
                calls.append(argv)
                if argv[1] == "bootstrap":
                    loaded.add(Path(argv[-1]).stem)
                return type("Result", (), {"returncode": 0})()
            with patch.object(harness, "run", side_effect=fake_run), patch.object(harness, "job_loaded", side_effect=lambda label: label in loaded):
                result = harness.cleanup(base)
                self.assertFalse(result["protected_preserved"])
                self.assertTrue(result["daily_jobs_restored"])
                count = len(calls)
                self.assertEqual(result, harness.cleanup(base))
                self.assertEqual(count, len(calls))
            # Controller crash restore intents are not contingent on successful test startup.
            self.assertEqual(loaded, set(labels))
            (base / "cleanup.json").unlink()
            loaded.clear()
            with patch.object(harness, "run", side_effect=fake_run), patch.object(harness, "job_loaded", side_effect=lambda label: label in loaded), patch.object(harness, "capture", side_effect=PermissionError):
                unreadable = harness.cleanup(base)
                self.assertEqual(unreadable["capture_error"], "PermissionError")
                self.assertFalse(unreadable["protected_preserved"])
                self.assertTrue(unreadable["daily_jobs_restored"])


    def test_watchdog_controller_loss_invokes_cleanup_without_parent(self):
        with tempfile.TemporaryDirectory(prefix=harness.PREFIX, dir=str(harness.RUN_PARENT)) as temp:
            base = Path(temp)
            harness.write_json(base / "run.json", {"marker": harness.MARKER, "run": str(base), "id": "a" * 32})
            harness.write_json(base / "journal.json", {"controller_pid": 123456789, "deadline": 99999999999})
            with patch.object(harness.os, "kill", side_effect=ProcessLookupError), patch.object(harness, "cleanup") as cleanup:
                harness.watchdog(base)
                cleanup.assert_called_once_with(base)
            self.assertTrue((base / "watchdog-ready.json").exists())

    def test_matrix_requires_native_permission_evidence_and_no_automatic_pass(self):
        root = Path(__file__).resolve().parents[1]
        matrix = json.loads((root / "docs/quality/reliability-matrix.json").read_text())
        self.assertEqual([c["id"] for c in matrix["cases"]], [f"{i:02d}" for i in range(1, 10)])
        self.assertTrue(all(c["initial_status"] == "not_run" for c in matrix["cases"]))
        self.assertTrue(all("native_ui" in c["required_evidence"] for c in matrix["cases"]))
        self.assertIn("Actual macOS", matrix["cases"][6]["title"])

    def test_package_reads_only_literal_runtime_declaration(self):
        source = Path(__file__).resolve().parents[1]
        groups = [ast.literal_eval(node.iter) for node in ast.walk(ast.parse((source / "install.py").read_text()))
                  if isinstance(node, ast.For) and isinstance(node.target, ast.Name) and node.target.id == "name"
                  and isinstance(node.iter, (ast.Tuple, ast.List))]
        self.assertEqual(sum("repohub.py" in group for group in groups), 1)

    def test_registered_native_cleanup_never_removes_foreign_or_changed_assets(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp) / "run"
            base.mkdir()
            home = Path(temp) / "home"
            home.mkdir()
            original = base / "RepoHub Reliability.app"
            original.mkdir()
            (original / "asset").write_text("known candidate")
            marker = {"id": "b" * 32}
            with patch.object(harness, "run"):
                app = harness.register_native(base, marker, home)
                (app / "asset").write_text("unexpected mutation")
                self.assertEqual(harness.unregister_native(base, marker, home), "registered_assets_changed")
                self.assertTrue(app.exists())
                receipt = harness.read_json(base / "native-registration.json")
                receipt["path"] = str(home / "Applications/Repo Hub.app")
                harness.write_json(base / "native-registration.json", receipt)
                self.assertEqual(harness.unregister_native(base, marker, home), "unowned_registration")
                self.assertTrue(app.exists())
                receipt["path"] = str(app)
                harness.write_json(base / "native-registration.json", receipt)
                (app / "asset").write_text("known candidate")
                self.assertIsNone(harness.unregister_native(base, marker, home))
                self.assertFalse(app.exists())
                self.assertIsNone(harness.unregister_native(base, marker, home))

    def test_native_registration_refuses_existing_and_redirected_application(self):
        with tempfile.TemporaryDirectory() as temp:
            home = Path(temp)
            marker = {"id": "c" * 32}
            app = harness.registered_app_path(home, marker)
            app.mkdir(parents=True)
            (app / "personal").write_text("preserve")
            with self.assertRaises(ValueError):
                harness.register_native(home, marker, home)
            self.assertEqual((app / "personal").read_text(), "preserve")
            redirected_home = home / "redirected-home"
            redirected_home.mkdir()
            (redirected_home / "Applications").symlink_to(app.parent, target_is_directory=True)
            with self.assertRaises(ValueError):
                harness.register_native(home, marker, redirected_home)
