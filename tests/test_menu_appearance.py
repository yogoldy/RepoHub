"""Shared status counts, native preference boundaries and bounded diagnostic evidence."""
import copy
import json
from pathlib import Path
import platform
import subprocess
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

from change_evidence import ChangeEvidence
from diagnostics import DiagnosticLog, read_events
from diagnostic_export import export_bundle
from repohub import Hub, Handler, ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]


def fixtures():
    good = {'id': 'sample', 'name': 'Private sample', 'health': {'fresh': True},
            'needs_backup': False, 'last_backup': {'archive': '/private/current', 'sha256': 'hash'},
            'verification': {'state': 'matched', 'archive': '/private/current'},
            'cloud': {'state': 'uploaded', 'archive': '/private/current'}}
    rows = [good]
    finder = copy.deepcopy(good)
    finder['verification'].update(state='different', ignored_finder_only=True, backup_required=False)
    rows.append(finder)
    first = copy.deepcopy(good)
    first.update(needs_backup=True, last_backup=None)
    first['id'] = 'first'
    rows.append(first)
    for counts in ({'repo_files': 1, 'git_data': 0, 'finder_metadata': 0},
                   {'repo_files': 0, 'git_data': 2, 'finder_metadata': 0},
                   {'repo_files': 0, 'git_data': 0, 'finder_metadata': 1},
                   {'repo_files': 0, 'git_data': 1, 'finder_metadata': 1}, {}):
        row = copy.deepcopy(good)
        row['needs_backup'] = True
        row['verification'].update(state='different', changes={'counts': counts})
        rows.append(row)
    for state in ('checking', 'changing', 'error'):
        row = copy.deepcopy(good)
        row['verification']['state'] = state
        rows.append(row)
    for state in ('pending', 'uploading', 'unknown', 'error'):
        row = copy.deepcopy(good)
        row['cloud'].update(state=state, percent=100)
        rows.append(row)
        old = copy.deepcopy(row)
        old['cloud']['archive'] = '/private/old'
        rows.append(old)
    stale = copy.deepcopy(good)
    stale['health']['fresh'] = False
    rows.append(stale)
    result = []
    for row in rows:
        for mode in ('pending', 'edits', 'none'):
            result.append({'mode': mode, 'status': {'repos': [row], 'backup': {}}})
    for mode in ('pending', 'edits', 'none'):
        for backup in ({'running': True, 'current_repo_id': 'sample'}, {'errors': [{'error': 'synthetic'}]}):
            result.append({'mode': mode, 'status': {'repos': [good], 'backup': backup}})
        result.append({'mode': mode, 'status': {'repos': [], 'backup': {}}})
        result.append({'mode': mode, 'status': {'repos': [finder, first], 'backup': {}}})
        result.append({'mode': mode, 'status': {'repos': [good], 'data_cloud': {'state': 'error'}}})
    return result


def render(cases):
    script = """const p=require('./web/repo-status.js');
const input=JSON.parse(require('fs').readFileSync(0,'utf8'));
console.log(JSON.stringify(input.map(({status,mode})=>{
const states=(status.repos||[]).map(r=>p.present(r,status.backup));
const a=p.menuBar(status,mode), b=p.summarizeMenuBar(states,mode,status.backup,status.data_cloud);
if(JSON.stringify(a)!==JSON.stringify(b))throw Error('Native count drifted from card presentations');
return a;})));"""
    return json.loads(subprocess.check_output(['node', '-e', script], cwd=ROOT,
                      input=json.dumps(cases), text=True, timeout=15))


