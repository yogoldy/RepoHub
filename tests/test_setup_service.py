import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from repohub import Hub, sha256, atomic_json


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.cloud = self.base / 'cloud'; self.cloud.mkdir()
        self.dest = self.cloud / 'Backups'; self.dest.mkdir()
        self.source = self.base / 'repos/Project'; self.source.mkdir(parents=True)
        (self.source / 'work').write_text('original source')
        self.config = {'repos_root': str(self.source.parent), 'backup_root': str(self.dest),
                       'state_dir': str(self.base / 'state'), 'retention': 'all',
                       '_setup_test_cloud_root': str(self.cloud)}
        self.hub = Hub(self.config)

    def tearDown(self):
        self.temp.cleanup()

    def draft(self, hub=None, destination=None):
        hub = hub or self.hub
        status = hub.setup.status()
        return {key: status[key] for key in ['source', 'settings', 'revision', 'discovery_parent']} | {
            'destination': str(destination or self.dest)}

    def apply(self, hub=None, destination=None):
        hub = hub or self.hub
        draft = self.draft(hub, destination)
        review = hub.setup.review(draft)
        return hub.setup.apply({'draft': draft, 'review': review['review'], 'backup_now': False})

    def test_existing_apply_migrates_names_but_preserves_bytes_ids_settings_and_restart(self):
        self.hub.backup()
        before = copy.deepcopy(self.hub.index)
        key = next(iter(self.hub.repositories()))
        self.hub.repo_settings[key] = copy.deepcopy(self.hub.settings)
        atomic_json(self.hub.repo_settings_path, self.hub.repo_settings)
        self.hub.cloud_states[key] = {'state': 'uploaded', 'archive': before[key]['archive']}
        result = self.apply()
        current = self.hub.index[key]
        self.assertTrue(result['reviewed'])
        self.assertEqual(Path(current['archive']).parent, self.dest / 'Project')
        self.assertEqual(sha256(current['archive']), before[key]['sha256'])
        self.assertEqual(current['sha256'], before[key]['sha256'])
        self.assertEqual(self.hub.cloud_for(key, current)['state'], 'unknown')
        restarted = Hub(self.config)
        self.assertIn(key, restarted.repositories())
        self.assertEqual(restarted.repo_settings[key], self.hub.repo_settings[key])
        self.assertEqual(restarted.index[key], current)
        self.assertFalse(restarted.setup.status()['recovery_required'])

    def test_destination_switch_keeps_old_archives_and_requires_new_copy(self):
        self.hub.backup(); before = copy.deepcopy(self.hub.index)
        target = self.cloud / 'New'; target.mkdir()
        self.apply(destination=target)
        key = next(iter(self.hub.repositories()))
        self.assertTrue(self.hub.public_status()['repos'][0]['needs_backup'])
        self.hub.backup()
        self.assertEqual(Path(self.hub.index[key]['archive']).parent, target / 'Project')
        for value in before.values():
            self.assertEqual(sha256(value['archive']), value['sha256'])
        self.assertEqual(Hub(self.config).backups, target)

    def test_fresh_install_is_idle_until_explicit_apply_and_preserves_default_schedule(self):
        config = {**self.config, 'setup_required': True, 'sources': {'mode': 'manual', 'paths': []}}
        config.pop('repos_root'); config['state_dir'] = str(self.base / 'fresh')
        fresh = Hub(config)
        self.assertFalse(fresh.configured)
        with self.assertRaises(ValueError):
            fresh.backup()
        fresh.automatic_tick()
        self.assertFalse((fresh.state_dir / 'backups.json').exists())
        draft = self.draft(fresh)
        draft['source']['paths'] = [str(self.source)]
        with self.assertRaises(FileExistsError):
            fresh.setup.apply({'draft': draft, 'review': 'invented', 'backup_now': False})
        review = fresh.setup.review(draft)
        fresh.setup.apply({'draft': draft, 'review': review['review'], 'backup_now': False})
        self.assertTrue(fresh.configured)
        self.assertEqual(fresh.settings['battery']['frequency_minutes'], 60)
        self.assertFalse((fresh.state_dir / 'backups.json').read_text() != '{}\n')
        self.assertGreater(fresh.last_periodic_at, 0)
        self.assertTrue(Hub(config).configured)

    def test_stale_busy_denied_and_changed_selection_never_apply_a_partial_draft(self):
        draft = self.draft(); review = self.hub.setup.review(draft)
        baseline = self.hub.registry.path.read_bytes()
        changed = copy.deepcopy(draft); changed['settings']['battery']['frequency_minutes'] = 15
        with self.assertRaises(FileExistsError):
            self.hub.setup.apply({'draft': changed, 'review': review['review'], 'backup_now': False})
        with self.hub.backup_lock, self.assertRaises(FileExistsError):
            self.hub.setup.apply({'draft': draft, 'review': review['review'], 'backup_now': False})
        with patch('setup_service.probe_source', side_effect=PermissionError('synthetic denial')):
            with self.assertRaises(PermissionError):
                self.hub.setup.apply({'draft': draft, 'review': review['review'], 'backup_now': False})
        self.assertEqual(baseline, self.hub.registry.path.read_bytes())
        self.assertFalse((self.hub.data_dir / 'setup.json').exists())
        self.hub.save_settings({'revision': self.hub.settings_status()['revision'],
                                'settings': self.hub.settings})
        atomic_json(self.hub.settings_path, {**self.hub.settings, 'battery': {
            'frequency_minutes': 15, 'after_edits': False, 'edit_delay_minutes': 5}})
        with self.assertRaises(FileExistsError):
            self.hub.setup.apply({'draft': draft, 'review': review['review'], 'backup_now': False})

    def test_existing_continue_and_fresh_cancel_do_not_activate_changes(self):
        source = self.hub.registry.path.read_bytes()
        revision = self.hub.setup.status()['revision']
        self.hub.setup.continue_current({'revision': revision})
        self.assertEqual(source, self.hub.registry.path.read_bytes())
        self.assertIsNone(self.hub.layout.names)
        self.assertTrue(Hub(self.config).setup_record['reviewed'])

    def test_interrupted_metadata_save_blocks_runtime_until_restart_recovers(self):
        self.hub.backup()
        draft = self.draft(); review = self.hub.setup.review(draft)
        original = self.hub.setup.writer
        def fail(path, value):
            if Path(path).name == 'setup.json':
                raise OSError('synthetic storage failure')
            original(path, value)
        self.hub.setup.writer = fail
        with self.assertRaises(OSError):
            self.hub.setup.apply({'draft': draft, 'review': review['review'], 'backup_now': False})
        self.assertTrue(self.hub.setup_recovery_required)
        with self.assertRaises(ValueError):
            self.hub.backup()
        self.assertTrue(Hub(self.config).setup.status()['reviewed'])
