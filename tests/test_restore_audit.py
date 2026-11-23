import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from repohub import snapshot
import restore_audit as audit


class RestoreAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.base=Path(self.temp.name)
        self.root=self.base/'Sample';self.root.mkdir()
        (self.root/'script.sh').write_text('DO NOT EXECUTE');os.chmod(self.root/'script.sh',0o755)
        (self.root/'.env').write_text('PRIVATE FIXTURE SECRET')
        (self.root/'ignored').mkdir();(self.root/'ignored/data').write_text('ignored bytes')
        (self.root/'link').symlink_to('script.sh')
        subprocess.run(['git','init','-q',str(self.root)],check=True,capture_output=True)
        # Keep this controlled fixture idle: recent Git can start maintenance
        # after commit and remove its lock while snapshot inventories entries.
        for key in ['maintenance.auto', 'gc.auto']:
            subprocess.run(['git','-C',str(self.root),'config',key,'0'],check=True)
        (self.root/'.gitignore').write_text('.env\nignored/\n')
        subprocess.run(['git','-C',str(self.root),'add','.'],check=True)
        subprocess.run(['git','-C',str(self.root),'-c','user.name=Fixture','-c','user.email=fixture@example.invalid',
                        'commit','-qm','fixture'],check=True)
        (self.root/'uncommitted.txt').write_text('uncommitted')
        self.archive=Path(snapshot(self.root,self.base/'archives',self.base/'stage')['archive'])
        self.capture=self.base/'capture'
        self.assertEqual(audit.main(['capture','--source',str(self.root),'--archive-sha256',audit.digest(self.archive),
                                     '--out',str(self.capture)]),0)
        self.expected=self.capture/'expected.json'

    def tearDown(self):self.temp.cleanup()

    def verify(self, output='verify', checksum=None):
        return audit.main(['verify','--archive',str(self.archive),'--expected',str(self.expected),
                           '--manifest-sha256',checksum or audit.digest(self.expected),'--out',str(self.base/output)])

    def result(self, output='verify'):return json.loads((self.base/output/'result.json').read_text())

    def test_full_restore_with_ignored_uncommitted_git_and_log_receipts(self):
        before=(audit.digest(self.archive),audit.digest(self.expected))
        self.assertEqual(self.verify(),0);result=self.result()
        self.assertEqual(result['result'],'passed');self.assertEqual(result['git_history'],'verified')
        self.assertFalse(result['cloud_retrieval_tested'])
        restored=self.base/'verify/restored'
        self.assertEqual(audit.manifest(restored),audit.manifest(self.root))
        self.assertEqual((restored/'.env').read_text(),'PRIVATE FIXTURE SECRET')
        self.assertEqual((audit.digest(self.archive),audit.digest(self.expected)),before)
        logs=(self.base/'verify/events.jsonl').read_text()
        self.assertNotIn('PRIVATE FIXTURE SECRET',logs);self.assertNotIn(str(self.base),logs)
        self.assertTrue(all(json.loads(line).get('stage') for line in logs.splitlines()))
        self.assertEqual((self.base/'verify/events.jsonl').stat().st_mode&0o777,0o600)

    @unittest.skipUnless(hasattr(os, 'lchmod') or os.chmod in os.supports_follow_symlinks,
                         'Platform cannot set symlink permissions')
    def test_symlink_mode_survives_different_receiver_umask_without_changing_target(self):
        os.chmod(self.root/'link', 0o700, follow_symlinks=False)
        self.archive=Path(snapshot(self.root,self.base/'mode-archives',self.base/'mode-stage')['archive'])
        cap=self.base/'mode-capture'
        self.assertEqual(audit.main(['capture','--source',str(self.root),'--archive-sha256',audit.digest(self.archive),
                                    '--out',str(cap)]),0)
        self.expected=cap/'expected.json'
        previous=os.umask(0o022)
        try:
            self.assertEqual(self.verify('mode-verify'),0)
        finally:
            os.umask(previous)
        restored=self.base/'mode-verify/restored'
        self.assertEqual(restored.joinpath('link').lstat().st_mode & 0o777,0o700)
        self.assertEqual(restored.joinpath('script.sh').stat().st_mode & 0o777,0o755)
        self.assertEqual(audit.manifest(restored),audit.manifest(self.root))

    def snapshot_capture(self, name):
        archive=Path(snapshot(self.root,self.base/(name+'-archives'),self.base/(name+'-stage'))['archive'])
        out=self.base/(name+'-capture')
        code=audit.main(['capture','--source',str(self.root),'--archive-sha256',audit.digest(archive),'--out',str(out)])
        return code,archive,out

    def test_finder_files_in_git_refs_are_tolerated_but_other_fsck_errors_fail(self):
        # Finder writes these into folders it shows; strict fsck calls them bad refs.
        (self.root/'.git/refs/.DS_Store').write_bytes(b'\x00\x00\x00\x01Bud1\x00Finder view')
        (self.root/'.git/refs/heads/._main').write_bytes(b'\x00\x05\x16\x07AppleDouble')
        code,archive,out=self.snapshot_capture('finder')
        self.assertEqual(code,0)
        self.archive,self.expected=archive,out/'expected.json'
        self.assertEqual(self.verify('finder-verify'),0)
        self.assertEqual(self.result('finder-verify')['git_history'],'verified')
        restored=self.base/'finder-verify/restored'
        self.assertEqual((restored/'.git/refs/.DS_Store').read_bytes(),(self.root/'.git/refs/.DS_Store').read_bytes())
        self.assertIn('finder_refs_ignored',(self.base/'finder-verify/events.jsonl').read_text())
        # A malformed ref that is not a Finder file still fails, even beside Finder files.
        (self.root/'.git/refs/notes-backup').write_text('not a ref')
        code,_,out=self.snapshot_capture('other-ref')
        self.assertEqual(code,1)
        self.assertEqual(json.loads((out/'result.json').read_text())['reason'],'git_check_failed')
        (self.root/'.git/refs/notes-backup').unlink()
        # Object damage always fails, whatever Finder files are present.
        loose=next(p for p in (self.root/'.git/objects').glob('[0-9a-f][0-9a-f]/*') if p.is_file())
        os.chmod(loose,0o644);loose.write_bytes(b'corrupt object')
        code,_,out=self.snapshot_capture('corrupt')
        self.assertEqual(code,1)
        self.assertEqual(json.loads((out/'result.json').read_text())['reason'],'git_check_failed')

    def test_empty_nested_git_marker_restores_but_pointer_files_still_fail(self):
        # Package caches such as uv leave an empty .git marker; the app backs it up as a file.
        cache=self.root/'ignored/cache';cache.mkdir()
        (cache/'.git').write_bytes(b'')
        code,archive,out=self.snapshot_capture('marker')
        self.assertEqual(code,0)
        self.archive,self.expected=archive,out/'expected.json'
        self.assertEqual(self.verify('marker-verify'),0)
        self.assertEqual(self.result('marker-verify')['git_history'],'verified')
        marker=self.base/'marker-verify/restored/ignored/cache/.git'
        self.assertTrue(marker.is_file());self.assertEqual(marker.stat().st_size,0)
        # A baseline claiming a non-empty nested .git file is refused before extraction.
        baseline=json.loads(self.expected.read_text())
        baseline['entries']['ignored/cache/.git']['size']=5
        self.expected.write_text(json.dumps(baseline))
        self.assertEqual(self.verify('marker-tampered'),1)
        self.assertEqual(self.result('marker-tampered')['reason'],'external_git_layout')
        self.assertFalse((self.base/'marker-tampered/restored').exists())
        # A nested pointer file still means Git data stored elsewhere.
        (cache/'.git').write_text('gitdir: /elsewhere/.git\n')
        code,_,out=self.snapshot_capture('pointer')
        self.assertEqual(code,1)
        self.assertEqual(json.loads((out/'result.json').read_text())['reason'],'external_git_layout')

    def test_corrupt_archive_and_wrong_manifest_identity_fail_before_extraction(self):
        self.archive.write_bytes(b'corrupt')
        self.assertEqual(self.verify(),1)
        self.assertEqual(self.result()['reason'],'archive_checksum_mismatch')
        self.assertFalse((self.base/'verify/restored').exists())
        self.assertEqual(self.verify('wrong',checksum='0'*64),1)
        self.assertEqual(self.result('wrong')['reason'],'expected_manifest_checksum_mismatch')

    def rewrite_archive(self, extra):
        with tarfile.open(self.archive,'r:gz') as old:
            members=[(m,old.extractfile(m).read() if m.isfile() else None) for m in old]
        with tarfile.open(self.archive,'w:gz') as new:
            for m,body in members:new.addfile(m,io.BytesIO(body) if body is not None else None)
            for m,body in extra:new.addfile(m,io.BytesIO(body) if body is not None else None)
        expected=json.loads(self.expected.read_text());expected['archive_sha256']=audit.digest(self.archive)
        self.expected.write_text(json.dumps(expected))

    def test_traversal_duplicate_extra_and_absolute_paths_are_rejected(self):
        original=self.archive.read_bytes();baseline=self.expected.read_bytes()
        for i,name in enumerate(('Sample/../../escape','/absolute','Sample/script.sh','Sample/extra')):
            self.archive.write_bytes(original);self.expected.write_bytes(baseline)
            member=tarfile.TarInfo(name);member.size=1
            self.rewrite_archive([(member,b'x')])
            self.assertEqual(self.verify(str(i)),1)
            self.assertFalse((self.base/str(i)/'restored').exists())
        self.assertFalse((self.base/'escape').exists())

    def test_outside_link_is_reported_but_git_alternates_fail_capture(self):
        (self.root/'link').unlink();(self.root/'link').symlink_to('/private/outside')
        self.assertEqual(audit.main(['capture','--source',str(self.root),'--archive-sha256',audit.digest(self.archive),
                                    '--out',str(self.base/'external')]),0)
        report=json.loads((self.base/'external/expected.json').read_text())['outside_links']
        self.assertEqual([(item['path'],item['scope']) for item in report],[('link','absolute')])
        (self.root/'link').unlink();(self.root/'.git/objects/info/alternates').write_text('/private/objects')
        self.assertEqual(audit.main(['capture','--source',str(self.root),'--archive-sha256',audit.digest(self.archive),
                                    '--out',str(self.base/'alternates')]),1)

    def test_full_content_difference_and_git_failure_are_not_passes(self):
        expected=json.loads(self.expected.read_text());expected['entries']['uncommitted.txt']['sha256']='0'*64
        self.expected.write_text(json.dumps(expected))
        self.assertEqual(self.verify(),1)
        self.assertEqual(self.result()['reason'],'restored_manifest_mismatch')
        # A valid byte restore must still fail when Git validation fails.
        expected['entries']['uncommitted.txt']['sha256']=hashlib.sha256(b'uncommitted').hexdigest()
        self.expected.write_text(json.dumps(expected))
        with patch.object(audit,'git_facts',side_effect=audit.AuditError('git_check_failed')):
            self.assertEqual(self.verify('git-failure'),1)
        self.assertEqual(self.result('git-failure')['reason'],'git_check_failed')

    def test_existing_output_is_not_overwritten_and_capture_cannot_write_to_source(self):
        output=self.base/'verify';output.mkdir();(output/'keep').write_text('keep')
        self.assertEqual(self.verify(),1);self.assertEqual((output/'keep').read_text(),'keep')
        inside=self.root/'capture'
        self.assertEqual(audit.main(['capture','--source',str(self.root),'--archive-sha256',audit.digest(self.archive),
                                    '--out',str(inside)]),1)
        self.assertFalse(inside.exists())

    def test_input_mutation_during_restore_is_reported(self):
        original=audit.git_facts
        def changing(root,evidence):
            value=original(root,evidence)
            self.expected.write_bytes(self.expected.read_bytes()+b'\n')
            return value
        with patch.object(audit,'git_facts',side_effect=changing):self.assertEqual(self.verify(),1)
        self.assertEqual(self.result()['reason'],'inputs_changed_during_test')

    def test_missing_input_logs_failure_and_non_git_source_is_disclosed(self):
        self.archive.unlink();self.assertEqual(self.verify(),1)
        self.assertEqual(self.result()['reason'],'missing_or_nonregular_input')
        plain=self.base/'plain';plain.mkdir();(plain/'data').write_text('plain')
        archive=Path(snapshot(plain,self.base/'plain-archives',self.base/'plain-stage')['archive'])
        cap=self.base/'plain-capture'
        self.assertEqual(audit.main(['capture','--source',str(plain),'--archive-sha256',audit.digest(archive),'--out',str(cap)]),0)
        self.assertEqual(audit.main(['verify','--archive',str(archive),'--expected',str(cap/'expected.json'),
                                     '--manifest-sha256',audit.digest(cap/'expected.json'),'--out',str(self.base/'plain-verify')]),0)
        self.assertEqual(self.result('plain-verify')['git_history'],'not_applicable')

    def test_restored_hooks_and_fsmonitor_are_not_executed(self):
        marker=self.base/'unexpected-execution'
        hook=self.root/'.git/hooks/post-checkout'
        hook.write_text('#!/bin/sh\ntouch "'+str(marker)+'"\n');os.chmod(hook,0o755)
        monitor=self.root/'monitor.sh'
        monitor.write_text('#!/bin/sh\ntouch "'+str(marker)+'"\n');os.chmod(monitor,0o755)
        subprocess.run(['git','-C',str(self.root),'config','core.fsmonitor',str(monitor)],check=True)
        self.archive=Path(snapshot(self.root,self.base/'new-archives',self.base/'new-stage')['archive'])
        out=self.base/'hook-capture'
        self.assertEqual(audit.main(['capture','--source',str(self.root),'--archive-sha256',audit.digest(self.archive),
                                    '--out',str(out)]),0)
        self.expected=out/'expected.json'
        self.assertEqual(self.verify(),0)
        self.assertFalse(marker.exists())

    def test_relative_output_and_source_paths_still_verify_git(self):
        # Git gets both --git-dir and -C; a relative root used to be applied twice,
        # so Git reported "not a git repository" and a good restore failed.
        previous=os.getcwd()
        try:
            os.chdir(self.base)
            self.assertEqual(audit.main(['capture','--source','Sample','--archive-sha256',audit.digest(self.archive),
                                         '--out','relative-capture']),0)
            expected=Path('relative-capture/expected.json')
            self.assertEqual(audit.main(['verify','--archive',str(self.archive),'--expected',str(expected),
                                         '--manifest-sha256',audit.digest(expected),'--out','relative-verify']),0)
        finally:
            os.chdir(previous)
        self.assertEqual(self.result('relative-verify')['git_history'],'verified')

    def test_gitmodules_inside_a_dependency_restores_but_top_level_submodules_fail(self):
        # Some npm packages ship a .gitmodules file; inside node_modules it is just data.
        package=self.root/'ignored/node_modules/sanitize-filename';package.mkdir(parents=True)
        (package/'.gitmodules').write_text('[submodule "vendor"]\n\tpath = vendor\n')
        code,archive,out=self.snapshot_capture('package')
        self.assertEqual(code,0)
        self.archive,self.expected=archive,out/'expected.json'
        self.assertEqual(self.verify('package-verify'),0)
        restored=self.base/'package-verify/restored/ignored/node_modules/sanitize-filename/.gitmodules'
        self.assertEqual(restored.read_text(),(package/'.gitmodules').read_text())
        # A top-level .gitmodules means real submodules, which stay out of scope.
        (self.root/'.gitmodules').write_text('[submodule "vendor"]\n\tpath = vendor\n')
        code,_,out=self.snapshot_capture('submodules')
        self.assertEqual(code,1)
        self.assertEqual(json.loads((out/'result.json').read_text())['reason'],'submodules_not_in_scope')

    def finder_case(self, name, change):
        """Archive the repo, change the live source, then capture it as the baseline."""
        self.archive=Path(snapshot(self.root,self.base/(name+'-archives'),self.base/(name+'-stage'))['archive'])
        change()
        out=self.base/(name+'-capture')
        self.assertEqual(audit.main(['capture','--source',str(self.root),'--archive-sha256',audit.digest(self.archive),
                                     '--out',str(out)]),0)
        self.expected=out/'expected.json'

    def verify_finder(self, output):
        return audit.main(['verify','--archive',str(self.archive),'--expected',str(self.expected),
                           '--manifest-sha256',audit.digest(self.expected),'--out',str(self.base/output),
                           '--allow-finder-only'])

    def test_finder_only_differences_pass_only_when_allowed_and_are_counted(self):
        # RepoHub does not re-archive .DS_Store-only changes, so the archive keeps older ones.
        (self.root/'.DS_Store').write_bytes(b'old view')
        (self.root/'ignored/.DS_Store').write_bytes(b'removed later')
        # A new folder is a real change the app would back up, so archive it first.
        (self.root/'script-folder').mkdir();(self.root/'script-folder/keep.txt').write_text('real content')
        self.archive=Path(snapshot(self.root,self.base/'f-archives',self.base/'f-stage')['archive'])
        (self.root/'.DS_Store').write_bytes(b'newer, longer view settings')
        (self.root/'ignored/.DS_Store').unlink()
        (self.root/'script-folder/.DS_Store').write_bytes(b'only in source')
        out=self.base/'f-capture'
        self.assertEqual(audit.main(['capture','--source',str(self.root),'--archive-sha256',audit.digest(self.archive),
                                     '--out',str(out)]),0)
        self.expected=out/'expected.json'
        # Strict by default.
        self.assertEqual(self.verify('f-strict'),1)
        self.assertFalse((self.base/'f-strict/restored').exists())
        # Allowed and disclosed; the restored Finder files are the archive's own bytes.
        self.assertEqual(self.verify_finder('f-allowed'),0)
        result=self.result('f-allowed')
        self.assertEqual(result['git_history'],'verified')
        report=result['finder_only_differences']
        self.assertEqual((report['changed'],report['only_in_source'],report['only_in_archive']),(1,1,1))
        restored=self.base/'f-allowed/restored'
        self.assertEqual((restored/'.DS_Store').read_bytes(),b'old view')
        self.assertEqual((restored/'ignored/.DS_Store').read_bytes(),b'removed later')
        self.assertFalse((restored/'script-folder/.DS_Store').exists())
        self.assertEqual((restored/'script-folder/keep.txt').read_text(),'real content')
        self.assertIn('finder_only_differences',(self.base/'f-allowed/events.jsonl').read_text())

    def test_allowing_finder_files_still_catches_every_other_difference(self):
        cases={
            'content':lambda:(self.root/'uncommitted.txt').write_text('edited!!!!!'),
            'appledouble':lambda:(self.root/'._uncommitted.txt').write_bytes(b'AppleDouble'),
            'inside-git':lambda:(self.root/'.git/info/.DS_Store').write_bytes(b'Finder in Git'),
        }
        for name,change in cases.items():
            with self.subTest(case=name):
                self.finder_case(name,change)
                self.assertEqual(self.verify_finder(name+'-verify'),1)
                self.assertFalse(self.result(name+'-verify')['result']=='passed')
                for extra in (self.root/'._uncommitted.txt',self.root/'.git/info/.DS_Store'):
                    if extra.exists():extra.unlink()
                (self.root/'uncommitted.txt').write_text('uncommitted')

    def test_named_pipes_in_the_source_are_not_part_of_the_restore(self):
        # RepoHub does not archive sockets or pipes, so a live pipe must not fail capture or the match.
        os.mkfifo(self.root/'events.pipe')
        code,archive,out=self.snapshot_capture('pipe')
        self.assertEqual(code,0)
        self.archive,self.expected=archive,out/'expected.json'
        self.assertNotIn('events.pipe',json.loads(self.expected.read_text())['entries'])
        self.assertEqual(self.verify('pipe-verify'),0)
        self.assertFalse((self.base/'pipe-verify/restored/events.pipe').exists())

    def test_legacy_baseline_without_worktree_scope_still_restores(self):
        baseline = json.loads(self.expected.read_text())
        baseline.pop('worktree_metadata', None)
        self.expected.write_text(json.dumps(baseline))
        self.assertEqual(self.verify('legacy-baseline'), 0)