class MenuAppearanceTests(unittest.TestCase):
    def test_counts_consume_existing_card_statuses_including_finder_and_unknown(self):
        cases = fixtures()
        output = render(cases)
        self.assertEqual(output[0]['title'], '')
        self.assertEqual(output[3]['title'], '', 'Finder-only backed up cannot show an upload arrow')
        self.assertEqual(output[6]['count'], 1, 'First backups count as waiting')
        self.assertEqual(output[7]['count'], 0, 'First backups are not confirmed edits')
        self.assertEqual(output[9]['count'], 1)
        self.assertEqual(output[10]['count'], 1)
        self.assertEqual(output[21]['count'], 1)
        self.assertEqual(output[22]['count'], 0, 'Unclassified changes are not confirmed edits')
        for case, observed in zip(cases, output):
            self.assertEqual(observed['mode'], case['mode'])
            if case['mode'] == 'none':
                self.assertEqual(observed['count'], 0)

    def test_native_counts_have_independent_diagnostics_and_private_export(self):
        cases = fixtures()
        with tempfile.TemporaryDirectory() as temp:
            log = DiagnosticLog(Path(temp)/'logs')
            evidence = ChangeEvidence(log)
            last = None
            for case, rendered in zip(cases, render(cases)):
                observation = evidence.observe_status(case['status'])
                payload = {key: rendered[key] for key in ('mode', 'count', 'title')}
                payload.update(observation_id=observation, policy_version='status-clarity-6')
                evidence.menu_bar_presentation(payload)
                last = payload
            events = list(read_events(log.directory))
            self.assertFalse([row for row in events if row['event'] == 'menu_bar_disagreement'])
            altered = dict(last, title='')
            evidence.menu_bar_presentation(altered)
            evidence.menu_bar_presentation(dict(last, count=1))
            self.assertEqual(len([row for row in read_events(log.directory)
                                 if row['event'] == 'menu_bar_disagreement']), 2)
            altered = dict(last, count=True)
            with self.assertRaises(ValueError):
                evidence.menu_bar_presentation(altered)
            altered = dict(last, title='/private/secret')
            with self.assertRaises(ValueError):
                evidence.menu_bar_presentation(altered)
            exported = export_bundle(log.directory, Path(temp)/'exports')
            shared = (exported/'share/events.jsonl').read_text()
            self.assertIn('menu_count_mode', shared)
            self.assertNotIn('/private/', shared)
            self.assertNotIn('Private sample', shared)
            self.assertEqual(log.failed, 0)

    def test_native_readback_receipt_and_http_origin_token_guards(self):
        case = fixtures()[0]
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            source = base/'repos'
            source.mkdir()
            hub = Hub({'repos_root': str(source), 'backup_root': str(base/'backups'),
                       'state_dir': str(base/'state')})
            observation = hub.evidence.observe_status(case['status'])
            case['status']['diagnostic_observation_id'] = observation
            script = """const assert=require('node:assert/strict');
globalThis.RepoStatus=require('./web/repo-status.js');
const d=require('./web/diagnostics-client.js');
const value=JSON.parse(require('fs').readFileSync(0,'utf8'));
const observed=RepoStatus.menuBar(value.status,value.mode);
observed.title=' !'; // Model says ready; simulate an incorrect native title readback.
const fetcher=async(url,options={})=>{
if(url==='/api/session')return {ok:true,json:async()=>({token:'fixture-token'})};
assert.equal(url,'/api/diagnostics/menu-bar');
assert.equal(options.headers['X-RepoHub-Token'],'fixture-token');
console.log(options.body);return {ok:true};};
d.recordMenuBar(value.status,observed,fetcher).then(ok=>assert.equal(ok,true));"""
            output = subprocess.check_output(['node', '-e', script], cwd=ROOT,
                input=json.dumps(case), text=True, timeout=15)
            payload = json.loads(output)
            self.assertEqual(payload['title'], ' !')
            self.assertNotIn('/private/', output)
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            server.hub = hub
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            origin = f'http://127.0.0.1:{server.server_port}'
            try:
                headers = {'Origin': origin, 'X-RepoHub-Token': hub.csrf,
                           'Content-Type': 'application/json'}
                for changes in ({'X-RepoHub-Token': 'bad'}, {'Origin': 'https://outside.example'},
                                {'Host': 'outside.example'}):
                    request = urllib.request.Request(origin+'/api/diagnostics/menu-bar',
                        json.dumps(payload).encode(), {**headers, **changes})
                    with self.assertRaises(urllib.error.HTTPError) as caught:
                        urllib.request.urlopen(request)
                    self.assertEqual(caught.exception.code, 403)
                    caught.exception.close()
                request = urllib.request.Request(origin+'/api/diagnostics/menu-bar',
                    json.dumps(payload).encode(), headers)
                with urllib.request.urlopen(request) as response:
                    self.assertTrue(json.load(response)['recorded'])
                self.assertTrue([row for row in read_events(hub.diagnostics.directory)
                                 if row['event'] == 'menu_bar_disagreement'])
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_appearance_page_explicit_save_discard_conflict_and_duplicate_submit(self):
        result = subprocess.run(['node', 'tests/menu-appearance.cjs'], cwd=ROOT,
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    @unittest.skipUnless(platform.system() == 'Darwin', 'Native menu bar requires macOS')
    def test_native_bridge_persistence_and_exact_shared_javascript_execution(self):
        cases = fixtures()
        with tempfile.TemporaryDirectory() as temp:
            binary = str(Path(temp)/'native-menu-appearance')
            built = subprocess.run(['xcrun', 'swiftc', '-module-cache-path', str(Path(temp)/'cache'),
                'native/MenuAppearance.swift', 'native/MenuBridge.swift', 'tests/menu_appearance.swift',
                '-framework', 'JavaScriptCore', '-o', binary], cwd=ROOT,
                capture_output=True, text=True, timeout=120)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            result = subprocess.run([binary, str(ROOT/'web/repo-status.js')], cwd=ROOT,
                input=json.dumps(cases), capture_output=True, text=True, timeout=15)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads(result.stdout), render(cases))
