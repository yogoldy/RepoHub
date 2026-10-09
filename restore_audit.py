#!/usr/bin/env python3
"""Controlled offline restore audit. Private inputs/results never belong in Git."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import time

SCHEMA = 1
MAX_ENTRIES = 250000
MAX_BYTES = 8 * 1024**3


class AuditError(Exception):
    pass


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda:source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def stamp(path):
    s = Path(path).lstat()
    return (s.st_dev, s.st_ino, s.st_mode, s.st_size, s.st_mtime_ns, s.st_ctime_ns)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()


def write_private(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as target:
        target.write(json.dumps(value, indent=2, sort_keys=True).encode()+b'\n')


class Evidence:
    def __init__(self, output):
        self.output = Path(output)
        if self.output.exists() or self.output.is_symlink():
            raise AuditError('output_must_be_new')
        self.output.mkdir(mode=0o700, parents=True)
        self.stage = 'initialization'
        self.started = time.monotonic()
        self.events = self.output/'events.jsonl'
        self.emit('audit_started', python=sys.version.split()[0], platform=platform.platform(),
                  verifier_sha256=digest(__file__), max_entries=MAX_ENTRIES, max_bytes=MAX_BYTES,
                  network_policy='offline_commands_only', execute_restored_code=False)

    def emit(self, event, **facts):
        record={'utc':datetime.now(timezone.utc).isoformat(), 'event':event,
                'stage':self.stage, 'elapsed_ms':round((time.monotonic()-self.started)*1000), **facts}
        fd=os.open(self.events, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd,'ab') as target:
            target.write(canonical(record)+b'\n')

    def enter(self, stage):
        self.stage=stage
        self.emit('stage_started')

    def finish(self, result, **facts):
        self.emit('audit_finished', result=result, **facts)
        write_private(self.output/'result.json', {'schema_version':SCHEMA, 'result':result, **facts})


def inventory(root):
    root=Path(root)
    result={}
    def walk(directory):
        with os.scandir(directory) as children:
            for child in sorted(children,key=lambda e:e.name):
                path=Path(child.path);s=path.lstat();relative=path.relative_to(root).as_posix()
                if not (stat.S_ISREG(s.st_mode) or stat.S_ISDIR(s.st_mode) or stat.S_ISLNK(s.st_mode)):
                    raise AuditError('unsupported_source_file_type')
                result[relative]=stamp(path)
                if stat.S_ISDIR(s.st_mode):walk(path)
    walk(root)
    return result


def manifest(root):
    root=Path(root);before=inventory(root);result={}
    for relative,s in before.items():
        path=root/relative;mode=s[2];item={'mode':stat.S_IMODE(mode)}
        if stat.S_ISREG(mode):
            fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
            with os.fdopen(fd,'rb') as source:
                first=os.fstat(source.fileno());h=hashlib.sha256()
                for block in iter(lambda:source.read(1024*1024),b''):h.update(block)
                last=os.fstat(source.fileno())
            if (first.st_ino,first.st_size,first.st_mtime_ns,first.st_ctime_ns)!=(last.st_ino,last.st_size,last.st_mtime_ns,last.st_ctime_ns):
                raise AuditError('source_changed_during_hashing')
            item.update(kind='file',size=last.st_size,sha256=h.hexdigest())
        elif stat.S_ISDIR(mode):item.update(kind='directory')
        else:item.update(kind='symlink',target=os.readlink(path))
        result[relative]=item
    if before!=inventory(root):raise AuditError('source_changed_during_capture')
    return result


def relative_path(value):
    if not isinstance(value,str) or not value or '\\' in value or '\x00' in value:
        raise AuditError('unsafe_path')
    p=PurePosixPath(value)
    if p.is_absolute() or any(v in ('','.', '..') for v in value.split('/')):
        raise AuditError('unsafe_path')
    return p


def validate_entries(entries):
    if not isinstance(entries,dict) or len(entries)>MAX_ENTRIES:raise AuditError('invalid_manifest')
    total=0
    for relative,item in entries.items():
        path=relative_path(relative)
        if not isinstance(item,dict):raise AuditError('invalid_manifest_entry')
        if type(item.get('mode')) is not int or not 0<=item['mode']<=0o777:raise AuditError('unsupported_permission_bits')
        kind=item.get('kind')
        required={'kind','mode'} | ({'size','sha256'} if kind=='file' else {'target'} if kind=='symlink' else set())
        if kind not in {'file','directory','symlink'} or set(item)!=required:raise AuditError('invalid_manifest_entry')
        for parent in path.parents:
            if str(parent)=='.':continue
            if entries.get(str(parent),{}).get('kind')!='directory':raise AuditError('missing_or_unsafe_parent')
        if kind=='file':
            if type(item['size']) is not int or item['size']<0 or not re.fullmatch('[0-9a-f]{64}',str(item['sha256'])):
                raise AuditError('invalid_manifest_file')
            total+=item['size']
        elif kind=='symlink':
            target=item['target']
            if not isinstance(target,str) or not target or '\\' in target or '\x00' in target or PurePosixPath(target).is_absolute():
                raise AuditError('external_or_invalid_symlink')
            # Preserve link text, but require its lexical target to remain inside the root.
            parts=list(path.parent.parts)
            for part in target.split('/'):
                if part=='..':
                    if not parts:raise AuditError('external_or_invalid_symlink')
                    parts.pop()
                elif part not in ('','.'):parts.append(part)
    if total>MAX_BYTES:raise AuditError('resource_limit')
    # Git files outside this root, submodules and alternates need a separate protocol.
    for relative,item in entries.items():
        if PurePosixPath(relative).name=='.git' and item['kind']!='directory':raise AuditError('external_git_layout')
        if PurePosixPath(relative).name=='.gitmodules':raise AuditError('submodules_not_in_scope')
        if '.git' in PurePosixPath(relative).parts and relative.endswith('/commondir'):raise AuditError('external_git_layout')
        if '.git' in PurePosixPath(relative).parts and (relative.endswith('/objects/info/alternates') or relative.endswith('/objects/info/http-alternates')):
            raise AuditError('git_alternates_not_in_scope')
    return total


def git_facts(root, evidence):
    if not (root/'.git').exists():return None
    if (root/'.git').is_symlink() or not (root/'.git').is_dir():raise AuditError('external_git_layout')
    executable=shutil.which('git')
    if not executable:raise AuditError('git_unavailable')
    home=evidence.output/'git-home';home.mkdir(mode=0o700,exist_ok=True)
    env={'PATH':os.defpath,'HOME':str(home),'LC_ALL':'C','GIT_CONFIG_NOSYSTEM':'1',
         'GIT_CONFIG_GLOBAL':os.devnull,'GIT_OPTIONAL_LOCKS':'0','GIT_TERMINAL_PROMPT':'0',
         'GIT_NO_REPLACE_OBJECTS':'1','GIT_NO_LAZY_FETCH':'1','GIT_EXTERNAL_DIFF':'false'}
    options=['--git-dir='+str(root/'.git'),'--work-tree='+str(root),'--no-optional-locks','-c','core.hooksPath='+os.devnull,'-c','core.fsmonitor=false',
             '-c','core.pager=cat','-c','protocol.allow=never','-c','safe.directory='+str(root)]
    def run(*args, allowed=(0,)):
        start=time.monotonic()
        completed=subprocess.run([executable,*options,'-C',str(root),*args],env=env,
                                 capture_output=True,timeout=120)
        evidence.emit('git_command', command=['git',*args], returncode=completed.returncode,
                      stdout_sha256=hashlib.sha256(completed.stdout).hexdigest(),
                      stderr_sha256=hashlib.sha256(completed.stderr).hexdigest(),
                      stdout_bytes=len(completed.stdout),stderr_bytes=len(completed.stderr),
                      duration_ms=round((time.monotonic()-start)*1000))
        if completed.returncode not in allowed:raise AuditError('git_check_failed')
        return completed
    version=subprocess.run([executable,'--version'],env=env,capture_output=True,check=True,timeout=10)
    evidence.emit('git_tool',version=version.stdout.decode().strip())
    run('fsck','--full','--strict')
    head=run('rev-parse','--verify','HEAD',allowed=(0,128))
    if head.returncode!=0 and (root/'.git/objects').is_dir():
        # Only permit an unborn HEAD; a broken committed HEAD fails fsck above.
        run('symbolic-ref','HEAD')
    return {'head':head.stdout.decode().strip() if head.returncode==0 else None,
            'head_symbolic':run('symbolic-ref','-q','HEAD',allowed=(0,1)).stdout.decode().strip() or None,
            'refs':run('for-each-ref','--format=%(refname) %(objectname)').stdout.decode().splitlines(),
            'history_count':run('rev-list','--all','--count').stdout.decode().strip()}


def capture(source, checksum, evidence):
    if not re.fullmatch('[0-9a-f]{64}',checksum):raise AuditError('invalid_expected_checksum')
    source=Path(source)
    if source.is_symlink() or not source.is_dir():raise AuditError('invalid_source_root')
    relative_path(source.name)
    evidence.enter('independent_source_capture')
    expected=manifest(source);validate_entries(expected)
    git=git_facts(source,evidence)
    if expected!=manifest(source):raise AuditError('source_changed_during_git_checks')
    baseline={'schema_version':SCHEMA,'root_name':source.name,'archive_sha256':checksum,
              'entries':expected,'git':git,'captured_at':datetime.now(timezone.utc).isoformat(),
              'provenance':'live_source_inventory_not_archive_derived'}
    write_private(evidence.output/'expected.json',baseline)
    evidence.finish('captured',manifest_sha256=digest(evidence.output/'expected.json'),entries=len(expected),
                    note='Capture alone does not prove the supplied archive matches this source point in time.')


def extract_checked(archive, baseline, destination, evidence):
    expected=baseline['entries'];root_name=baseline['root_name'];members={};root_member=None
    evidence.enter('archive_preflight')
    with tarfile.open(archive,'r:gz') as stored:
        total=0
        for member in stored:
            path=relative_path(member.name)
            if member.name==root_name:
                if root_member is not None or not member.isdir():raise AuditError('invalid_archive_root')
                root_member=member;continue
            if path.parts[0]!=root_name or len(path.parts)<2:raise AuditError('unexpected_archive_root')
            relative='/'.join(path.parts[1:])
            if relative in members or relative not in expected:raise AuditError('duplicate_or_unexpected_entry')
            item=expected[relative]
            kind='file' if member.isfile() or member.islnk() else 'directory' if member.isdir() else 'symlink' if member.issym() else 'unsupported'
            if kind!=item['kind'] or member.mode!=item['mode']:raise AuditError('entry_type_or_mode_mismatch')
            if kind=='symlink' and member.linkname!=item['target']:raise AuditError('symlink_mismatch')
            if member.islnk():
                target=relative_path(member.linkname)
                key='/'.join(target.parts[1:])
                if target.parts[0]!=root_name or key not in members or not members[key].isfile():raise AuditError('unsafe_hardlink')
                if expected[key]['size']!=item['size'] or expected[key]['sha256']!=item['sha256']:raise AuditError('hardlink_mismatch')
            elif kind=='file' and member.size!=item['size']:raise AuditError('file_size_mismatch')
            total+=item.get('size',0)
            if len(members)>=MAX_ENTRIES or total>MAX_BYTES:raise AuditError('resource_limit')
            members[relative]=member
        if root_member is None or members.keys()!=expected.keys():raise AuditError('missing_archive_entries')
        destination.mkdir(mode=0o700)
        evidence.enter('isolated_extraction')
        directories=[r for r,i in expected.items() if i['kind']=='directory']
        for relative in sorted(directories,key=lambda r:len(PurePosixPath(r).parts)):
            (destination/relative).mkdir(mode=0o700)
        for relative,member in members.items():
            if expected[relative]['kind']!='file':continue
            fd=os.open(destination/relative,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
            with os.fdopen(fd,'wb') as target,stored.extractfile(member) as source:
                shutil.copyfileobj(source,target,1024*1024)
                os.fchmod(target.fileno(),expected[relative]['mode'])
        for relative,item in expected.items():
            if item['kind']=='symlink':os.symlink(item['target'],destination/relative)
        for relative in sorted(directories,key=lambda r:len(PurePosixPath(r).parts),reverse=True):
            os.chmod(destination/relative,expected[relative]['mode'])
        evidence.emit('extraction_finished',entries=len(members),bytes=total)


def verify(archive, expected, manifest_sha256, evidence):
    archive,expected=Path(archive),Path(expected)
    for path in (archive,expected):
        if path.is_symlink() or not path.is_file():raise AuditError('missing_or_nonregular_input')
    inputs={str(p):stamp(p) for p in (archive,expected)}
    evidence.enter('input_identity')
    if expected.stat().st_size>128*1024**2 or archive.stat().st_size>MAX_BYTES:raise AuditError('resource_limit')
    actual_manifest=digest(expected);actual_archive=digest(archive)
    evidence.emit('input_hashes',archive_sha256=actual_archive,manifest_sha256=actual_manifest,
                  archive_bytes=archive.stat().st_size)
    if actual_manifest!=manifest_sha256:raise AuditError('expected_manifest_checksum_mismatch')
    baseline=json.loads(expected.read_text())
    if baseline.get('schema_version')!=SCHEMA or baseline.get('provenance')!='live_source_inventory_not_archive_derived':raise AuditError('invalid_baseline_provenance')
    relative_path(baseline['root_name'])
    if '/' in baseline['root_name']:raise AuditError('invalid_root_name')
    validate_entries(baseline['entries'])
    if actual_archive!=baseline['archive_sha256']:raise AuditError('archive_checksum_mismatch')
    destination=evidence.output/'restored';extract_checked(archive,baseline,destination,evidence)
    evidence.enter('restored_manifest_comparison')
    actual=manifest(destination)
    if actual!=baseline['entries']:
        changed=[r for r in actual.keys()|baseline['entries'].keys() if actual.get(r)!=baseline['entries'].get(r)]
        evidence.emit('manifest_mismatch',entries=len(changed),path_refs=[hashlib.sha256(r.encode()).hexdigest()[:16] for r in sorted(changed)[:8]])
        raise AuditError('restored_manifest_mismatch')
    evidence.emit('manifest_verified',entries=len(actual),manifest_content_sha256=hashlib.sha256(canonical(actual)).hexdigest())
    evidence.enter('git_history_verification')
    git=git_facts(destination,evidence)
    if git!=baseline['git']:raise AuditError('git_history_mismatch')
    if actual!=manifest(destination):raise AuditError('restored_tree_changed_during_git_check')
    evidence.enter('input_immutability')
    if any(stamp(Path(p))!=s for p,s in inputs.items()) or digest(archive)!=actual_archive or digest(expected)!=actual_manifest:
        raise AuditError('inputs_changed_during_test')
    evidence.finish('passed',archive_sha256=actual_archive,manifest_sha256=actual_manifest,
                    entries=len(actual),git_history='verified' if git is not None else 'not_applicable',
                    claim='Supplied archive restores to the supplied independent source baseline.',
                    cloud_retrieval_tested=False)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='action',required=True)
    capture_parser=sub.add_parser('capture');capture_parser.add_argument('--source',required=True)
    capture_parser.add_argument('--archive-sha256',required=True)
    capture_parser.add_argument('--out',required=True)
    verify_parser=sub.add_parser('verify');verify_parser.add_argument('--archive',required=True)
    verify_parser.add_argument('--expected',required=True);verify_parser.add_argument('--manifest-sha256',required=True)
    verify_parser.add_argument('--out',required=True)
    args=parser.parse_args(argv)
    evidence=None
    try:
        output=Path(args.out).resolve()
        checkout=Path(__file__).resolve().parent
        if output==checkout or checkout in output.parents:raise AuditError('output_inside_verifier_checkout')
        if args.action=='capture':
            source=Path(args.source).resolve()
            if output==source or source in output.parents:raise AuditError('output_inside_source')
        evidence=Evidence(args.out)
        if args.action=='capture':capture(args.source,args.archive_sha256,evidence)
        else:verify(args.archive,args.expected,args.manifest_sha256,evidence)
        return 0
    except Exception as error:
        reason=str(error) if isinstance(error,AuditError) else type(error).__name__
        if evidence:evidence.finish('failed',reason=reason)
        print('Audit failed: '+reason,file=sys.stderr)
        return 1


if __name__=='__main__':raise SystemExit(main())
