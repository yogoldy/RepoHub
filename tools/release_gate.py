#!/usr/bin/env python3
"""Run RepoHub's domain regression contract; never operate on installed app/data."""
import argparse
import contextlib
import ast
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
REGISTER = ROOT / 'docs/quality/golden-rules.json'


def validate_register(value):
    if not isinstance(value, dict) or type(value.get('schema_version')) is not int or value.get('schema_version') != 1:
        raise ValueError('Unsupported golden-rule register')
    rules = value.get('rules')
    if not isinstance(rules, list) or not rules:
        raise ValueError('Empty golden-rule register')
    seen = set()
    for rule in rules:
        if not isinstance(rule, dict) or not re.fullmatch(r'GR\d{2}', rule.get('id', '')) or rule['id'] in seen:
            raise ValueError('Invalid or duplicate golden-rule ID')
        seen.add(rule['id'])
        if not isinstance(rule.get('test_ids'), list) or not rule['test_ids']:
            raise ValueError('Every rule needs executable regressions')
        if any(not isinstance(t, str) or not re.fullmatch(r'test_\w+\.\w+\.test_\w+', t) for t in rule['test_ids']):
            raise ValueError('Invalid regression test ID')
        for field in ['title', 'breakpoint', 'cause_and_solution', 'required_behavior', 'remaining_gap']:
            if not isinstance(rule.get(field), str) or not rule[field].strip():
                raise ValueError('Incomplete failure-mode evidence')
        if not isinstance(rule.get('diagnostic_events'), list) or not rule['diagnostic_events']:
            raise ValueError('Missing diagnostic trail')
        from diagnostic_export import EVENTS
        if any(not isinstance(event,str) or event not in EVENTS for event in rule['diagnostic_events']):
            raise ValueError('Diagnostic trail uses unregistered events')
    return rules


def assess_rules(rules, outcomes):
    return [{'id':rule['id'], 'title':rule['title'],
             'result':'passed' if all(outcomes.get(t) == 'passed' for t in rule['test_ids']) else 'failed',
             'tests':{t:outcomes.get(t, 'not_executed') for t in rule['test_ids']},
             'remaining_gap':rule['remaining_gap']} for rule in rules]


def packaging_contract(root):
    tree = ast.parse((root / 'install.py').read_text())
    groups = [n.iter for n in ast.walk(tree) if isinstance(n, ast.For) and isinstance(n.target, ast.Name)
              and n.target.id == 'name' and isinstance(n.iter, (ast.Tuple, ast.List))]
    groups = [ast.literal_eval(g) for g in groups]
    packaged = next((set(g) for g in groups if 'repohub.py' in g), set())
    if not packaged:
        raise ValueError('Missing runtime package declaration')
    for name in packaged:
        path = root / name
        if not path.is_file():
            raise ValueError('Packaged module missing: ' + name)
        for node in ast.walk(ast.parse(path.read_text())):
            modules = ([node.module] if isinstance(node, ast.ImportFrom) else
                       [alias.name for alias in node.names] if isinstance(node, ast.Import) else [])
            for module in modules:
                candidate = (module or '').split('.')[0] + '.py'
                if (root / candidate).is_file() and candidate not in packaged:
                    raise ValueError('Unpackaged runtime dependency: ' + candidate)
    route_groups = [n for n in ast.walk(ast.parse((root/'repohub.py').read_text())) if isinstance(n,ast.Assign)
                    and any(isinstance(t,ast.Name) and t.id=='routes' for t in n.targets)]
    routes = ast.literal_eval(route_groups[0].value)
    for route, name in routes.items():
        if not (root/'web'/name).is_file():
            raise ValueError('Missing served web asset: ' + route)
    for html in (root/'web').glob('*.html'):
        for asset in re.findall(r'(?:src|href)=["\'](/[^"\']+)["\']',html.read_text()):
            if asset not in routes:
                raise ValueError('Unserved HTML dependency: ' + asset)
    return {'runtime_modules':len(packaged), 'web_routes':len(routes)}


def source_fingerprint(root):
    files = set(root.glob('*.py')) | {root/'AGENTS.md'}
    for folder in ['native', 'web', 'tests', 'tools', 'docs/quality', '.github/workflows']:
        files.update(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix in {'.py','.js','.cjs','.html','.css','.swift','.json','.md','.yml'})
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(str(path.relative_to(root)).encode())
        digest.update(b'\0')
        digest.update(hashlib.sha256(path.read_bytes()).digest())
    return digest.hexdigest()


class RecordedResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.outcomes = {}
    def addSuccess(self, test):
        super().addSuccess(test); self.outcomes[test.id()] = 'passed'
    def addFailure(self, test, err):
        super().addFailure(test, err); self.outcomes[test.id()] = 'failed'
    def addError(self, test, err):
        super().addError(test, err); self.outcomes[test.id()] = 'error'
    def addSkip(self, test, reason):
        super().addSkip(test, reason); self.outcomes[test.id()] = 'skipped'
    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err); self.outcomes[test.id()] = 'expected_failure'
    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test); self.outcomes[test.id()] = 'unexpected_success'
    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            self.outcomes[test.id()] = 'failed'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', help='New private JSON receipt path; never overwrite a prior receipt')
    parser.add_argument('--require-clean', action='store_true', help='Reject a dirty checkout before accepting release evidence')
    parser.add_argument('--profile', choices=['macos','portable'], default='macos')
    args = parser.parse_args()
    os.umask(0o077)
    evidence = Path(tempfile.mkdtemp(prefix='repohub-golden-'))
    output = Path(args.output) if args.output else evidence/'result.json'
    if output.exists() or output.is_symlink():
        raise SystemExit('Receipt path must be new')
    started = time.monotonic()
    source = source_fingerprint(ROOT)
    report = {'schema_version':1, 'profile':args.profile, 'result':'running', 'source_digest':source,
              'commands':[], 'manual_release_approval':False,
              'scope':'Synthetic regression and build evidence. Does not test real iCloud delivery, deployed UI, power hardware or installed runtime.',
              'manual_checks':['Installed runtime hashes/build identity and settings preservation',
                               'Changed UI rendered state and diagnostic receipts',
                               'Two-device iCloud receive/restore when backup or restore policy changes',
                               'Live fault/power/login checks relevant to the changed boundary']}
    try:
        report['source_commit'] = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
        report['dirty_source'] = bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True))
        if args.require_clean and report['dirty_source']:
            raise ValueError('Release evidence requires a clean source checkout')
        rules = validate_register(json.loads(REGISTER.read_text()))
        report['packaging'] = packaging_contract(ROOT)
        suite = unittest.defaultTestLoader.discover(str(ROOT/'tests'),pattern='test_*.py')
        with (evidence/'python-tests.log').open('w') as log, contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
            result = unittest.TextTestRunner(stream=log,verbosity=2,resultclass=RecordedResult).run(suite)
        report['python'] = {'tests_run':result.testsRun, 'skipped':len(result.skipped), 'successful':result.wasSuccessful(),
                            'outcomes':result.outcomes, 'log':str(evidence/'python-tests.log')}
        report['rules'] = assess_rules(rules,result.outcomes)
        good = result.wasSuccessful() and not result.skipped and not result.expectedFailures and all(r['result']=='passed' for r in report['rules'])
        def command(label, argv):
            nonlocal good
            log = evidence/(label+'.log')
            with log.open('w') as target:
                try:
                    process = subprocess.run(argv,cwd=ROOT,stdout=target,stderr=subprocess.STDOUT,timeout=180)
                    code = process.returncode
                except (OSError,subprocess.TimeoutExpired):
                    code = -1
            report['commands'].append({'check':label,'result':'passed' if code==0 else 'failed','returncode':code,'log':str(log)})
            good = good and code == 0
        node = shutil.which('node') or 'node'
        for file in sorted((ROOT/'web').glob('*.js')):
            command('syntax-'+file.stem,[node,'--check',str(file)])
        for file in ['menu-status.cjs','diagnostics-client.cjs','workspace-setup.cjs']:
            command(file.split('.')[0],[node,str(ROOT/'tests'/file)])
        if args.profile=='macos':
            if platform.system()!='Darwin':
                raise ValueError('macOS profile requires macOS; native checks may not be silently skipped')
            swift=['/usr/bin/xcrun','swiftc','-module-cache-path',str(evidence/'swift-cache'),'-target',platform.machine()+'-apple-macos13.0']
            command('native-app-build',swift+[str(ROOT/'native'/name) for name in ['RepoHub.swift','BackupReadiness.swift','ProblemAlerts.swift','MenuBridge.swift','GitHubConnection.swift']]+['-o',str(evidence/'RepoHub'),'-framework','AppKit','-framework','WebKit','-framework','UserNotifications'])
            command('cloud-helper-build',swift+[str(ROOT/'native/CloudStatus.swift'),'-o',str(evidence/'cloud-status')])
            command('readiness-build',swift+[str(ROOT/'native/BackupReadiness.swift'),str(ROOT/'native/ProblemAlerts.swift'),str(ROOT/'tests/readiness.swift'),'-o',str(evidence/'readiness')])
            command('readiness-checks',[str(evidence/'readiness')])
            command('bridge-build',swift+[str(ROOT/'native/MenuBridge.swift'),str(ROOT/'tests/menu_bridge_checks.swift'),'-o',str(evidence/'bridge')])
            command('bridge-checks',[str(evidence/'bridge')])
        report['source_unchanged'] = source_fingerprint(ROOT)==source
        good = good and report['source_unchanged']
        report['result'] = ('passed' if args.profile=='macos' else 'partial') if good else 'failed'
    except (OSError,ValueError,IndexError,subprocess.SubprocessError) as error:
        report['result']='failed'
        report['gate_error']=type(error).__name__+': '+str(error)
    report['duration_seconds'] = round(time.monotonic()-started,3)
    output.parent.mkdir(parents=True,exist_ok=True)
    fd = os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'w') as target:json.dump(report,target,indent=2)
    print(json.dumps({'result':report['result'],'profile':args.profile,'receipt':str(output),'python_tests':report.get('python',{}).get('tests_run'),'manual_checks_pending':True},indent=2))
    return 1 if report['result']=='failed' else 0

if __name__=='__main__':
    sys.exit(main())
