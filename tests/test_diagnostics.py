import errno
import json
import os
from pathlib import Path
import stat
import tempfile
import threading
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from diagnostics import DiagnosticLog, read_events
from repohub import Hub


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.logs = self.root / "diagnostics"

    def tearDown(self):
        self.temp.cleanup()

    def test_private_structured_records_and_allowlisted_fields(self):
        log = DiagnosticLog(self.logs)
        self.assertTrue(log.emit("helper_started", build_id="abc"))
        self.assertFalse(log.emit("bad_payload", token="never-save-this"))
        self.assertFalse(log.emit("bad_payload", samples=[{"contents": "private"}]))
        self.assertTrue(log.emit("repo_checked", counts={"repo_files": 2}))
        events = list(read_events(self.logs))
        self.assertEqual(events[-1]["dropped_events"], 2)
        self.assertEqual(events[-1]["schema_version"], 1)
        self.assertTrue(events[-1]["utc"].endswith("+00:00"))
        self.assertNotIn("never-save-this", ''.join(p.read_text() for p in self.logs.iterdir()))
        self.assertEqual(stat.S_IMODE(self.logs.stat().st_mode), 0o700)
        self.assertTrue(all(stat.S_IMODE(p.stat().st_mode) == 0o600 for p in self.logs.iterdir()))

    def test_rotation_and_total_limit_preserve_unmanaged_files(self):
        log = DiagnosticLog(self.logs, file_bytes=420, total_bytes=1100)
        log.emit("started")
        note = self.logs / "keep.txt"
        note.write_text("unmanaged")
        for _ in range(30):
            self.assertTrue(log.emit("heartbeat", repo_count=11))
        managed = list(self.logs.glob("events-*.jsonl"))
        self.assertGreater(len(managed), 1)
        self.assertTrue(all(p.stat().st_size <= 420 for p in managed))
        self.assertLessEqual(sum(p.stat().st_size for p in managed), 1100)
        self.assertEqual(note.read_text(), "unmanaged")

    def test_seven_day_retention_runs_after_restart(self):
        now = 2_000_000_000
        log = DiagnosticLog(self.logs, clock=lambda: now)
        log.emit("old_run")
        old = log.active
        os.utime(old, (now - 8 * 86400, now - 8 * 86400))
        fresh = DiagnosticLog(self.logs, clock=lambda: now)
        self.assertTrue(fresh.emit("new_run"))
        self.assertFalse(old.exists())
        self.assertEqual([e["event"] for e in read_events(self.logs)], ["new_run"])

    def test_full_disk_failure_recovers_and_records_loss(self):
        log = DiagnosticLog(self.logs)
        with patch("diagnostics.os.open", side_effect=OSError(errno.ENOSPC, "disk full at private path")):
            self.assertFalse(log.emit("heartbeat"))
        self.assertEqual(log.status()["state"], "unavailable")
        self.assertTrue(log.emit("heartbeat"))
        self.assertEqual(log.status()["state"], "recording")
        self.assertEqual(list(read_events(self.logs))[0]["dropped_events"], 1)

    def test_partial_write_survives_restart_without_poisoning_next_event(self):
        log = DiagnosticLog(self.logs)
        log.emit("valid_before")
        original = os.write
        calls = 0
        def interrupted(fd, data):
            nonlocal calls
            calls += 1
            if calls == 1:
                return original(fd, data[:30])
            raise OSError(errno.ENOSPC, "full")
        with patch("diagnostics.os.write", side_effect=interrupted):
            self.assertFalse(log.emit("interrupted"))
        restarted = DiagnosticLog(self.logs)
        restarted.emit("valid_after")
        self.assertEqual([e["event"] for e in read_events(self.logs)], ["valid_before", "valid_after"])

    def test_unsafe_directory_and_file_links_are_not_followed(self):
        outside = self.root / "outside"
        outside.mkdir()
        self.logs.symlink_to(outside, target_is_directory=True)
        self.assertFalse(DiagnosticLog(self.logs).emit("started"))
        self.assertFalse(list(outside.iterdir()))
        self.logs.unlink()
        log = DiagnosticLog(self.logs)
        log.emit("started")
        active = log.active
        active.unlink()
        target = outside / "private"
        target.write_text("unchanged")
        active.symlink_to(target)
        self.assertTrue(log.emit("next"))
        self.assertEqual(target.read_text(), "unchanged")
        self.assertEqual([e["event"] for e in read_events(self.logs)], ["next"])

    def test_threaded_events_do_not_interleave(self):
        log = DiagnosticLog(self.logs)
        threads = [threading.Thread(target=lambda: [log.emit("tick", repo_count=1) for _ in range(40)]) for _ in range(5)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(list(read_events(self.logs))), 200)

    def test_reader_skips_special_files_and_malformed_schema(self):
        log = DiagnosticLog(self.logs)
        log.emit("valid")
        with log.active.open('a') as output:
            output.write('{"schema_version":1}\n')
        fifo = self.logs/'events-00000000000000000001-aaaaaaaaaaaa-000001.jsonl'
        os.mkfifo(fifo)
        self.assertEqual([event['event'] for event in read_events(self.logs)], ['valid'])

    def test_heartbeat_is_throttled_and_gaps_are_observations(self):
        wall, mono = [1000], [0]
        log = DiagnosticLog(self.logs, clock=lambda: wall[0], monotonic=lambda: mono[0])
        log.heartbeat(repo_count=2)
        wall[0] += 15; mono[0] += 15
        log.heartbeat(repo_count=2)
        wall[0] += 180; mono[0] += 180
        log.heartbeat(repo_count=2)
        events = list(read_events(self.logs))
        self.assertEqual([e['event'] for e in events], ['heartbeat', 'runtime_gap', 'heartbeat'])
        self.assertEqual(events[1]['result'], 'unobserved_interval')

    def test_logging_failure_does_not_stop_backup_or_enter_backup_data(self):
        repo = self.root / "repos" / "Example"
        repo.mkdir(parents=True)
        (repo / "work.txt").write_text("work")
        cloud = self.root / "cloud"; cloud.mkdir()
        state = self.root / "state"; state.mkdir()
        (state / "diagnostics").write_text("unavailable directory")
        hub = Hub({'repos_root': str(repo.parent), 'backup_root': str(cloud/'Snapshots'), 'state_dir': str(state)})
        hub.backup()
        self.assertFalse(hub.status['backup']['errors'])
        self.assertTrue(hub.index)
        self.assertEqual(hub.public_status()['diagnostics']['state'], 'unavailable')
        self.assertFalse((hub.data_dir/'diagnostics').exists())


if __name__ == "__main__":
    unittest.main()
