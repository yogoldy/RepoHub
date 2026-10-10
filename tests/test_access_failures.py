import copy
import errno
import json
import os
import stat
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from repohub import Hub, content_manifest
from diagnostics import read_events
from access_checks import access_failure


class AccessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.base = Path(self.temp.name).resolve()
        self.a = self.base/'repos/A'; self.b = self.base/'repos/B'
        for p in (self.a,self.b):p.mkdir(parents=True);(p/'file').write_text('baseline')
        (self.base/'destination').mkdir()
        self.modes={p:stat.S_IMODE(p.stat().st_mode) for p in (self.a,self.b,self.a/'file',self.b/'file')}
        self.hub = Hub({'repos_root':str(self.a.parent),'state_dir':str(self.base/'state'),'backup_root':str(self.base/'destination/Snapshots')})
        self.hub.backup();self.ids = {p:k for k,p in self.hub.repositories().items()}
        self.before = copy.deepcopy(self.hub.index[self.ids[self.a]])
        self.archive_bytes = Path(self.before['archive']).read_bytes()
    def tearDown(self):self.temp.cleanup()
    def kept(self):
        self.assertEqual(self.hub.index[self.ids[self.a]], self.before)
        self.assertEqual(Path(self.before['archive']).read_bytes(), self.archive_bytes)
    def test_errno_classification_is_not_a_privacy_claim(self):
        for code,state in ((errno.EACCES,'blocked'),(errno.EPERM,'blocked'),(errno.ENOENT,'unavailable'),(errno.EIO,'error'),(errno.EROFS,'blocked')):
            value=access_failure(OSError(code,'secret path or prose'), 'source_read')
            self.assertEqual(value['state'],state);self.assertNotIn('secret',json.dumps(value))
            self.assertNotIn('TCC',value['detail'])
    def test_unreadable_nested_file_preserves_archive_and_other_repo_recovers(self):
        path=self.a/'file';path.chmod(0)
        try:
            with self.assertRaises(PermissionError):content_manifest(self.a)
            (self.b/'file').write_text('new accessible contents')
            self.hub.scan(force=True);row=next(r for r in self.hub.status['repos'] if r['id']==self.ids[self.a])
            self.assertEqual(row['verification']['access']['state'],'blocked')
            self.hub.backup();self.kept()
            self.assertNotEqual(self.hub.index[self.ids[self.b]]['signature'],self.before['signature'])
        finally:path.chmod(self.modes[path])
        self.hub.scan(force=True);self.assertEqual(next(r for r in self.hub.status['repos'] if r['id']==self.ids[self.a])['verification']['state'],'matched')
    def test_unreadable_root_scan_keeps_identity_and_previous_archive(self):
        self.a.chmod(0)
        try:
            self.hub.scan(force=True);row=next(r for r in self.hub.status['repos'] if r['id']==self.ids[self.a])
            self.assertEqual(row['access']['state'],'blocked');self.hub.backup();self.kept()
        finally:self.a.chmod(self.modes[self.a])
        self.hub.scan(force=True);self.assertNotIn('error',next(r for r in self.hub.status['repos'] if r['id']==self.ids[self.a]))
    def test_unwritable_destination_preserves_previous_archive(self):
        directory=Path(self.before['archive']).parent;old_mode=stat.S_IMODE(directory.stat().st_mode);directory.chmod(0o555)
        try:
            (self.a/'file').write_text('changed source')
            self.hub.backup(keys=[self.ids[self.a]]);self.kept()
            failure=self.hub.status['backup']['errors'][0]
            self.assertEqual(failure['access']['operation'],'destination_write');self.assertEqual(failure['access']['state'],'blocked')
        finally:directory.chmod(old_mode)
        self.hub.backup(keys=[self.ids[self.a]]);self.assertNotEqual(self.hub.index[self.ids[self.a]]['archive'],self.before['archive'])
    def test_revocation_during_archive_creation_never_publishes_partial_copy(self):
        from repohub import snapshot
        path=self.a/'file';directory=Path(self.before['archive']).parent
        def after():path.chmod(0)
        try:
            with self.assertRaises((PermissionError,RuntimeError)):snapshot(self.a,directory,self.base/'stage',after_archive=after)
            self.kept();self.assertEqual(list(directory.glob('*.tar.gz')),[Path(self.before['archive'])])
        finally:path.chmod(self.modes[path])
    def test_missing_destination_is_not_empty_success(self):
        missing=self.base/'missing';self.hub.backups=missing/'Snapshots'
        self.hub.backup(keys=[self.ids[self.a]]);self.kept()
        self.assertTrue(self.hub.status['backup']['errors'])
