import unittest
import copy
import json
from pathlib import Path
from unittest.mock import patch
import test_access_failures
from repohub import Hub
from workspace_registry import SourceIdentityChanged, source_identity


class IdentityTests(unittest.TestCase):
    setUp = test_access_failures.AccessTests.setUp
    tearDown = test_access_failures.AccessTests.tearDown
    kept = test_access_failures.AccessTests.kept
    def test_replacement_at_same_path_requires_review_and_preserves_id(self):
        old=self.a.with_name('held-original');self.a.rename(old);self.a.mkdir();(self.a/'file').write_text('replacement')
        self.hub.scan(force=True)
        row=next(r for r in self.hub.status['repos'] if r['id']==self.ids[self.a])
        self.assertEqual(row['access']['state'],'changed')
        self.hub.backup(keys=[self.ids[self.a]]);self.kept()
        source={'mode':'manual','paths':[str(self.a)]};revision=self.hub.workspace_status()['revision']
        review=self.hub.preview_workspaces({'source':source,'revision':revision})
        self.hub.save_workspaces({'source':source,'revision':revision,'review':review['review']})
        self.assertEqual(self.hub.repositories(),{self.ids[self.a]:self.a})
        self.hub.backup(keys=[self.ids[self.a]]);self.assertNotEqual(self.hub.index[self.ids[self.a]]['archive'],self.before['archive'])
    def test_original_directory_restores_without_identity_reset(self):
        old=self.a.with_name('held-original');self.a.rename(old)
        self.hub.scan(force=True);self.hub.backup(keys=[self.ids[self.a]]);self.kept()
        old.rename(self.a);self.hub.scan(force=True)
        self.assertNotIn('error',next(r for r in self.hub.status['repos'] if r['id']==self.ids[self.a]))
    def test_volume_mismatch_cannot_be_hidden_by_same_inode(self):
        identity=source_identity(self.a);identity['volume']='different-volume'
        with patch('workspace_registry.source_identity',return_value=identity):
            with self.assertRaises(SourceIdentityChanged):self.hub.registry.require_workspace(self.ids[self.a],self.a)
    def test_legacy_identity_migration_waits_for_accessible_source(self):
        p=self.hub.registry.path;value=json.loads(p.read_text())
        for r in value['workspaces']:r.pop('identity',None)
        value['source'].pop('identity',None);p.write_text(json.dumps(value));self.a.chmod(0)
        try:
            again=Hub(self.hub.config);row=next(r for r in again.registry.value['workspaces'] if r['id']==self.ids[self.a])
            self.assertNotIn('identity',row)
            self.assertEqual(again.index[self.ids[self.a]],self.before)
        finally:self.a.chmod(self.modes[self.a])
        again.registry.refresh();self.assertEqual(again.registry.value['workspaces'][0]['id'],self.ids[self.a])
