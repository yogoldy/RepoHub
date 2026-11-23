import json
from pathlib import Path
import tempfile
import unittest
from diagnostics import DiagnosticLog
from report_preview import preview_report

class ReportPreviewTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.logs=self.root/'diagnostics';self.state=self.root/'state'
        DiagnosticLog(self.logs).emit('repo_checked',repo_ref='private-repo',reason='repo_files_differ')
    def tearDown(self):self.temp.cleanup()
    def bug(self,**extra):
        return {'type':'bug','title':'Unexpected changed icon','description':'I saw a change without editing.','expected':'An unchanged icon.',**extra}
    def test_bug_has_exact_share_files_and_private_local_draft(self):
        result=preview_report(self.state,self.logs,self.bug())
        self.assertEqual(result['state'],'draft');self.assertTrue(result['delivery_available'])
        self.assertEqual(result['labels'],['bug','from-app'])
        self.assertEqual({f['name'] for f in result['files']},{'schema.json','events.jsonl'})
        shared=json.dumps(result)
        self.assertNotIn('private-repo',shared);self.assertNotIn('PRIVATE_ALIAS_KEY',shared)
        draft=self.state/'reports'/result['report_id']/'draft.json'
        self.assertEqual(json.loads(draft.read_text()),result)
        self.assertEqual(draft.stat().st_mode & 0o777,0o600)
        self.assertIn('What I expected',result['body'])
    def test_feature_separate_labels_and_no_default_diagnostics(self):
        result=preview_report(self.state,self.logs,{'type':'feature','title':'New idea','description':'Explain the selected icon.'})
        self.assertEqual(result['type'],'feature');self.assertEqual(result['files'],[])
        self.assertEqual(result['labels'],['enhancement','from-app'])
        self.assertNotIn('What I expected',result['body'])
    def test_omit_logs_and_explicit_feature_opt_in(self):
        self.assertEqual(preview_report(self.state,self.logs,self.bug(include_diagnostics=False))['files'],[])
        result=preview_report(self.state,self.logs,{'type':'feature','title':'Idea','description':'Prose','include_diagnostics':True,'hours':1})
        self.assertEqual(len(result['files']),2)
    def test_bad_inputs_and_destination_injection_rejected(self):
        for payload in [self.bug(title=' '),self.bug(expected=''),self.bug(description='x'*8001),self.bug(type='other'),self.bug(include_diagnostics='true'),self.bug(hours=True),self.bug(destination='https://evil.test')]:
            with self.subTest(payload=payload):
                with self.assertRaises(ValueError):preview_report(self.state,self.logs,payload)
    def test_prose_is_preserved_for_exact_preview_not_treated_as_markup(self):
        text='<img src=x onerror="bad()">\nprivate prose'
        result=preview_report(self.state,self.logs,self.bug(description=text,include_diagnostics=False))
        self.assertIn(text,result['body'])

    def test_http_preview_requires_existing_origin_and_token_checks(self):
        import threading
        import urllib.request
        import urllib.error
        from types import SimpleNamespace
        from http.server import ThreadingHTTPServer
        from repohub import Handler
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.hub=SimpleNamespace(state_dir=self.state,diagnostics=SimpleNamespace(directory=self.logs),csrf='test-token')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        try:
            request=urllib.request.Request(origin+'/api/reports/preview',json.dumps(self.bug()).encode(),{'Content-Type':'application/json'})
            with self.assertRaises(urllib.error.HTTPError) as failure:urllib.request.urlopen(request)
            self.assertEqual(failure.exception.code,403)
            request=urllib.request.Request(origin+'/api/reports/preview',json.dumps(self.bug(include_diagnostics=False)).encode(),{'Content-Type':'application/json','Origin':origin,'X-RepoHub-Token':'test-token'})
            with urllib.request.urlopen(request) as response:
                self.assertEqual(response.status,201)
                self.assertEqual(json.load(response)['state'],'draft')
        finally:
            server.shutdown();server.server_close();thread.join()
