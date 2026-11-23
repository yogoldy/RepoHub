"""Explicit user action scopes preserve all unselected archives and receipts."""
import copy
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from tests import test_hub


class SelectedActionTests(unittest.TestCase):
    setUp = test_hub.HubTests.setUp
    tearDown = test_hub.HubTests.tearDown
    # Reuse fixture lifecycle only, rather than inheriting unrelated tests.
    def test_explicit_backup_and_scan_preserve_unselected_repositories(self):
        other = self.repos / 'Other'
        other.mkdir()
        (other / 'work.txt').write_text('original other')
        self.hub.backup()
        rows = {row['name']: row for row in self.hub.status['repos']}
        first, second = rows['Example']['id'], rows['Other']['id']
        old = copy.deepcopy(self.hub.index)
        (self.repo / 'work.txt').write_text('changed first')
        (other / 'work.txt').write_text('changed other')
        original = self.hub.scan
        finished = threading.Event()
        def observed_scan(**kwargs):
            try: return original(**kwargs)
            finally: finished.set()
        revision = self.hub.workspace_status()['revision']
        with patch.object(self.hub, 'scan', side_effect=observed_scan):
            result = self.hub.request_selected_action('scan', {'repo_ids':[first], 'revision':revision})
            self.assertTrue(finished.wait(5))
        self.assertEqual(result['repo_ids'], [first])
        self.assertEqual(self.hub.index, old)
        self.assertIs(next(row for row in self.hub.status['repos'] if row['id']==second), rows['Other'])
        self.assertTrue(next(row for row in self.hub.status['repos'] if row['id']==first)['needs_backup'])
        finished.clear()
        old_global_clock = self.hub.last_periodic_at
        old_scheduler_clock = self.hub.scheduler.last_periodic
        original_backup = self.hub.backup
        def observed_backup(**kwargs):
            try: return original_backup(**kwargs)
            finally: finished.set()
        with patch.object(self.hub, 'backup', side_effect=observed_backup):
            self.hub.request_selected_action('backup', {'repo_ids':[first], 'revision':revision})
            self.assertTrue(finished.wait(5))
        self.assertNotEqual(self.hub.index[first]['sha256'], old[first]['sha256'])
        self.assertEqual(self.hub.index[second], old[second])
        self.assertEqual(self.hub.last_periodic_at, old_global_clock)
        self.assertEqual(self.hub.scheduler.last_periodic, old_scheduler_clock)
        self.assertIn(first, self.hub.repo_periodic_at)
        self.assertNotIn(second, self.hub.repo_periodic_at)

    def test_invalid_missing_stale_and_busy_selection_never_starts_worker(self):
        revision = self.hub.workspace_status()['revision']
        key = next(iter(self.hub.repositories()))
        with patch('repohub.threading.Thread') as worker:
            for payload in ({}, {'repo_ids':[], 'revision':revision},
                            {'repo_ids':[key,key], 'revision':revision},
                            {'repo_ids':['unknown'], 'revision':revision},
                            {'repo_ids':[key], 'revision':'stale'}):
                with self.assertRaises((ValueError, FileExistsError)):
                    self.hub.request_selected_action('backup', payload)
            self.hub.scan_lock.acquire()
            try:
                with self.assertRaises(FileExistsError):
                    self.hub.request_selected_action('scan', {'repo_ids':[key], 'revision':revision})
            finally: self.hub.scan_lock.release()
            self.repo.rename(self.base / 'moved')
            with self.assertRaises(OSError):
                self.hub.request_selected_action('backup', {'repo_ids':[key], 'revision':revision})
            worker.assert_not_called()
        self.assertFalse(self.hub.backup_lock.locked())
        self.assertFalse(self.hub.scan_lock.locked())

    def test_multi_scan_and_worker_start_failure_preserve_locks(self):
        other = self.repos / 'Other'
        other.mkdir()
        (other / 'work.txt').write_text('other')
        current = self.hub.workspace_status()
        keys = list(self.hub.repositories())
        with patch('repohub.threading.Thread') as thread:
            thread.return_value.start.side_effect = RuntimeError('synthetic start failure')
            for action in ('scan', 'backup'):
                with self.assertRaises(RuntimeError):
                    self.hub.request_selected_action(action, {'repo_ids':keys, 'revision':current['revision']})
                self.assertFalse(self.hub.backup_lock.locked())
                self.assertFalse(self.hub.scan_lock.locked())
        self.hub.scan()
        done = threading.Event()
        scan = self.hub.scan
        def observed(**options):
            try: return scan(**options)
            finally: done.set()
        with patch.object(self.hub, 'scan', side_effect=observed):
            self.hub.request_selected_action('scan', {'repo_ids':keys, 'revision':current['revision']})
            self.assertTrue(done.wait(5))
        self.assertEqual({row['id'] for row in self.hub.status['repos']}, set(keys))

    def test_http_guards_and_explicit_fields_precede_worker_dispatch(self):
        import json
        import urllib.request
        import urllib.error
        from repohub import Handler, ThreadingHTTPServer
        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        server.hub = self.hub
        threading.Thread(target=server.serve_forever, daemon=True).start()
        origin = 'http://127.0.0.1:' + str(server.server_port)
        headers = {'Origin':origin, 'X-RepoHub-Token':self.hub.csrf, 'Content-Type':'application/json'}
        keys = list(self.hub.repositories())
        body = {'repo_ids':keys, 'revision':self.hub.workspace_status()['revision']}
        try:
            for action in ('backup', 'scan'):
                for changed in ({'Origin':'https://untrusted.example'}, {'Host':'untrusted.example'},
                                {'X-RepoHub-Token':'wrong'}):
                    request = urllib.request.Request(origin+'/api/actions/'+action,
                        json.dumps(body).encode(), {**headers, **changed})
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(request)
                    self.assertEqual(error.exception.code, 403)
                    error.exception.close()
                with patch.object(self.hub, 'request_selected_action', wraps=self.hub.request_selected_action) as dispatch:
                    request = urllib.request.Request(origin+'/api/actions/'+action, b'{}', headers)
                    with self.assertRaises(urllib.error.HTTPError) as error:
                        urllib.request.urlopen(request)
                    self.assertEqual(error.exception.code, 400)
                    error.exception.close()
        finally:
            server.shutdown()
            server.server_close()
