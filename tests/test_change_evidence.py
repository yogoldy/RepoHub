import copy
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from repohub import Hub, Handler, ThreadingHTTPServer, workspace_id, utc_now, tree_entries
from diagnostics import read_events, diagnostic_ref
from diagnostics_report import summarize


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root/'repos'/'Private repo name'
        self.repo.mkdir(parents=True)
        (self.repo/'confidential-name.txt').write_text('secret document contents')
        (self.repo/'.DS_Store').write_text('finder before')
        (self.root/'cloud').mkdir()
        self.hub = Hub({'repos_root':str(self.repo.parent), 'backup_root':str(self.root/'cloud/Snapshots'),
                        'state_dir':str(self.root/'state')})
        self.key = workspace_id(self.repo.name)
        self.hub.backup()
        self.hub.cloud_states[self.key] = {'state':'uploaded', 'checked_at':utc_now(), 'archive':self.hub.index[self.key]['archive']}

    def tearDown(self):
        self.temp.cleanup()

    def events(self):
        return list(read_events(self.hub.state_dir/'diagnostics'))

    def payload(self, surface, label='Finder metadata changed', phase='changed'):
        status = self.hub.public_status()
        return {'surface':surface, 'native':surface=='menu', 'client_id':('a' if surface=='menu' else 'b')*24,
                'observation_id':status['diagnostic_observation_id'], 'policy_version':'change-evidence-1',
                'rows':[{'repo_id':self.key, 'display_label':label, 'phase':phase, 'ready':phase=='ready'}]}

    def test_finder_timestamp_and_real_edits_have_distinct_evidence(self):
        (self.repo/'.DS_Store').write_text('finder after')
        self.hub.scan(force=True)
        event = [e for e in self.events() if e['event']=='repo_checked' and e['repo_ref']==diagnostic_ref(self.key)][-1]
        self.assertEqual(event['reason'], 'finder_metadata_only')
        self.assertEqual(event['counts']['repo_files'], 0)
        self.assertEqual(event['samples'][0]['known_file'], 'finder_store')
        self.hub.backup()
        path = self.repo/'confidential-name.txt'; info = path.stat()
        os.utime(path, ns=(info.st_atime_ns,info.st_mtime_ns+1_000_000_000))
        self.hub.scan(force=True)
        event = [e for e in self.events() if e['event']=='repo_checked' and e['repo_ref']==diagnostic_ref(self.key)][-1]
        self.assertEqual(event['reason'], 'timestamp_only_match')
        self.assertFalse(event['needs_backup'])
        self.assertEqual(event['content_signature'], event['archive_content_signature'])
        path.write_text('different document contents')
        self.hub.scan(force=True)
        event = [e for e in self.events() if e['event']=='repo_checked' and e['repo_ref']==diagnostic_ref(self.key)][-1]
        self.assertEqual(event['reason'], 'repo_files_differ')
        raw = '\n'.join(p.read_text() for p in (self.hub.state_dir/'diagnostics').glob('*.jsonl'))
        for private in ['Private repo name','confidential-name.txt','secret document contents',str(self.repo)]:
            self.assertNotIn(private,raw)

    def test_both_views_are_correlated_and_disagreement_is_reported(self):
        (self.repo/'.DS_Store').write_text('changed')
        self.hub.scan(force=True)
        menu, app = self.payload('menu'), self.payload('app')
        self.assertEqual(menu['observation_id'],app['observation_id'])
        self.hub.evidence.presentation(menu);self.hub.evidence.presentation(app)
        report = summarize(self.events())
        self.assertEqual(report['same_observation_comparisons'],1)
        self.assertEqual(report['matching_comparisons'],1)
        self.assertFalse(report['disagreements'])
        app['rows'][0]['display_label']='Files changed'
        self.hub.evidence.presentation(app)
        report = summarize(self.events())
        self.assertEqual(len(report['disagreements']),1)
        self.assertEqual(report['matching_comparisons'],0)
        self.assertEqual(report['repos'][diagnostic_ref(self.key)]['views']['menu_native']['backend']['counts']['repo_files'],0)
        before = sum(e['event']=='ui_presented' for e in self.events())
        self.hub.evidence.presentation(app)
        self.assertEqual(sum(e['event']=='ui_presented' for e in self.events()), before)

    def test_no_record_of_second_view_is_not_claimed_as_agreement(self):
        self.hub.evidence.presentation(self.payload('menu','Backed up','ready'))
        report = summarize(self.events())
        self.assertEqual(report['same_observation_comparisons'],0)
        self.assertFalse(report['disagreements'])

    def test_diagnostic_activity_does_not_create_repo_or_saved_data_changes(self):
        repo_before, data_before = tree_entries(self.repo), tree_entries(self.hub.data_dir)
        archive = self.hub.index[self.key]['archive']
        for _ in range(20):
            self.hub.diagnostics.emit('heartbeat', repo_count=1)
        self.hub.scan(force=True)
        self.hub.public_status()
        self.assertEqual(tree_entries(self.repo), repo_before)
        self.assertEqual(tree_entries(self.hub.data_dir), data_before)
        self.assertFalse(self.hub.status['repos'][0]['needs_backup'])
        self.assertEqual(self.hub.index[self.key]['archive'], archive)

    def test_observation_identity_includes_publication_errors_and_backup_hash(self):
        original = self.hub.public_status()['diagnostic_observation_id']
        self.hub.status['backup']['errors'] = [{'repo':self.repo.name,'error':'private exception prose'}]
        failed = self.hub.public_status()['diagnostic_observation_id']
        self.assertNotEqual(failed, original)
        self.hub.status['backup']['errors'] = []
        self.assertEqual(self.hub.public_status()['diagnostic_observation_id'], original)
        self.hub.status['repos'][0]['last_backup']['sha256'] = ''
        self.assertNotEqual(self.hub.public_status()['diagnostic_observation_id'], original)
        raw = '\n'.join(p.read_text() for p in (self.hub.state_dir/'diagnostics').glob('*.jsonl'))
        self.assertNotIn('private exception prose', raw)

    def test_schema_rejects_unknown_identifiers_strings_fields_and_expired_snapshots(self):
        payload = self.payload('menu','Backed up','ready')
        mutations = [lambda p:p.update(token='credential'), lambda p:p.update(surface=[]),
                     lambda p:p['rows'][0].update(repo_id=[]), lambda p:p['rows'][0].update(display_label='secret prose'),
                     lambda p:p['rows'][0].update(phase=[]), lambda p:p.update(rows=[]),
                     lambda p:p.update(rows=p['rows']*2), lambda p:p.update(policy_version='unknown')]
        for mutate in mutations:
            invalid = copy.deepcopy(payload);mutate(invalid)
            with self.assertRaises(ValueError): self.hub.evidence.presentation(invalid)
        old = copy.deepcopy(payload)
        for i in range(20):
            self.hub.status['repos'][0]['signature']=str(i)
            self.hub.public_status()
        with self.assertRaises(FileExistsError): self.hub.evidence.presentation(old)
        self.assertLessEqual(len(self.hub.evidence.snapshots),16)

    def test_presentation_endpoint_requires_origin_token_and_safe_payload(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.hub=self.hub
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin=f'http://127.0.0.1:{server.server_port}'
        payload=self.payload('app','Backed up','ready')
        def send(headers):
            req=urllib.request.Request(origin+'/api/diagnostics/presentation',data=json.dumps(payload).encode(),
                headers={'Content-Type':'application/json',**headers})
            with urllib.request.urlopen(req) as response:return json.load(response)
        try:
            for headers in [{},{'Origin':origin},{'Origin':'https://outside.example','X-RepoHub-Token':self.hub.csrf},
                            {'Origin':origin,'X-RepoHub-Token':self.hub.csrf,'Host':'localhost'}]:
                with self.assertRaises(urllib.error.HTTPError) as result:send(headers)
                self.assertEqual(result.exception.code,403);result.exception.close()
            self.assertTrue(send({'Origin':origin,'X-RepoHub-Token':self.hub.csrf})['recorded'])
            with urllib.request.urlopen(origin+'/diagnostics-client.js') as response:
                self.assertIn(b'RepoDiagnostics',response.read())
                self.assertIn("default-src 'self'",response.headers['Content-Security-Policy'])
        finally:server.shutdown();server.server_close()


if __name__=='__main__': unittest.main()
