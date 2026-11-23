import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from backup_layout import BackupLayout, LayoutTransaction, readable_paths
from repohub import atomic_json


class LayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.root = self.base / 'backups'
        self.state = self.base / 'state'
        self.root.mkdir(); self.state.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def test_names_keep_identity_separate_and_group_duplicate_parents(self):
        rows = [{'id': 'one', 'path': '/work/Client A/App'},
                {'id': 'two', 'path': '/work/Client B/App'},
                {'id': 'three', 'path': '/work/Other'}]
        names = readable_paths(rows)
        self.assertEqual(names['one'], 'Client A/App')
        self.assertEqual(names['two'], 'Client B/App')
        self.assertEqual(names['three'], 'Other')
        self.assertEqual(readable_paths([{'id': 'one', 'path': '/a/app'},
                                        {'id': 'two', 'path': '/b/APP'}])['one'], 'a/app')

    def test_journal_recovers_rename_and_partial_metadata_write_without_losing_bytes(self):
        (self.root / 'old-id').mkdir()
        (self.root / 'old-id/archive.tar.gz').write_bytes(b'archive bytes')
        calls = []
        def interrupted(path, value):
            if str(path).endswith('backup-layout.json'):
                raise OSError('synthetic write interruption')
            calls.append(str(path)); atomic_json(path, value)
        updates = {'data/backup-layout.json': {'old-id': 'Project'}, 'backups.json': {'kept': True}}
        with self.assertRaises(OSError):
            LayoutTransaction(self.state, interrupted).begin(self.root, [('old-id', 'Project')], updates)
        self.assertTrue((self.state / 'layout-transaction.json').exists())
        self.assertEqual((self.root / 'Project/archive.tar.gz').read_bytes(), b'archive bytes')
        self.assertTrue(LayoutTransaction(self.state, atomic_json).recover())
        self.assertFalse(LayoutTransaction(self.state, atomic_json).recover())
        self.assertEqual(BackupLayout(self.state, self.root).directory('old-id'), self.root / 'Project')
        self.assertEqual(json.loads((self.state / 'backups.json').read_text()), {'kept': True})

    def test_stage_interruption_and_id_name_swap_are_recoverable(self):
        for key in ['one', 'two']:
            (self.root / key).mkdir(); (self.root / key / 'data').write_text(key)
        original = Path.rename
        count = 0
        def rename(path, target):
            nonlocal count
            count += 1
            if count == 2:
                raise OSError('synthetic interruption')
            return original(path, target)
        with patch.object(Path, 'rename', rename), self.assertRaises(OSError):
            LayoutTransaction(self.state, atomic_json).begin(self.root, [('one', 'two'), ('two', 'one')], {})
        LayoutTransaction(self.state, atomic_json).recover()
        self.assertEqual((self.root / 'one/data').read_text(), 'two')
        self.assertEqual((self.root / 'two/data').read_text(), 'one')

    def test_collisions_links_and_changed_archives_fail_without_overwrite(self):
        (self.root / 'old').mkdir(); (self.root / 'old/data').write_text('keep')
        (self.root / 'occupied').mkdir(); (self.root / 'occupied/data').write_text('foreign')
        with self.assertRaises(FileExistsError):
            LayoutTransaction(self.state, atomic_json).begin(self.root, [('old', 'occupied')], {})
        (self.root / 'linked').symlink_to(self.base)
        with self.assertRaises(ValueError):
            LayoutTransaction(self.state, atomic_json).begin(self.root, [('old', 'linked/New')], {})
        self.assertEqual((self.root / 'old/data').read_text(), 'keep')
        self.assertEqual((self.root / 'occupied/data').read_text(), 'foreign')
