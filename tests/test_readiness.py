import json
import threading
import unittest
import urllib.request
import urllib.error
import test_access_failures
from repohub import Handler,ThreadingHTTPServer
from diagnostics import read_events
from diagnostic_export import export_bundle


class ReadinessTests(unittest.TestCase):
    setUp=test_access_failures.AccessTests.setUp
    tearDown=test_access_failures.AccessTests.tearDown
    def test_helper_probe_detects_and_recovers_denial_without_changing_backup(self):
        before=self.hub.registry.path.read_bytes();index=json.dumps(self.hub.index,sort_keys=True)
        (self.a/'file').chmod(0)
        try:
            self.hub.check_readiness();status=self.hub.readiness_status()
            self.assertEqual(next(r for r in status['sources'] if r['id']==self.ids[self.a])['state'],'blocked')
            self.assertEqual(status['destination']['state'],'accessible')
        finally:(self.a/'file').chmod(self.modes[self.a/'file'])
        self.hub.check_readiness();self.assertTrue(all(r['state']=='accessible' for r in self.hub.readiness_status()['sources']))
        self.assertEqual(self.hub.registry.path.read_bytes(),before);self.assertEqual(json.dumps(self.hub.index,sort_keys=True),index)
        self.assertFalse(list(self.hub.backups.glob('.repohub-access-*')))
        raw=json.dumps(list(read_events(self.hub.state_dir/'diagnostics')))
        self.assertNotIn(str(self.a),raw)
    def test_notifications_are_optional_and_do_not_gate_backup(self):
        from repohub import atomic_json
        atomic_json(self.hub.state_dir/'notifications.json',{'enabled':False,'permission':'denied'})
        self.hub.check_readiness();self.assertEqual(self.hub.readiness_status()['notifications']['permission'],'denied')
        (self.a/'file').write_text('new');self.hub.backup(keys=[self.ids[self.a]])
        self.assertFalse(self.hub.status['backup']['errors'])
    def test_access_endpoint_requires_origin_token_and_no_path_payload(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.hub=self.hub
        threading.Thread(target=server.serve_forever,daemon=True).start();origin=f'http://127.0.0.1:{server.server_port}'
        def send(body,headers):
            request=urllib.request.Request(origin+'/api/readiness/check',data=json.dumps(body).encode(),headers={'Content-Type':'application/json',**headers})
            return urllib.request.urlopen(request)
        try:
            for body,headers,code in [({}, {},403),({'path':str(self.a)},{'Origin':origin,'X-RepoHub-Token':self.hub.csrf},400)]:
                with self.assertRaises(urllib.error.HTTPError) as caught:send(body,headers)
                self.assertEqual(caught.exception.code,code);caught.exception.close()
            with send({}, {'Origin':origin,'X-RepoHub-Token':self.hub.csrf}) as response:self.assertEqual(response.status,200)
            while self.hub.readiness_running:__import__('time').sleep(.01)
        finally:server.shutdown();server.server_close()
