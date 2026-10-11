from contextlib import contextmanager
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tools import reliability_account_guard as g


class AccountGuardTests(unittest.TestCase):
    def owned_run(self, parent):
        base = Path(tempfile.mkdtemp(prefix=g.h.PREFIX, dir=parent))
        marker = {'marker': g.h.MARKER, 'id': 'a' * 32, 'run': str(base), 'source_commit': 'b' * 40}
        g.h.write_json(base / 'run.json', marker)
        return base, marker

    def test_peer_sharing_is_read_only_and_redirects_are_rejected(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(g.h, 'RUN_PARENT', Path(temp)):
            base, marker = self.owned_run(temp)
            with patch.object(g.time, 'time', return_value=100):
                receipt = g.prepare_peer(base, 60)
            coord = Path(receipt['coord'])
            self.assertEqual(coord.stat().st_mode & 0o777, 0o755)
            self.assertEqual((coord / 'lock').stat().st_mode & 0o777, 0o444)
            with g.coordinated(coord) as peer:
                self.assertEqual(peer['state'], 'prepared')
                self.assertEqual(peer['run_id'], marker['id'])
            (coord / 'lock').unlink()
            (coord / 'lock').symlink_to(base / 'run.json')
            with self.assertRaisesRegex(ValueError, 'Redirected'):
                g.coord_info(coord)

    def test_peer_is_bounded_single_use_and_wrong_owner_fails(self):
        with tempfile.TemporaryDirectory() as temp, patch.object(g.h, 'RUN_PARENT', Path(temp)):
            base, _ = self.owned_run(temp)
            with self.assertRaises(ValueError): g.prepare_peer(base, 3601)
            receipt = g.prepare_peer(base, 60)
            with self.assertRaises(ValueError): g.prepare_peer(base, 60)
            coord = Path(receipt['coord'])
            info = g.h.read_json(coord / 'peer.json')
            info['test_uid'] += 1
            g.public_json(coord / 'peer.json', info)
            with self.assertRaisesRegex(ValueError, 'owner'): g.coord_info(coord)

    def test_port_reuse_requires_loaded_daily_helper_and_exact_source(self):
        journal = {'daily_labels': ['com.leogoldberg.repohub.service', 'com.leogoldberg.repohub.app'], 'daily_repos_root': '/synthetic/daily'}
        with patch.object(g, 'port_free', return_value=False), patch.object(g.h, 'job_loaded', return_value=False):
            self.assertFalse(g.safe_restore_port(journal))
        with patch.object(g, 'port_free', return_value=False), patch.object(g.h, 'job_loaded', return_value=True):
            with patch.object(g.h, 'get_status', return_value={'repos_root': '/synthetic/test'}):
                self.assertFalse(g.safe_restore_port(journal))
            with patch.object(g.h, 'get_status', return_value={'repos_root': '/synthetic/daily'}):
                self.assertTrue(g.safe_restore_port(journal))
            with patch.object(g.h, 'get_status', side_effect=TimeoutError):
                self.assertFalse(g.safe_restore_port(journal))
        with patch.object(g, 'port_free', return_value=True):
            self.assertTrue(g.safe_restore_port(journal))

    def hold_fixture(self, base):
        labels = ['com.leogoldberg.repohub.app', 'com.leogoldberg.repohub.service']
        protected = base / 'protected'
        protected.write_text('original')
        g.h.write_json(base / 'account-journal.json', {'kind': 'hold', 'coord': '/synthetic/peer', 'peer_run_id': 'c' * 32,
            'daily_labels': labels, 'restore_intents': labels, 'daily_home': '/synthetic',
            'protected_before': g.h.capture([protected])})
        g.public_json(base / 'hold.json', {'state': 'held'})
        return labels, protected

    def test_daily_restore_waits_for_active_test_even_when_port_is_empty(self):
        with tempfile.TemporaryDirectory(dir=str(g.h.RUN_PARENT)) as temp, patch.object(g.h, 'RUN_PARENT', Path(temp)):
            base, _ = self.owned_run(temp)
            self.hold_fixture(base)
            @contextmanager
            def peer(_): yield {'test_uid': os.getuid() + 1, 'run_id': 'c' * 32, 'state': 'active'}
            with patch.object(g, 'coordinated', peer), patch.object(g.h, 'run') as run, patch.object(g, 'port_free', return_value=True):
                result = g.cleanup_hold(base)
                self.assertTrue(result['waiting_for_test_cleanup'])
                run.assert_not_called()
                self.assertEqual(g.h.read_json(base / 'hold.json')['state'], 'held')

    def test_stopped_peer_restores_daily_jobs_and_discloses_changed_baseline(self):
        with tempfile.TemporaryDirectory(dir=str(g.h.RUN_PARENT)) as temp, patch.object(g.h, 'RUN_PARENT', Path(temp)):
            base, _ = self.owned_run(temp)
            labels, protected = self.hold_fixture(base)
            protected.write_text('unexpected change')
            @contextmanager
            def peer(_): yield {'test_uid': os.getuid() + 1, 'run_id': 'c' * 32, 'state': 'stopped'}
            loaded = set()
            def run(argv, check=True):
                self.assertEqual(argv[1], 'bootstrap')
                loaded.add(Path(argv[-1]).stem)
                return type('Result', (), {'returncode': 0})()
            with patch.object(g, 'coordinated', peer), patch.object(g, 'port_free', return_value=True), patch.object(g.h, 'run', side_effect=run), patch.object(g.h, 'job_loaded', side_effect=lambda l: l in loaded):
                result = g.cleanup_hold(base)
                self.assertTrue(result['daily_jobs_restored'])
                self.assertFalse(result['protected_preserved'])
                self.assertEqual(loaded, set(labels))
                self.assertEqual(g.h.read_json(base / 'hold.json')['state'], 'restored')
                self.assertEqual(g.cleanup_hold(base), result)

    def test_test_cleanup_does_not_release_daily_hold_until_jobs_are_gone(self):
        with tempfile.TemporaryDirectory(dir=str(g.h.RUN_PARENT)) as temp, patch.object(g.h, 'RUN_PARENT', Path(temp)):
            base, marker = self.owned_run(temp)
            coord = base / 'coord'; coord.mkdir()
            labels = ['com.leogoldberg.repohub.acceptance.' + marker['id'] + suffix for suffix in ['.service', '.app']]
            g.h.write_json(base / 'account-journal.json', {'kind': 'test', 'coord': str(coord), 'test_labels': labels, 'protected_before': {}})
            value = {'test_uid': os.getuid(), 'run_id': marker['id'], 'state': 'active'}
            @contextmanager
            def peer(_): yield dict(value)
            with patch.object(g, 'coordinated', peer), patch.object(g.h, 'run'), patch.object(g.h, 'unregister_native', return_value=None), patch.object(g.h, 'job_loaded', return_value=True):
                result = g.cleanup_test(base)
                self.assertFalse(result['owned_jobs_stopped'])
                self.assertFalse((coord / 'peer.json').exists())
            with patch.object(g, 'coordinated', peer), patch.object(g.h, 'run'), patch.object(g.h, 'unregister_native', return_value=None), patch.object(g.h, 'job_loaded', return_value=False):
                result = g.cleanup_test(base)
                self.assertTrue(result['owned_jobs_stopped'])
                self.assertEqual(g.h.read_json(coord / 'peer.json')['state'], 'stopped')

    def test_watchdog_retries_until_daily_restoration_finishes(self):
        with tempfile.TemporaryDirectory(dir=str(g.h.RUN_PARENT)) as temp, patch.object(g.h, 'RUN_PARENT', Path(temp)):
            base, _ = self.owned_run(temp)
            g.h.write_json(base / 'account-journal.json', {'kind': 'test', 'controller_pid': 123456789, 'deadline': 99999999999})
            with patch.object(g.os, 'kill', side_effect=ProcessLookupError), patch.object(g.time, 'sleep'), patch.object(g, 'cleanup', side_effect=[{'waiting_for_test_cleanup': True}, {'daily_jobs_restored': True}]) as cleanup:
                g.watchdog(base)
                self.assertEqual(cleanup.call_count, 2)
