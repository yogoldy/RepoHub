import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer
import urllib.request
import urllib.error
from repohub import Hub, Handler, atomic_json, content_manifest, archive_manifest, workspace_id, snapshot
from status_health import ProblemTracker
from workspace_registry import WorkspaceRegistry
from diagnostic_export import export_bundle


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.home = self.base/'repos'; self.repo = self.home/'Example'
        self.repo.mkdir(parents=True); (self.repo/'work.txt').write_text('baseline')
        (self.base/'cloud').mkdir()
        self.config = {'repos_root':str(self.home),'backup_root':str(self.base/'cloud/Snapshots'),
                       'state_dir':str(self.base/'state'),'retention':'all'}
        self.hub = Hub(self.config)
    def tearDown(self): self.temp.cleanup()
    def select(self, source):
        return self.hub.save_workspaces({'source':source,'revision':self.hub.workspace_status()['revision']})
    def folder(self, relative):
        p=self.base/relative;p.mkdir(parents=True,exist_ok=True);(p/'work').write_text(relative);return p

    def test_migration_preserves_ids_archives_json_and_overrides(self):
        key=workspace_id('Example');self.hub.backup();index=copy.deepcopy(self.hub.index)
        self.hub.repo_settings[key]=copy.deepcopy(self.hub.settings)
        atomic_json(self.hub.repo_settings_path,self.hub.repo_settings)
        atomic_json(self.hub.data_path(key,'notes'),{'keep':True})
        before=self.hub.registry.path.read_bytes()
        again=Hub(self.config)
        self.assertEqual(again.index,index)
        self.assertEqual(again.repositories(),{key:self.repo})
        self.assertIn(key,again.repo_settings)
        self.assertEqual(json.loads(again.data_path(key,'notes').read_text()),{'keep':True})
        self.assertEqual(again.registry.path.read_bytes(),before)
        self.assertEqual(again.registry.path.stat().st_mode & 0o777,0o600)

    def test_same_named_manual_folders_have_independent_identity_and_complete_archives(self):
        a=self.folder('a/Project');b=self.folder('b/Project')
        (a/'.git').mkdir();(a/'.git/history').write_text('contained history')
        (a/'ignored').mkdir();(a/'ignored/cache').write_text('untracked cache')
        self.select({'mode':'manual','paths':[str(a),str(b),str(a)]})
        repos=self.hub.repositories();self.assertEqual(len(repos),2)
        self.hub.backup()
        for key,root in repos.items():
            self.assertEqual(archive_manifest(self.hub.index[key]['archive'],'Project'),content_manifest(root))
        self.assertEqual(Hub(self.config).repositories(),repos)
        self.assertEqual(self.hub.status['source_mode'],'manual')
        self.assertEqual(len(self.hub.status['workspace_sources']),2)
        no_home={k:v for k,v in self.config.items() if k!='repos_root'}
        self.assertEqual(Hub(no_home).repositories(),repos)

    def test_initial_manual_configuration_needs_no_repo_home(self):
        a=self.folder('elsewhere/Project')
        config={**self.config,'state_dir':str(self.base/'new-state'),'sources':{'mode':'manual','paths':[str(a)]}}
        config.pop('repos_root')
        self.assertEqual(list(Hub(config).repositories().values()),[a])

    def test_saved_manual_selection_is_authoritative_over_legacy_home(self):
        a=self.folder('outside/Project')
        self.select({'mode':'manual','paths':[str(a)]})
        before=self.hub.workspace_status()
        restarted=Hub({**self.config,'repos_root':self.config['backup_root']})
        self.assertEqual(restarted.workspace_status(),before)
        self.assertEqual(list(restarted.repositories().values()),[a])
        self.assertIsNone(restarted.status['repos_root'])

    def test_removing_and_readding_preserves_identity_backups_and_scoped_settings(self):
        key=workspace_id('Example');self.hub.backup();archive=self.hub.index[key]['archive']
        self.hub.repo_settings[key]=copy.deepcopy(self.hub.settings)
        atomic_json(self.hub.repo_settings_path,self.hub.repo_settings)
        atomic_json(self.hub.data_path(key,'notes'),{'retained':True})
        self.select({'mode':'manual','paths':[]})
        self.assertEqual(self.hub.repositories(),{})
        self.assertTrue(Path(archive).exists());self.assertTrue((self.repo/'work.txt').exists())
        with self.assertRaises(ValueError):self.hub.data_path(key,'notes')
        self.select({'mode':'manual','paths':[str(self.repo)]})
        self.assertEqual(list(self.hub.repositories()),[key]);self.assertEqual(self.hub.index[key]['archive'],archive)
        restarted=Hub(self.config)
        self.assertEqual(restarted.repo_settings[key],self.hub.settings)
        self.assertEqual(json.loads(restarted.data_path(key,'notes').read_text()),{'retained':True})

    def test_missing_folder_cannot_replace_archive_with_empty_backup(self):
        self.hub.backup();key=workspace_id('Example');before=copy.deepcopy(self.hub.index[key])
        self.repo.rename(self.base/'moved')
        self.hub.scan(force=True)
        self.assertIn('error',self.hub.status['repos'][0])
        self.hub.backup(keys=[key])
        self.assertEqual(self.hub.index[key],before)
        self.assertTrue(Path(before['archive']).exists())

    def test_dynamic_children_exclude_hidden_symlinks_and_keep_missing_identity(self):
        new=self.folder('repos/New');self.folder('repos/.Hidden')
        (self.home/'Linked').symlink_to(self.base/'cloud',target_is_directory=True)
        repos=self.hub.repositories();self.assertIn(new,repos.values());self.assertEqual(len(repos),2)
        self.assertEqual(repos[workspace_id('New')],new)
        key=next(k for k,v in repos.items() if v==new);new.rename(self.base/'gone')
        self.assertIn(key,self.hub.repositories())
        (self.base/'gone').rename(new);self.assertEqual(self.hub.repositories()[key],new)

    def test_deduplicated_alias_and_retargeted_source_never_change_identity(self):
        a=self.folder('outside/Project');alias=self.base/'alias';alias.symlink_to(a,target_is_directory=True)
        self.select({'mode':'manual','paths':[str(a),str(alias)]})
        self.assertEqual(len(self.hub.repositories()),1)
        a.rename(self.base/'original');a.symlink_to(self.repo,target_is_directory=True)
        self.hub.scan(force=True);self.assertIn('error',self.hub.status['repos'][0])

    def test_backup_activity_and_failures_use_workspace_ids(self):
        a=self.folder('a/Project');b=self.folder('b/Project')
        self.select({'mode':'manual','paths':[str(a),str(b)]});self.hub.backup()
        sources=self.hub.repositories();keys={path:key for key,path in sources.items()}
        previous=copy.deepcopy(self.hub.index[keys[a]])
        (a/'work').write_text('changed first');(b/'work').write_text('changed second')
        seen=[]
        def controlled_snapshot(root,*args,**kwargs):
            if root in keys:
                seen.append(self.hub.status['backup']['current_repo_id'])
                self.assertEqual(seen[-1],keys[root])
                if root==a:raise OSError('controlled fixture failure')
            return snapshot(root,*args,**kwargs)
        with patch('repohub.snapshot',side_effect=controlled_snapshot):self.hub.backup()
        self.assertEqual(set(seen),set(sources))
        self.assertEqual(self.hub.index[keys[a]],previous)
        self.assertEqual(self.hub.status['backup']['errors'][0]['repo_id'],keys[a])
        self.assertEqual(archive_manifest(self.hub.index[keys[b]]['archive'],'Project'),content_manifest(b))

    def test_duplicate_names_scope_diagnostics_and_problem_episodes(self):
        a=self.folder('a/Project');b=self.folder('b/Project')
        self.select({'mode':'manual','paths':[str(a),str(b)]});self.hub.backup()
        keys={path:key for key,path in self.hub.repositories().items()}
        status=self.hub.public_status()
        status['backup']={'running':True,'current_repo':'Project','current_repo_id':keys[a],'run_id':'fixture-run'}
        obs=self.hub.evidence.observe_status(status);facts=self.hub.evidence.snapshots[obs]
        self.assertTrue(facts[keys[a]]['copying']);self.assertFalse(facts[keys[b]]['copying'])
        self.assertEqual(facts[keys[a]]['active_run_id'],'fixture-run');self.assertIsNone(facts[keys[b]]['active_run_id'])
        status['backup']={'running':False,'errors':[{'repo':'Project','repo_id':keys[a],'error':'fixture'}]}
        obs=self.hub.evidence.observe_status(status);facts=self.hub.evidence.snapshots[obs]
        self.assertTrue(facts[keys[a]]['has_error']);self.assertFalse(facts[keys[b]]['has_error'])
        tracker=ProblemTracker();tracker.update(status,1000)
        self.assertIn('backup:'+keys[a],tracker.episodes);self.assertNotIn('backup:'+keys[b],tracker.episodes)
        status['backup']['errors'].append({'repo':'Project','repo_id':keys[b],'error':'fixture'})
        tracker.update(status,1001)
        self.assertIn('backup:'+keys[b],tracker.episodes)
        status['backup']={'running':True,'current_repo':'Project','current_repo_id':keys[a],'started_at':'fixture'}
        tracker.update(status,2000);first=tracker.episodes['copy:running']['id']
        status['backup']['current_repo_id']=keys[b];tracker.update(status,2001)
        self.assertNotEqual(tracker.episodes['copy:running']['id'],first)

    def test_invalid_overlap_missing_and_protected_sources_do_not_mutate_registry(self):
        before=self.hub.registry.path.read_bytes()
        for paths in [[str(self.home),str(self.repo)],[str(self.base/'absent')],
                      [str(self.base/'cloud')],[str(self.base/'cloud/Snapshots')],
                      [str(self.base/'state')],['relative'],[str(self.base)]]:
            with self.assertRaises(ValueError):self.select({'mode':'manual','paths':paths})
            self.assertEqual(self.hub.registry.path.read_bytes(),before)

    def test_revision_busy_and_write_failure_leave_prior_selection_intact(self):
        prior=self.hub.workspace_status()
        self.select({'mode':'manual','paths':[str(self.repo)]})
        with self.assertRaises(FileExistsError):self.hub.save_workspaces({'source':{'mode':'manual','paths':[]},'revision':prior['revision']})
        for lock in [self.hub.scan_lock,self.hub.backup_lock]:
            lock.acquire()
            try:
                with self.assertRaises(FileExistsError):self.select({'mode':'manual','paths':[]})
            finally:lock.release()
        before=self.hub.registry.path.read_bytes()
        with patch.object(self.hub.registry,'writer',side_effect=OSError('simulated disk failure')):
            with self.assertRaises(OSError):self.select({'mode':'manual','paths':[]})
        self.assertEqual(self.hub.registry.path.read_bytes(),before)
        self.assertEqual(list(self.hub.repositories().values()),[self.repo])

    def test_backup_source_selection_is_serialized_with_configuration_changes(self):
        before=self.hub.workspace_status()
        original=self.hub.repositories; attempted=[]
        def interleaved_selection():
            sources=original()
            if not attempted:
                attempted.append(True)
                with self.assertRaises(FileExistsError):
                    self.hub.save_workspaces({'source':{'mode':'manual','paths':[]},'revision':before['revision']})
            return sources
        with patch.object(self.hub,'repositories',side_effect=interleaved_selection):
            self.assertTrue(self.hub.backup())
        self.assertEqual(self.hub.workspace_status(),before)
        self.assertIn(workspace_id('Example'),self.hub.index)
        for keys in [[],['unknown']]:
            if keys:
                with self.assertRaises(ValueError):self.hub.backup(keys=keys)
            else:
                self.assertFalse(self.hub.backup(keys=keys))
            self.assertFalse(self.hub.backup_lock.locked())

    def test_invalid_saved_registry_fails_closed_without_resetting(self):
        p=self.hub.registry.path;value=json.loads(p.read_text());value['workspaces'][0]['id']='../escape';p.write_text(json.dumps(value))
        before=p.read_bytes()
        with self.assertRaises(ValueError):Hub(self.config)
        self.assertEqual(p.read_bytes(),before)

    def test_configuration_diagnostics_export_no_paths(self):
        self.select({'mode':'manual','paths':[str(self.repo)]})
        bundle=export_bundle(self.hub.diagnostics.directory,self.base/'export')
        text=(bundle/'share/events.jsonl').read_text()
        self.assertIn('workspace_configuration',text);self.assertIn('saved',text)
        self.assertNotIn(str(self.repo),text);self.assertNotIn('Example',text)

    def test_workspace_api_requires_host_origin_token_and_revision(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.hub=self.hub
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        def request(payload, token=None, source=None):
            return urllib.request.urlopen(urllib.request.Request(origin+'/api/workspaces',json.dumps(payload).encode(),
                {'Content-Type':'application/json','Origin':source or origin,'X-RepoHub-Token':token or self.hub.csrf}),timeout=5)
        try:
            with self.assertRaises(urllib.error.HTTPError) as caught:
                urllib.request.urlopen(urllib.request.Request(origin+'/api/workspaces',headers={'Host':'other.example'}))
            self.assertEqual(caught.exception.code,403);caught.exception.close()
            with urllib.request.urlopen(origin+'/api/workspaces') as r:value=json.load(r)
            payload={'source':{'mode':'manual','paths':[str(self.repo)]},'revision':value['revision']}
            for token,source in [('bad',origin),(self.hub.csrf,'https://other.example')]:
                with self.assertRaises(urllib.error.HTTPError) as caught:request(payload,token,source)
                self.assertEqual(caught.exception.code,403);caught.exception.close()
            with request(payload) as r:self.assertEqual(json.load(r)['configuration']['source']['mode'],'manual')
            with self.assertRaises(urllib.error.HTTPError) as caught:request(payload)
            self.assertEqual(caught.exception.code,409);caught.exception.close()
        finally:server.shutdown();server.server_close();thread.join()

    def test_review_is_read_only_and_requires_same_discovered_folder_list(self):
        self.hub.backup();before=self.hub.registry.path.read_bytes();index=copy.deepcopy(self.hub.index)
        source={'mode':'home','home':str(self.home)}
        payload={'source':source,'revision':self.hub.workspace_status()['revision']}
        reviewed=self.hub.preview_workspaces(payload)
        self.assertEqual(self.hub.registry.path.read_bytes(),before)
        self.assertEqual(self.hub.index,index)
        self.assertEqual([r['path'] for r in reviewed['workspaces']],[str(self.repo)])
        self.folder('repos/Added')
        with self.assertRaises(FileExistsError):self.hub.save_workspaces({**payload,'review':reviewed['review']})
        self.assertEqual(self.hub.index,index)
        latest=self.hub.workspace_status();payload['revision']=latest['revision']
        reviewed=self.hub.preview_workspaces(payload)
        saved=self.hub.save_workspaces({**payload,'review':reviewed['review']})
        self.assertEqual(len([r for r in saved['configuration']['workspaces'] if r['active']]),2)
        self.assertEqual(self.hub.index,index)

    def test_review_discloses_removal_without_erasing_data_and_rejects_invalid_token(self):
        self.hub.backup();key=workspace_id('Example');notes=self.hub.data_path(key,'notes');atomic_json(notes,{'keep':True})
        index=copy.deepcopy(self.hub.index);payload={'source':{'mode':'manual','paths':[]},'revision':self.hub.workspace_status()['revision']}
        reviewed=self.hub.preview_workspaces(payload)
        self.assertEqual(reviewed['workspaces'],[]);self.assertEqual(reviewed['removed'][0]['id'],key)
        for token in [None,'wrong','0'*64]:
            with self.assertRaises((ValueError,FileExistsError)):self.hub.save_workspaces({**payload,'review':token})
        self.hub.save_workspaces({**payload,'review':reviewed['review']})
        self.assertEqual(self.hub.index,index);self.assertTrue(self.repo.exists())
        self.assertEqual(json.loads(notes.read_text()),{'keep':True})

    def test_preview_guard_and_diagnostics_exclude_source_prose(self):
        from diagnostics import read_events
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler);server.hub=self.hub
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        origin='http://127.0.0.1:'+str(server.server_port)
        payload={'source':{'mode':'manual','paths':[str(self.repo)]},'revision':self.hub.workspace_status()['revision']}
        def post(token,site,body):
            return urllib.request.urlopen(urllib.request.Request(origin+'/api/workspaces/preview',json.dumps(body).encode(),
                {'Content-Type':'application/json','Origin':site,'X-RepoHub-Token':token}),timeout=5)
        try:
            for token,site in [('bad',origin),(self.hub.csrf,'https://other.example')]:
                with self.assertRaises(urllib.error.HTTPError) as caught:post(token,site,payload)
                self.assertEqual(caught.exception.code,403);caught.exception.close()
            with post(self.hub.csrf,origin,payload) as response:preview=json.load(response)
            self.assertEqual(preview['workspaces'][0]['id'],workspace_id('Example'))
            with self.assertRaises(urllib.error.HTTPError) as caught:post(self.hub.csrf,origin,{**payload,'revision':'stale'})
            self.assertEqual(caught.exception.code,409);caught.exception.close()
            events=[e for e in read_events(self.hub.state_dir/'diagnostics') if e['event']=='workspace_review']
            self.assertEqual([e['result'] for e in events],['complete','failed'])
            self.assertNotIn(str(self.repo),json.dumps(events));self.assertNotIn('Example',json.dumps(events))
        finally:server.shutdown();server.server_close();thread.join()

    def test_unmonitored_home_inventory_drift_rejects_review_without_registry_change(self):
        other=self.folder('other-home/One');source={'mode':'home','home':str(other.parent)}
        payload={'source':source,'revision':self.hub.workspace_status()['revision']}
        reviewed=self.hub.preview_workspaces(payload);before=self.hub.registry.path.read_bytes()
        self.folder('other-home/Two')
        with self.assertRaises(FileExistsError):self.hub.save_workspaces({**payload,'review':reviewed['review']})
        self.assertEqual(self.hub.registry.path.read_bytes(),before)
        from diagnostics import read_events
        failed=[e for e in read_events(self.hub.state_dir/'diagnostics') if e['event']=='workspace_configuration']
        self.assertEqual(failed[-1]['result'],'failed');self.assertNotIn(str(other),json.dumps(failed))
