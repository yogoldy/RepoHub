import copy
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from repohub import Hub, archive_manifest, content_manifest, sha256, workspace_id


class ScopedBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repos = {}
        for name in ('Changed', 'FinderOnly', 'Unchanged'):
            root = self.base/'repos'/name
            (root/'.git').mkdir(parents=True)
            (root/'.git/history').write_text('history')
            (root/'.DS_Store').write_text('Finder before')
            (root/'ignored').mkdir()
            (root/'ignored/cache').write_text('ignored but protected')
            (root/'work').write_text('work before')
            self.repos[name] = root
        (self.base/'cloud').mkdir()
        self.hub = Hub({'repos_root':str(self.base/'repos'), 'backup_root':str(self.base/'cloud/Snapshots'),
                        'state_dir':str(self.base/'state'), 'retention':'all'})
        self.hub.backup()
        self.original = copy.deepcopy(self.hub.index)

    def tearDown(self):
        self.temp.cleanup()

    def archive(self, name):
        return self.hub.index[workspace_id(name)]['archive']

    def test_repeated_finder_writes_do_not_replace_archives_or_rewrite_cloud_index(self):
        index = self.hub.backups/'index.json'
        initial = (index.read_bytes(), index.stat().st_mtime_ns)
        for i in range(3):
            (self.repos['FinderOnly']/'.DS_Store').write_text('Finder layout '+str(i))
            self.hub.scan(force=True)
            row = next(r for r in self.hub.status['repos'] if r['name']=='FinderOnly')
            self.assertFalse(row['needs_backup'])
            self.assertEqual(row['verification']['state'], 'different')
            self.assertTrue(row['verification']['ignored_finder_only'])
            self.assertNotEqual(row['verification']['content_signature'], row['verification']['archive_content_signature'])
            self.hub.backup(reason='scheduled')
        self.assertEqual(self.hub.index, self.original)
        self.assertEqual((index.read_bytes(), index.stat().st_mtime_ns), initial)
        self.assertEqual(len(list(self.hub.backups.rglob('*.tar.gz'))), len(self.original))

    def test_only_meaningfully_changed_repo_gets_archive_when_schedule_checks_every_repo(self):
        (self.repos['FinderOnly']/'.DS_Store').write_text('Finder after')
        (self.repos['Changed']/'.DS_Store').write_text('include this too')
        (self.repos['Changed']/'.git/history').write_text('new committed history')
        (self.repos['Changed']/'ignored/cache').write_text('new ignored work')
        self.hub.backup(reason='scheduled')
        key = workspace_id('Changed')
        self.assertNotEqual(self.hub.index[key]['archive'], self.original[key]['archive'])
        for other in ('FinderOnly','Unchanged','repohub-data'):
            other_key = other if other=='repohub-data' else workspace_id(other)
            self.assertEqual(self.hub.index[other_key], self.original[other_key])
        self.assertEqual(archive_manifest(self.archive('Changed'),'Changed'), content_manifest(self.repos['Changed']))
        self.assertEqual(len(list(self.hub.backups.rglob('*.tar.gz'))), len(self.original)+1)

    def test_targeted_backup_cannot_copy_another_repo_even_if_it_changed(self):
        for name in ('Changed','Unchanged'):
            (self.repos[name]/'work').write_text('real edit '+name)
        self.hub.backup(keys=[workspace_id('Changed')], reason='after_edits')
        self.assertNotEqual(self.archive('Changed'), self.original[workspace_id('Changed')]['archive'])
        self.assertEqual(self.archive('Unchanged'), self.original[workspace_id('Unchanged')]['archive'])
        row=next(r for r in self.hub.status['repos'] if r['name']=='Unchanged')
        self.assertTrue(row['needs_backup'])

    def test_unknown_or_non_workspace_selection_cannot_trigger_any_archive(self):
        for keys in (['unknown'], ['repohub-data'], [['invalid']], 'Changed'):
            with self.assertRaises(ValueError):self.hub.backup(keys=keys)
        self.assertFalse(self.hub.backup(keys=[]))
        self.assertEqual(self.hub.index, self.original)

    def test_finder_add_remove_and_nested_writes_are_ignored_only_for_regular_files(self):
        root=self.repos['FinderOnly']
        (root/'.DS_Store').unlink()
        (root/'.git/.DS_Store').write_text('nested Finder state')
        self.hub.scan(force=True)
        row=next(r for r in self.hub.status['repos'] if r['name']=='FinderOnly')
        self.assertFalse(row['needs_backup'])
        (root/'.DS_Store').symlink_to('work')
        self.hub.scan(force=True)
        row=next(r for r in self.hub.status['repos'] if r['name']=='FinderOnly')
        self.assertTrue(row['needs_backup'])
        self.assertFalse(row['verification']['ignored_finder_only'])

    def test_appledouble_and_hidden_ignored_files_are_still_protected(self):
        root=self.repos['Changed']
        for relative in ('._work','.env','ignored/cache'):
            (root/relative).write_text('preserve '+relative)
            self.hub.scan(force=True)
            row=next(r for r in self.hub.status['repos'] if r['name']=='Changed')
            self.assertTrue(row['needs_backup'])
            self.hub.backup(keys=[workspace_id('Changed')])
            self.assertEqual(archive_manifest(self.archive('Changed'),'Changed'), content_manifest(root))

    def test_finder_exception_cannot_hide_corrupt_archive(self):
        root=self.repos['FinderOnly'];old=self.archive('FinderOnly')
        Path(old).write_bytes(b'corrupt')
        (root/'.DS_Store').write_text('Finder after')
        self.hub.scan(force=True)
        row=next(r for r in self.hub.status['repos'] if r['name']=='FinderOnly')
        self.assertTrue(row['needs_backup'])
        self.assertEqual(row['verification']['state'],'error')
        self.hub.backup(keys=[workspace_id('FinderOnly')])
        self.assertNotEqual(self.archive('FinderOnly'),old)
        self.assertEqual(sha256(self.archive('FinderOnly')),self.hub.index[workspace_id('FinderOnly')]['sha256'])

    def test_finder_write_does_not_reset_meaningful_edit_hint(self):
        self.hub.scan(force=True)
        before=next(r for r in self.hub.status['repos'] if r['name']=='FinderOnly')
        (self.repos['FinderOnly']/'.DS_Store').write_text('Finder after')
        self.hub.scan(force=True)
        after=next(r for r in self.hub.status['repos'] if r['name']=='FinderOnly')
        self.assertNotEqual(before['signature'],after['signature'])
        self.assertEqual(before['edit_signature'],after['edit_signature'])
