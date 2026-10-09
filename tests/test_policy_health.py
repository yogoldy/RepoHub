import copy
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from unittest.mock import patch

from backup_policy import BackupScheduler, default_settings, validate_settings, power_source
from status_health import annotate_health, ProblemTracker
from repohub import Hub, Handler, ThreadingHTTPServer, utc_now, workspace_id


def stamp(seconds):
    return datetime.fromtimestamp(seconds, timezone.utc).isoformat()


def status_at(now):
    return {'scanned_at': stamp(now), 'backup': {}, 'repos': [{
        'id': 'Example', 'name': 'Example', 'needs_backup': False,
        'verification': {'state': 'matched', 'checked_at': stamp(now)},
        'cloud': {'state': 'uploaded', 'archive': '/current', 'checked_at': stamp(now)}}]}


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.settings = default_settings()
        self.scheduler = BackupScheduler(0)
        self.rows = [{'id': 'one', 'signature': 'a', 'needs_backup': True},
                     {'id': 'two', 'signature': 'b', 'needs_backup': True}]
        self.scheduler.observe(self.rows, 0)

    def test_edit_timer_is_per_repo_and_restarts_for_more_edits(self):
        self.rows[0]['signature'] = 'new'
        self.scheduler.observe(self.rows, 250)
        plan = self.scheduler.plan(self.settings, 'battery', self.rows, 301)
        self.assertEqual(plan['keys'], ['two'])
        self.assertIsNone(self.scheduler.plan(self.settings, 'battery', self.rows, 299))
        self.assertEqual(self.scheduler.plan(self.settings, 'battery', self.rows, 551)['keys'], ['one', 'two'])

    def test_after_edits_default_is_battery_only_and_unknown_pauses(self):
        self.assertIsNone(self.scheduler.plan(self.settings, 'adapter', self.rows, 301))
        self.assertIsNone(self.scheduler.plan(self.settings, 'unknown', self.rows, 4000))
        self.assertEqual(self.scheduler.plan(self.settings, 'battery', self.rows, 301)['reason'], 'after_edits')

    def test_timed_off_and_edit_toggle_are_independent(self):
        self.settings['battery']['frequency_minutes'] = 0
        self.assertEqual(self.scheduler.plan(self.settings, 'battery', self.rows, 4000)['reason'], 'after_edits')
        self.settings['battery']['after_edits'] = False
        self.assertIsNone(self.scheduler.plan(self.settings, 'battery', self.rows, 4000))

    def test_each_power_source_uses_its_own_frequency(self):
        self.settings['adapter']['frequency_minutes'] = 15
        self.assertIsNone(self.scheduler.plan(self.settings, 'adapter', self.rows, 899))
        self.assertEqual(self.scheduler.plan(self.settings, 'adapter', self.rows, 900)['reason'], 'scheduled')
        plan = self.scheduler.plan(self.settings, 'adapter', self.rows, 900)
        self.scheduler.completed(plan, self.rows, 910)
        self.assertIsNone(self.scheduler.plan(self.settings, 'adapter', self.rows, 1000))

    def test_retry_is_throttled_and_manual_backup_resets_periodic_clock(self):
        plan = self.scheduler.plan(self.settings, 'battery', self.rows, 301)
        self.scheduler.completed(plan, self.rows, 310)
        self.assertIsNone(self.scheduler.plan(self.settings, 'battery', self.rows, 400))
        self.assertIsNotNone(self.scheduler.plan(self.settings, 'battery', self.rows, 611))
        self.scheduler.manual_completed(3500)
        self.assertIsNone(self.scheduler.plan(self.settings, 'adapter', self.rows, 4000))

    def test_current_repos_only_and_unchanged_repos_do_not_trigger(self):
        self.rows[0]['needs_backup'] = False
        self.scheduler.observe(self.rows[:1], 500)
        self.assertIsNone(self.scheduler.plan(self.settings, 'battery', self.rows[:1], 550))
        self.assertNotIn('two', self.scheduler.changes)

    def test_validation_rejects_arbitrary_values_paths_booleans_and_missing_fields(self):
        self.assertEqual(validate_settings(self.settings), self.settings)
        for key, value in [('frequency_minutes', True), ('frequency_minutes', 1),
                           ('edit_delay_minutes', -1), ('after_edits', 'yes')]:
            candidate = copy.deepcopy(self.settings)
            candidate['battery'][key] = value
            with self.assertRaises(ValueError):
                validate_settings(candidate)
        for candidate in [None, [], {'backup_root': '/outside'}, {'battery': self.settings['battery']}]:
            with self.assertRaises(ValueError):
                validate_settings(candidate)

    def test_power_source_uses_first_line_and_missing_probe_is_unknown(self):
        for raw, source in [("Now drawing from 'AC Power'\n95%; not charging", 'adapter'),
                            ("Now drawing from 'Battery Power'\n95%", 'battery'), ('', 'unknown')]:
            with patch('backup_policy.subprocess.run', return_value=subprocess.CompletedProcess([], 0, raw)):
                self.assertEqual(power_source(), source)
        with patch('backup_policy.subprocess.run', side_effect=OSError('failed')):
            self.assertEqual(power_source(), 'unknown')


