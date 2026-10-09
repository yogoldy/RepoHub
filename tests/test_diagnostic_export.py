import json
import os
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone, timedelta
from diagnostic_export import export_bundle
from diagnostics import DiagnosticLog

class ExportTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=Path(self.temp.name)
        self.logs=self.root/'logs'
        self.now=datetime.now(timezone.utc)
        self.log=DiagnosticLog(self.logs,clock=lambda:self.now.timestamp())
    def tearDown(self): self.temp.cleanup()
    def export(self,**kwargs): return export_bundle(self.logs,self.root/'exports',now=self.now,**kwargs)
    def test_private_text_nested_payloads_and_consistent_relationships(self):
        secret='/Users/Private Person/Secret Repo/strange🦄.env'
        self.log.emit('repo_checked',repo_ref=secret,source_signature='private-hash',reason='repo_files_differ',samples=[{'path_ref':secret,'category':'repo_files','change':'added','known_file':'https://user:password@example.test/key?token=secret'}])
        self.log.emit('ui_presented',repo_ref=secret,archive_ref='private-archive',verification_archive_ref='private-archive',run_id='private-run',display_label=secret,reason='observed_error',error_type='nested token password=secret')
        # An attacker-controlled legacy record cannot smuggle arbitrary nested data.
        path=next(self.logs.iterdir())
        with path.open('a') as target:
            target.write(json.dumps({'schema_version':1,'session_id':'private-session','utc':self.now.isoformat(),'event':'runtime_error','unknown':{'secret':secret},'samples':[{'path_ref':secret,'contents':secret}],'counts':{'repo_files':2,secret:3}})+'\n')
        case=self.export()
        shared=''.join(p.read_text() for p in (case/'share').iterdir())
        for text in [secret,'private-hash','private-archive','private-run','password=secret','user:password']:
            self.assertNotIn(text,shared)
        rows=[json.loads(x) for x in (case/'share/events.jsonl').read_text().splitlines()]
        self.assertNotIn('contents', rows[2]['samples'][0])
        self.assertEqual(rows[0]['repo_ref'],rows[1]['repo_ref'])
        self.assertEqual(rows[1]['archive_ref'],rows[1]['verification_archive_ref'])
        self.assertEqual(rows[0]['reason'],'repo_files_differ')
        self.assertIn(secret, [a['original'] for a in json.loads((case/'PRIVATE_ALIAS_KEY.json').read_text())['aliases']])
        self.assertEqual(os.stat(case).st_mode & 0o777,0o700)
        for p in case.rglob('*'):
            if p.is_file(): self.assertEqual(os.stat(p).st_mode & 0o777,0o600)
    def test_time_count_byte_bounds_and_incomplete_window_disclosure(self):
        self.log.clock=lambda:(self.now-timedelta(days=2)).timestamp()
        self.log.emit('heartbeat')
        self.log.clock=lambda:self.now.timestamp()
        for i in range(200): self.log.emit('repo_checked',repo_ref=str(i),reason='repo_files_differ')
        case=self.export(max_events=100,max_bytes=8192)
        schema=json.loads((case/'share/schema.json').read_text())
        self.assertEqual(schema['window']['eligible_events'],200)
        self.assertGreater(schema['window']['omitted_events'],100)
        self.assertLessEqual((case/'share/events.jsonl').stat().st_size,8192)
        self.assertEqual(schema['window']['exported_events'],len((case/'share/events.jsonl').read_text().splitlines()))
    def test_independent_report_keys_and_no_overwrite(self):
        self.log.emit('backup_started',run_id='private-run')
        a,b=self.export(),self.export()
        self.assertNotEqual(a,b)
        self.assertEqual(len(list((a/'share').iterdir())),2)
        self.assertTrue((a/'PRIVATE_ALIAS_KEY.json').exists())
    def test_symlink_output_and_invalid_limits_rejected(self):
        (self.root/'exports').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(ValueError): self.export()
        with self.assertRaises(ValueError): self.export(hours=169)
        with self.assertRaises(ValueError): self.export(max_events=0)
