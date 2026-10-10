import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from diagnostic_export import export_bundle
from diagnostics import DiagnosticLog
from report_delivery import (DeliveryError, GitHubClient, connection_status, delivery_status,
                             digest, public_payload, send_report)
from report_preview import preview_report


class Client:
    repository = 'yogoldy/RepoHub'
    def __init__(self):
        self.login='fixture-user'; self.creates=0; self.finds=0; self.row=None; self.error=None
    def account(self): return self.login
    def create(self, payload):
        self.creates+=1
        self.row={'number':17,'html_url':'https://github.com/yogoldy/RepoHub/issues/17',
                  **payload,'user':{'login':self.login}}
        if self.error: raise self.error
        return self.row
    def find(self, account, payload, marker):
        self.finds+=1
        return self.row


class ReportDeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.logs=DiagnosticLog(self.root/'logs');self.client=Client()
        self.draft=preview_report(self.root/'state',self.logs.directory,
            {'type':'bug','title':'Synthetic report','description':'Controlled issue',
             'expected':'Correct status','include_diagnostics':False})
        self.payload={'report_id':self.draft['report_id'],'preview_digest':self.draft['preview_digest'],
                      'account':self.client.login,'confirm':True}
        self.case=self.root/'state/reports'/self.draft['report_id']
    def tearDown(self): self.temp.cleanup()
    def send(self): return send_report(self.root/'state',self.payload,self.client,self.logs)

    def test_exact_preview_receipt_and_repeat_send_never_duplicates(self):
        issue=public_payload(self.draft)
        self.assertEqual(issue['body'],self.draft['issue_body'])
        self.assertEqual(digest(issue),self.draft['preview_digest'])
        self.assertEqual(self.send()['state'],'sent')
        self.assertEqual(self.send()['issue_url'],'https://github.com/yogoldy/RepoHub/issues/17')
        self.assertEqual(self.client.creates,1)
        self.assertEqual((self.case/'delivery.json').stat().st_mode & 0o777,0o600)
        self.assertEqual(self.client.row['labels'],['bug','from-app'])

    def test_lost_post_response_recovers_existing_issue_without_second_post(self):
        self.client.error=DeliveryError('network_unavailable',True)
        self.assertEqual(self.send()['state'],'uncertain')
        self.assertEqual(self.send()['state'],'sent')
        self.assertEqual(self.client.creates,1);self.assertEqual(self.client.finds,1)

    def test_absent_issue_after_ambiguous_send_is_not_permission_to_repost(self):
        self.client.error=DeliveryError('network_unavailable',True);self.send()
        self.client.row=None
        for _ in range(3): self.assertEqual(self.send()['state'],'uncertain')
        self.assertEqual(self.client.creates,1)
        self.assertTrue((self.case/'draft.json').exists())

    def test_explicit_rejection_can_retry_and_account_switch_cannot_post(self):
        self.client.error=DeliveryError('github_rejected')
        self.assertEqual(self.send()['state'],'failed')
        self.client.error=None;self.client.login='other-user'
        self.assertEqual(self.send()['error_code'],'account_changed')
        self.assertEqual(self.client.creates,1)
        self.client.login=self.payload['account'];self.assertEqual(self.send()['state'],'sent')
        self.assertEqual(self.client.creates,2)

    def test_process_interruption_leaves_durable_uncertain_identity(self):
        self.client.error=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt): self.send()
        self.assertEqual(delivery_status(self.root/'state',self.payload['report_id'])['state'],'uncertain')
        self.client.error=None
        self.assertEqual(self.send()['state'],'sent');self.assertEqual(self.client.creates,1)

    def test_double_click_while_posting_is_serialized(self):
        entered=threading.Event();release=threading.Event();original=self.client.create
        def create(payload): entered.set();release.wait(3);return original(payload)
        self.client.create=create
        results=[];thread=threading.Thread(target=lambda:results.append(self.send()));thread.start()
        try:
            self.assertTrue(entered.wait(2));self.assertEqual(self.send()['state'],'sending')
        finally: release.set();thread.join()
        self.assertEqual(results[0]['state'],'sent');self.assertEqual(self.client.creates,1)

    def test_client_cannot_change_destination_payload_or_consent(self):
        for changes in [{'confirm':False},{'destination':'https://evil.test'},
                        {'preview_digest':'0'*64},{'report_id':'../outside'},{'body':'secret'}]:
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):send_report(self.root/'state',{**self.payload,**changes},self.client)
        self.assertEqual(self.client.creates,0)
        changed=json.loads((self.case/'draft.json').read_text());changed['body']='changed after preview'
        (self.case/'draft.json').write_text(json.dumps(changed))
        with self.assertRaises(ValueError):self.send()
        self.assertEqual(self.client.creates,0)

    def test_foreign_or_malformed_receipt_never_becomes_sent(self):
        original=self.client.create
        def create(payload): row=original(payload);row['html_url']='https://evil.test/issues/17';return row
        self.client.create=create
        self.assertEqual(self.send()['state'],'uncertain')
        self.assertEqual(self.send()['state'],'uncertain');self.assertEqual(self.client.creates,1)

    def test_symlinked_report_or_receipt_is_rejected(self):
        outside=self.root/'outside';outside.write_text('{}')
        (self.case/'delivery.json').symlink_to(outside)
        with self.assertRaises(OSError):self.send()
        self.assertEqual(self.client.creates,0)
        (self.case/'delivery.json').unlink();(self.case/'draft.json').unlink();(self.case/'draft.json').symlink_to(outside)
        with self.assertRaises(OSError):self.send()

    def test_bounded_body_and_private_alias_key_never_shared(self):
        draft=preview_report(self.root/'state',self.logs.directory,
            {'type':'feature','title':'Feature','description':'New behavior','include_diagnostics':True})
        issue=public_payload(draft)
        self.assertLessEqual(len(issue['body'].encode()),60000)
        self.assertNotIn('PRIVATE_ALIAS_KEY',issue['body'])
        self.assertEqual(issue['labels'],['enhancement','from-app'])
        draft['body']='🙂'*20000
        with self.assertRaises(ValueError):public_payload(draft)

    def test_delivery_diagnostics_contain_only_codes_and_aliased_identity(self):
        self.send()
        bundle=export_bundle(self.logs.directory,self.root/'export')
        shared=(bundle/'share/events.jsonl').read_text()
        self.assertIn('report_delivery',shared);self.assertIn('sent',shared)
        for private in [self.payload['report_id'],self.client.login,'Synthetic report','Controlled issue','https://github.com']:
            self.assertNotIn(private,shared)
        self.logs.emit('report_delivery',report_ref='private-id',state='PRIVATE TEXT',reason='PRIVATE SECRET')
        bundle=export_bundle(self.logs.directory,self.root/'export2')
        shared=(bundle/'share/events.jsonl').read_text()
        self.assertNotIn('PRIVATE TEXT',shared);self.assertNotIn('PRIVATE SECRET',shared)

    def test_connection_errors_never_expose_credentials_or_error_prose(self):
        class Unconnected:
            def account(self):raise DeliveryError('connection_required')
        self.assertEqual(connection_status(Unconnected()),{'ready':False,'error_code':'connection_required'})
        self.assertEqual(connection_status(self.client),{'ready':True,'account':'fixture-user'})

    def test_reconciliation_requires_exact_body_not_only_marker(self):
        client=GitHubClient(token_reader=lambda:'not-a-real-token')
        row={'title':'wrong','body':self.draft['issue_body']}
        with patch.object(client,'request',return_value=[row]):
            with self.assertRaises(DeliveryError):client.find('fixture-user',public_payload(self.draft),'Report ID: '+self.draft['report_id'])

    def test_sender_api_uses_existing_origin_and_token_boundary(self):
        import urllib.request,urllib.error
        from http.server import ThreadingHTTPServer
        from types import SimpleNamespace
        from repohub import Handler
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        server.hub=SimpleNamespace(state_dir=self.root/'state',diagnostics=self.logs,csrf='fixture-csrf')
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        try:
            with patch('repohub.send_report') as send:
                request=urllib.request.Request(origin+'/api/reports/send',json.dumps(self.payload).encode(),{'Content-Type':'application/json'})
                with self.assertRaises(urllib.error.HTTPError) as failure:urllib.request.urlopen(request)
                self.assertEqual(failure.exception.code,403);failure.exception.close();send.assert_not_called()
            request=urllib.request.Request(origin+'/api/reports/draft',json.dumps({'report_id':self.payload['report_id']}).encode(),{'Content-Type':'application/json','Origin':origin,'X-RepoHub-Token':'fixture-csrf'})
            with urllib.request.urlopen(request) as response:
                reopened=json.load(response)
            self.assertEqual(reopened['draft']['preview_digest'],self.draft['preview_digest'])
            self.assertEqual(reopened['draft']['form']['description'],'Controlled issue')
        finally:server.shutdown();server.server_close();thread.join()
