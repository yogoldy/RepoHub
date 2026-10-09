import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from backup_lifecycle import BackupLifecycle
from backup_policy import BackupScheduler, default_settings
from diagnostics import DiagnosticLog, diagnostic_ref, read_events
from repohub import Hub, workspace_id
from diagnostics_report import summarize


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.repo = self.base/'repos'/'Private repo name'
        self.repo.mkdir(parents=True)
        (self.repo/'private-file').write_text('SECRET FILE CONTENT')
        (self.base/'cloud').mkdir()
        self.hub = Hub({'repos_root':str(self.repo.parent), 'backup_root':str(self.base/'cloud/Backups'),
                        'state_dir':str(self.base/'state'), 'retention':'latest', 'require_upload_before_prune':True})
        self.key = workspace_id(self.repo.name)

    def tearDown(self):
        self.temp.cleanup()

    def events(self, kind=None):
        events = list(read_events(self.hub.diagnostics.directory))
        return [e for e in events if kind is None or e['event']==kind]

    def test_creation_reuse_and_render_reason_share_archive_run_identity(self):
        self.hub.backup()
        current = self.hub.index[self.key]
        events = [e for e in self.events() if e.get('repo_ref')==diagnostic_ref(self.key)]
        stages = [e['stage'] for e in events if e['event']=='archive_stage']
        self.assertEqual(stages, ['source_hashing','archive_creation','archive_verification','archive_transfer',
                                  'destination_verification','index_publication','retention'])
        finished = next(e for e in events if e['event']=='repo_backup_finished')
        self.assertEqual(finished['run_id'],current['run_id'])
        self.assertEqual(finished['archive_ref'],diagnostic_ref(current['archive']))
        self.hub.backup()
        self.assertEqual(current,self.hub.index[self.key])
        reused = self.events('archive_reused')[-2] # saved app data is last
        self.assertEqual(reused['archive_ref'],finished['archive_ref'])
        raw={key:{'ubiquitous':True,'uploaded':True} for key in self.hub.index}
        with patch('repohub.subprocess.run',return_value=type('Result',(),{'stdout':json.dumps(raw)})()):
            self.hub.refresh_cloud()
        status = self.hub.public_status()
        observation = status['diagnostic_observation_id']
        self.hub.evidence.presentation({'surface':'menu','native':True,'client_id':'a'*24,
            'observation_id':observation,'policy_version':'change-evidence-2',
            'rows':[{'repo_id':self.key,'phase':'ready','display_label':'Backed up','ready':True}]})
        receipt = self.events('ui_presented')[-1]
        self.assertEqual(receipt['reason'],'fresh_hashes_and_upload_confirmed')
        self.assertEqual(receipt['run_id'],current['run_id'])
        report=summarize(self.events())
        self.assertTrue(report['recent_lifecycle'])
        self.assertEqual(report['repos'][diagnostic_ref(self.key)]['views']['menu_native']['backend']['run_id'],current['run_id'])

    def test_failure_recovery_privacy_and_logging_failure_do_not_stop_backups(self):
        with patch('repohub.snapshot',side_effect=OSError('SECRET ERROR /private/location')):
            self.hub.backup()
        self.assertEqual(self.events('backup_finished')[-1]['result'],'failed')
        self.assertEqual(self.events('repo_backup_failed')[0]['error_type'],'OSError')
        self.hub.backup()
        self.assertEqual(self.events('backup_finished')[-1]['result'],'complete')
        Path(self.hub.index[self.key]['archive']).write_bytes(b'corrupt')
        self.hub.backup()
        self.assertTrue(self.events('archive_repair_needed'))
        raw=json.dumps(self.events())
        for secret in ('SECRET FILE CONTENT','SECRET ERROR',str(self.base),self.repo.name,'private-file'):
            self.assertNotIn(secret,raw)
        (self.repo/'private-file').write_text('new')
        with patch.object(self.hub.diagnostics,'emit',return_value=False):
            self.hub.backup()
        self.assertTrue(Path(self.hub.index[self.key]['archive']).is_file())

    def test_upload_error_recovery_stale_and_gated_pruning(self):
        self.hub.backup();old=self.hub.index[self.key]['archive']
        (self.repo/'private-file').write_text('new')
        self.hub.backup();current=self.hub.index[self.key]
        self.assertTrue(Path(old).exists())
        self.assertIn('awaiting_upload',[e.get('reason') for e in self.events('retention_decision')])
        def poll(item):
            raw={key:item for key in self.hub.index}
            with patch('repohub.subprocess.run',return_value=type('Result',(),{'stdout':json.dumps(raw)})()):
                self.hub.refresh_cloud()
        poll({'ubiquitous':True,'error':'PRIVATE CLOUD ERROR','error_code':4355,'error_domain':'NSCocoaErrorDomain'})
        self.assertTrue(Path(old).exists())
        poll({'ubiquitous':True,'uploaded':True})
        states=[e['state'] for e in self.events('upload_observed') if e['repo_ref']==diagnostic_ref(self.key)]
        self.assertEqual(states,['error','uploaded'])
        self.assertFalse(Path(old).exists())
        removed=next(e for e in self.events('prune_finished') if e['repo_ref']==diagnostic_ref(self.key))
        self.assertEqual(removed['archive_ref'],diagnostic_ref(current['archive']))
        self.assertEqual(removed['previous_archive_ref'],diagnostic_ref(old))
        self.hub.cloud_states[self.key]['checked_at']='2000-01-01T00:00:00Z'
        self.assertEqual(self.hub.cloud_for(self.key,current)['state'],'unknown')
        self.assertTrue(self.events('upload_stale'))
        self.assertNotIn('PRIVATE CLOUD ERROR',json.dumps(self.events()))

    def test_schedule_explains_quiet_period_retry_and_power_pause(self):
        scheduler=BackupScheduler(0);settings=default_settings()
        settings['battery'].update(frequency_minutes=0,after_edits=True,edit_delay_minutes=2)
        rows=[{'id':self.key,'needs_backup':True,'signature':'a'}]
        scheduler.observe(rows,0)
        lifecycle=self.hub.lifecycle
        for now in (30,121):
            plan=scheduler.plan(settings,'battery',rows,now)
            lifecycle.schedule(scheduler,settings,'battery',rows,now,{},plan)
        scheduler.attempts[self.key]=121
        lifecycle.schedule(scheduler,settings,'battery',rows,122,{},None)
        lifecycle.schedule(scheduler,settings,'unknown',rows,123,{},None)
        reasons=[e['reason'] for e in self.events('schedule_decision')]
        self.assertEqual(reasons,['edits_not_settled','edits_settled','retry_delay','power_unknown'])
        with patch('repohub.power_source',return_value='adapter'):
            self.assertFalse(self.hub.backup(expected_power='battery'))
        self.assertEqual(self.events('backup_deferred')[-1]['reason'],'power_changed')
        with patch('repohub.power_source',side_effect=['battery','adapter']):
            self.hub.backup(expected_power='battery')
        self.assertEqual(self.events('backup_finished')[-1]['result'],'power_paused')

    def test_transition_dedup_and_heartbeat(self):
        clock=[0]
        lifecycle=BackupLifecycle(self.hub.diagnostics,clock=lambda:clock[0])
        for instant in (0,5,59,60):
            clock[0]=instant
            lifecycle.transition('upload_observed',key=self.key,state='pending')
        lifecycle.transition('upload_observed',key=self.key,state='uploaded')
        self.assertEqual([e['state'] for e in self.events('upload_observed')],['pending','pending','uploaded'])

    def test_green_icon_with_missing_upload_is_logged_as_input_disagreement(self):
        self.hub.backup()
        status=self.hub.public_status()
        self.hub.evidence.presentation({'surface':'app','native':False,'client_id':'b'*24,
            'observation_id':status['diagnostic_observation_id'],'policy_version':'change-evidence-2',
            'rows':[{'repo_id':self.key,'phase':'ready','display_label':'Backed up','ready':True}]})
        self.assertEqual(self.events('ui_presented')[-1]['reason'],'presentation_inputs_disagree')
        self.assertTrue(self.events('presentation_input_disagreement'))

    def test_automatic_selection_and_archive_creation_share_run(self):
        self.hub.last_periodic_at=0
        with patch('repohub.power_source',return_value='adapter'):
            self.hub.automatic_tick()
        decision=next(e for e in self.events('schedule_decision') if e['result']=='selected')
        created=next(e for e in self.events('repo_backup_finished') if e['repo_ref']==decision['repo_ref'])
        self.assertEqual(decision['run_id'],created['run_id'])

    def test_restart_discloses_incomplete_run_without_claiming_recovery(self):
        self.hub.status['backup']={'running':True,'run_id':'c'*24}
        self.hub.persist_status()
        restarted=Hub(self.hub.config)
        self.assertEqual(self.events('backup_interrupted')[-1]['result'],'unobserved_completion')
        restarted.backup()
        self.assertEqual(self.events('backup_started')[-1]['previous_run_id'],'c'*24)
