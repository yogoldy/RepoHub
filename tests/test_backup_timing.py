"""Forecasts describe existing decisions; they cannot advance backup clocks."""
import copy
from datetime import datetime, timezone
import unittest
from backup_policy import BackupScheduler, default_settings, project_schedule
from status_health import backup_location


def stamp(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat()


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.scheduler = BackupScheduler(0)
        self.settings = default_settings()
        self.row = {'id': 'one', 'needs_backup': True, 'edit_signature': 'known'}
        self.scheduler.observe([self.row], 0)

    def forecast(self, now, **kwargs):
        return project_schedule(self.scheduler, self.settings, 'adapter', self.row,
                                10000 + now, now, 10000, {}, **kwargs)

    def test_projection_matches_actual_eligibility_and_does_not_mutate(self):
        for edits in [False, True]:
            self.settings['adapter']['after_edits'] = edits
            for frequency in [0, 15, 30, 60, 120, 240]:
                self.settings['adapter']['frequency_minutes'] = frequency
                for now in [0, 119, 299, 300, 899, 900, 3599, 3600, 14400]:
                    with self.subTest(edits=edits, frequency=frequency, now=now):
                        before = copy.deepcopy(self.scheduler.__dict__)
                        projection = self.forecast(now)
                        plan = self.scheduler.plan(self.settings, 'adapter', [self.row], now)
                        self.assertEqual(projection['state'] == 'due', plan is not None)
                        self.assertEqual(self.scheduler.__dict__, before)
                        if plan:
                            self.assertEqual(projection['reason'], 'periodic' if plan.get('periodic_keys') else 'edits')

    def test_countdown_does_not_round_float_noise_into_an_extra_minute(self):
        for wall_now, monotonic_now in [(1792179000.429823, 38000.14357),
                                        (10000.1, 0.3), (20000.9, 125.4)]:
            result = project_schedule(self.scheduler, self.settings, 'adapter', self.row,
                                      wall_now, monotonic_now, wall_now - 1800, {})
            self.assertEqual(result['due_in_seconds'], 1800)

    def test_overrides_retry_busy_and_unobserved_edits(self):
        custom = default_settings()
        custom['adapter'].update(frequency_minutes=0, after_edits=True, edit_delay_minutes=2)
        overrides = {'one': custom}
        self.scheduler.attempts['one'] = 100
        self.assertEqual(self.forecast(399, overrides=overrides)['due_in_seconds'], 1)
        self.assertEqual(self.forecast(400, overrides=overrides, busy=True)['state'], 'busy')
        self.scheduler.changes.clear()
        self.assertEqual(self.forecast(400, overrides=overrides)['state'], 'awaiting_edits')
        self.row['error'] = 'private error'
        self.assertEqual(self.forecast(400, overrides=overrides)['state'], 'blocked')
        self.assertNotIn('private', str(self.forecast(400, overrides=overrides)))

    def test_saved_cadence_manual_reset_and_power_are_respected(self):
        result = project_schedule(self.scheduler, self.settings, 'adapter', self.row,
                                  15000, 20, 10000, {'one': 14000})
        self.assertEqual(result['due_at'], stamp(17600))
        # Global manual completion resets all per-repo cadence through the existing clock writer.
        self.scheduler.manual_completed(20)
        result = project_schedule(self.scheduler, self.settings, 'adapter', self.row,
                                  15000, 20, 15000, {})
        self.assertEqual(result['due_at'], stamp(18600))
        self.settings['battery']['frequency_minutes'] = 0
        self.assertEqual(project_schedule(self.scheduler, self.settings, 'battery', self.row,
                                         15000, 20, 15000, {})['state'], 'manual')
        self.assertEqual(project_schedule(self.scheduler, self.settings, 'unknown', self.row,
                                         15000, 20, 15000, {})['state'], 'unavailable')

    def test_cloud_location_requires_same_archive_fresh_observation_and_valid_creation(self):
        row = {'needs_backup': True, 'last_backup': {'archive': '/saved', 'sha256': 'hash', 'completed_at': stamp(9000)},
               'cloud': {'archive': '/saved', 'state': 'uploaded', 'checked_at': stamp(9999)}}
        self.assertEqual(backup_location(row, 10000, 45)['state'], 'cloud_confirmed')
        for changes in [{'archive': '/old'}, {'checked_at': stamp(9000)}, {'checked_at': stamp(11000)},
                        {'checked_at': 'invalid'}, {'checked_at': None}, {'state': 'uploading', 'percent': 100}]:
            changed = copy.deepcopy(row)
            changed['cloud'].update(changes)
            self.assertEqual(backup_location(changed, 10000, 45)['state'], 'local')
        row['last_backup']['completed_at'] = 'invalid'
        self.assertEqual(backup_location(row, 10000, 45)['state'], 'unavailable')
        self.assertEqual(backup_location({}, 10000, 45)['state'], 'none')