class HealthTests(unittest.TestCase):
    def test_stale_scan_cloud_and_hash_each_revoke_freshness(self):
        for field, delta in [('scan', 121), ('cloud', 46), ('hash', 1021)]:
            status = status_at(5000)
            if field == 'scan':
                status['scanned_at'] = stamp(5000-delta)
            else:
                status['repos'][0]['cloud' if field == 'cloud' else 'verification']['checked_at'] = stamp(5000-delta)
            annotate_health(status, {}, 5000)
            self.assertFalse(status['repos'][0]['health']['fresh'])
        status = status_at(5000)
        annotate_health(status, {}, 5000)
        self.assertTrue(status['repos'][0]['health']['fresh'])

    def test_future_or_missing_checks_cannot_stay_green(self):
        status = status_at(5000)
        status['scanned_at'] = stamp(6000)
        annotate_health(status, {}, 5000)
        self.assertFalse(status['repos'][0]['health']['fresh'])
        status['scanned_at'] = None
        annotate_health(status, {}, 5000)
        self.assertFalse(status['repos'][0]['health']['fresh'])

    def test_problem_episodes_persist_and_recovery_creates_a_new_episode(self):
        tracker = ProblemTracker()
        status = status_at(5000)
        status['repos'][0]['health'] = {'fresh': True}
        status['repos'][0]['cloud']['state'] = 'error'
        self.assertEqual(tracker.update(status, 5000), [])
        first = tracker.update(status, 5121)[0]
        reloaded = ProblemTracker(json.loads(json.dumps(tracker.episodes)))
        self.assertEqual(reloaded.update(status, 5500)[0]['id'], first['id'])
        status['repos'][0]['cloud']['state'] = 'uploaded'
        self.assertEqual(reloaded.update(status, 5510), [])
        status['repos'][0]['cloud']['state'] = 'error'
        reloaded.update(status, 5520)
        self.assertNotEqual(reloaded.update(status, 5641)[0]['id'], first['id'])

    def test_progress_with_4355_is_not_an_error_and_restarts_stall_timer(self):
        tracker = ProblemTracker()
        status = status_at(5000)
        status['repos'][0]['health'] = {'fresh': True}
        status['repos'][0]['cloud'].update(state='uploading', percent=10, error_code=4355)
        tracker.update(status, 5000)
        self.assertEqual(tracker.update(status, 6700), [])
        status['repos'][0]['cloud']['percent'] = 20
        self.assertEqual(tracker.update(status, 6701), [])
        self.assertEqual(tracker.update(status, 8400), [])
        self.assertEqual(len(tracker.update(status, 8502)), 1)

    def test_long_copy_resets_its_wait_when_the_active_repo_changes(self):
        tracker = ProblemTracker()
        status = status_at(5000)
        status['repos'][0]['health'] = {'fresh': True}
        status['backup'] = {'running': True, 'started_at': stamp(5000), 'current_repo': 'One'}
        tracker.update(status, 5000)
        self.assertEqual(tracker.update(status, 6799), [])
        status['backup']['current_repo'] = 'Two'
        self.assertEqual(tracker.update(status, 6800), [])
        self.assertEqual(len(tracker.update(status, 8601)), 1)

    def test_stale_and_backup_errors_wait_two_minutes(self):
        tracker = ProblemTracker()
        status = status_at(5000)
        status['repos'][0]['health'] = {'fresh': False}
        status['backup']['errors'] = [{'repo': 'Example', 'error': 'copy failed'}]
        self.assertEqual(tracker.update(status, 5000), [])
        self.assertEqual(len(tracker.update(status, 5121)), 2)


class SettingsHTTPTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        (root/'repos/Example').mkdir(parents=True)
        (root/'repos/Example/file').write_text('fixture')
        (root/'cloud').mkdir()
        self.config = {'repos_root': str(root/'repos'), 'backup_root': str(root/'cloud/Snapshots'), 'state_dir': str(root/'state')}
        self.hub = Hub(self.config)
        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.server.hub = self.hub
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.origin = f'http://127.0.0.1:{self.server.server_port}'

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.temp.cleanup()

    def request(self, payload=None, origin=None):
        req = urllib.request.Request(self.origin+'/api/settings',
            data=None if payload is None else json.dumps(payload).encode(),
            headers={'Origin': origin or self.origin, 'X-RepoHub-Token': self.hub.csrf, 'Content-Type': 'application/json'})
        with urllib.request.urlopen(req) as response:
            return json.load(response)

    def test_settings_persist_with_revision_and_reject_stale_writes(self):
        current = self.request()
        settings = current['settings']
        settings['adapter']['frequency_minutes'] = 30
        self.request({'settings': settings, 'revision': current['revision']})
        self.assertEqual(Hub(self.config).settings['adapter']['frequency_minutes'], 30)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request({'settings': settings, 'revision': current['revision']})
        self.assertEqual(caught.exception.code, 409)
        caught.exception.close()

    def test_settings_write_keeps_origin_and_validation_guards(self):
        current = self.request()
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request(current, origin='https://evil.example')
        self.assertEqual(caught.exception.code, 403)
        caught.exception.close()
        invalid = copy.deepcopy(current)
        invalid['settings']['battery']['frequency_minutes'] = 1
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.request(invalid)
        self.assertEqual(caught.exception.code, 400)
        caught.exception.close()
        self.assertEqual(self.request()['revision'], current['revision'])

    def test_automatic_start_rechecks_power_but_manual_always_runs(self):
        with patch('repohub.power_source', return_value='adapter'):
            self.assertFalse(self.hub.backup(expected_power='battery'))
            self.assertFalse(self.hub.index)
            self.assertTrue(self.hub.backup())
            self.assertIn(workspace_id('Example'), self.hub.index)

    def test_power_change_finishes_current_archive_and_stops_next_repo(self):
        other = Path(self.config['repos_root'])/'Other'
        other.mkdir()
        (other/'file').write_text('other')
        with patch('repohub.power_source', side_effect=['battery', 'battery', 'adapter']):
            self.hub.backup(reason='after_edits', expected_power='battery')
        self.assertIn(workspace_id('Example'), self.hub.index)
        self.assertNotIn(workspace_id('Other'), self.hub.index)
        self.assertNotIn('repohub-data', self.hub.index)

    def test_stale_upload_receipt_keeps_previous_backup(self):
        self.hub.config['retention'] = 'latest'
        self.hub.retention = 'latest'
        self.hub.config['require_upload_before_prune'] = True
        self.hub.backup()
        key = workspace_id('Example')
        old = self.hub.index[key]['archive']
        (Path(self.config['repos_root'])/'Example/file').write_text('changed')
        self.hub.backup()
        current = self.hub.index[key]
        self.hub.cloud_states[key] = {'archive': current['archive'], 'state': 'uploaded', 'checked_at': stamp(0)}
        self.hub.retain_current(key, current)
        self.assertTrue(Path(old).exists())

    def test_periodic_clock_survives_restart_and_respects_elapsed_wall_time(self):
        self.hub.backup()
        reloaded = Hub(self.config)
        self.assertEqual(reloaded.last_periodic_at, self.hub.last_periodic_at)
        with patch('repohub.power_source', return_value='adapter'), patch.object(reloaded, 'backup', return_value=True) as backup:
            reloaded.automatic_tick()
            backup.assert_not_called()
            reloaded.last_periodic_at -= 3601
            reloaded.automatic_tick()
            backup.assert_called_once()

    def test_after_edit_plan_only_archives_selected_repo(self):
        other = Path(self.config['repos_root'])/'Other'
        other.mkdir()
        (other/'file').write_text('other')
        self.hub.backup(keys=[workspace_id('Example')], reason='after_edits')
        self.assertIn(workspace_id('Example'), self.hub.index)
        self.assertNotIn(workspace_id('Other'), self.hub.index)
        self.assertIn('repohub-data', self.hub.index)


if __name__ == '__main__':
    unittest.main()
