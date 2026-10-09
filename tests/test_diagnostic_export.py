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

    def test_no_wall_clock_raw_sizes_hashes_or_free_text(self):
        self.log.emit('repo_checked',repo_ref='actual-name',bytes=123456789,files=777,duration_ms=1234.5,verification_checked_at=(self.now-timedelta(seconds=12)).isoformat(),error_type='email@example.test',reason='repo_files_differ',source_signature='deadbeef',percent=33.3)
        case=self.export()
        shared=''.join(p.read_text() for p in (case/'share').iterdir())
        row=json.loads((case/'share/events.jsonl').read_text().splitlines()[0])
        self.assertEqual(row['elapsed_seconds'],0)
        self.assertEqual(row['duration_seconds'],1)
        self.assertEqual(row['verification_age_seconds'],12)
        self.assertEqual(row['percent'],35)
        for field in ['utc','verification_checked_at','bytes','files','duration_ms','error_type']:
            self.assertNotIn(field,row)
        for secret in [self.now.isoformat(),'email@example.test','actual-name','deadbeef','123456789']:
            self.assertNotIn(secret,shared)
        self.assertNotIn('start',json.loads((case/'share/schema.json').read_text())['window'])
    def test_enums_are_field_specific_and_not_a_global_word_list(self):
        self.log.emit('repo_checked',mode='repo_files_differ',reason='app',state='ArchiveCreation',surface='token',display_label='a personal message',needs_backup='true',error_code=123456789)
        row=json.loads((self.export()/'share/events.jsonl').read_text().splitlines()[0])
        for field in ['mode','reason','state','surface','display_label','needs_backup','error_code']:
            self.assertNotIn(field,row)
    def test_unknown_events_and_unknown_nested_fields_fail_closed(self):
        self.log.emit('unreviewed_new_event',reason='contents_match')
        self.log.emit('repo_checked',samples=[{'path_ref':'private-file','category':'repo_files','change':'added','known_file':'private-filename'}],counts={'repo_files':90000})
        case=self.export();rows=[json.loads(line) for line in (case/'share/events.jsonl').read_text().splitlines()]
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['counts']['repo_files'],1000)
        self.assertNotIn('known_file',rows[0]['samples'][0])
        self.assertEqual(json.loads((case/'share/schema.json').read_text())['window']['unsupported_events'],1)
    def test_adversarial_types_and_huge_numbers_do_not_escape_or_crash(self):
        self.log.emit('repo_checked')
        path=next(self.logs.iterdir())
        with path.open('a') as target:
            target.write(json.dumps({'schema_version':1,'session_id':'private-session','utc':self.now.isoformat(),'event':'verification_deferred','repo_ref':123456789,'error_code':True,'percent':10**400,'duration_ms':10**400,'gap_seconds':10**400,'after_edits':'private','reason':['secret'],'counts':{'git_data':True},'samples':[{'path_ref':1234,'known_file':{'secret':'private'}}]})+'\n')
        rows=[json.loads(line) for line in (self.export()/'share/events.jsonl').read_text().splitlines()]
        for key in ['repo_ref','error_code','percent','duration_seconds','gap_seconds','after_edits','reason']:
            self.assertNotIn(key,rows[1])
        self.assertEqual(rows[1]['counts'],{})
    def test_namespaces_are_fresh_and_relative_order_preserved(self):
        self.log.emit('backup_started',run_id='private-run')
        self.log.clock=lambda:(self.now+timedelta(seconds=30)).timestamp()
        self.log.emit('backup_finished',run_id='private-run',result='complete')
        self.now+=timedelta(seconds=31)
        a,b=self.export(),self.export()
        rows_a=[json.loads(line) for line in (a/'share/events.jsonl').read_text().splitlines()]
        rows_b=[json.loads(line) for line in (b/'share/events.jsonl').read_text().splitlines()]
        self.assertEqual([r['elapsed_seconds'] for r in rows_a],[0,30])
        self.assertEqual(rows_a[0]['run_id'],rows_a[1]['run_id'])
        self.assertNotEqual(rows_a[0]['run_id'],rows_b[0]['run_id'])
