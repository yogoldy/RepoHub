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

    def test_external_links_and_git_layouts_fail_capture(self):
        (self.root/'link').unlink();(self.root/'link').symlink_to('/private/outside')
        self.assertEqual(audit.main(['capture','--source',str(self.root),'--archive-sha256',audit.digest(self.archive),
                                    '--out',str(self.base/'external')]),1)
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
