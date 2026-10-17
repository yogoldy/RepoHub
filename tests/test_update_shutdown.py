import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request

from repohub import Hub

ROOT = Path(__file__).resolve().parents[1]


class UpdateShutdownTests(unittest.TestCase):
    def test_bundled_sigterm_waits_for_archive_publication_and_preserves_prior_copy(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder).resolve()
            repo = root / 'repos/Example'
            repo.mkdir(parents=True)
            (repo / 'file').write_text('original')
            config = {'repos_root': str(repo.parent), 'state_dir': str(root / 'state'),
                      'backup_root': str(root / 'backups'), 'retention': 'latest',
                      'cloud_helper': '/nonexistent-test-provider', 'scan_seconds': 3600,
                      'require_upload_before_prune': True}
            hub = Hub(config)
            hub.backup()
            prior = next(value for key, value in hub.index.items() if key != '__data__')
            prior_path = Path(prior['archive'])
            prior_bytes = prior_path.read_bytes()
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                config['port'] = sock.getsockname()[1]
            config_path = root / 'config.json'
            config_path.write_text(json.dumps(config))
            (repo / 'file').write_text('confirmed replacement contents')
            script = '''
import json,sys,time,faulthandler
from pathlib import Path
faulthandler.enable()
faulthandler.dump_traceback_later(8, repeat=True)
import repohub
root=Path(sys.argv[1])
original_load=repohub.load_json
release={'source_revision':'a'*40,'build':'100','bundle_id':'com.leogoldberg.repohub.test.shutdown'}
def load(path,default):
    return release if Path(path).name=='release.json' else original_load(path,default)
repohub.load_json=load
# This case controls one manual publication, not background scheduler timing
# or provider availability on the runner.
repohub.Hub.automatic_tick=lambda self: None
repohub.Hub.refresh_cloud=lambda self: None
original_snapshot=repohub.snapshot
def snapshot(*args,**kwargs):
    (root/'busy').touch()
    deadline=time.monotonic()+15
    while not (root/'finish').exists():
        if time.monotonic()>deadline:raise RuntimeError('controlled hold timed out')
        time.sleep(.02)
    return original_snapshot(*args,**kwargs)
repohub.snapshot=snapshot
sys.argv=['repohub.py','--config',str(root/'config.json'),'--bundled']
repohub.main()
'''
            log = (root / 'child.log').open('w')
            process = subprocess.Popen([sys.executable, '-B', '-c', script, str(root)],
                                       cwd=ROOT, stdout=log, stderr=log)
            origin = 'http://127.0.0.1:' + str(config['port'])
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            def get(path):
                with opener.open(origin + path, timeout=1) as response:
                    return json.load(response)
            try:
                deadline = time.monotonic() + 10
                while True:
                    try:
                        token = get('/api/session')['token']
                        break
                    except OSError:
                        if time.monotonic() > deadline:
                            log.flush()
                            self.fail('Synthetic helper did not start; child evidence:\n' +
                                      (root / 'child.log').read_text()[-4000:])
                        time.sleep(.05)
                request = urllib.request.Request(origin + '/api/backup', data=b'{}', headers={
                    'Content-Type': 'application/json', 'Origin': origin, 'X-RepoHub-Token': token})
                with opener.open(request, timeout=2):
                    pass
                deadline = time.monotonic() + 5
                while not (root / 'busy').exists():
                    if time.monotonic() > deadline:
                        self.fail('Backup did not reach controlled snapshot hold')
                    time.sleep(.02)
                process.send_signal(signal.SIGTERM)
                time.sleep(.2)
                self.assertIsNone(process.poll(), 'SIGTERM interrupted an active archive')
                self.assertEqual(prior_path.read_bytes(), prior_bytes)
                (root / 'finish').touch()
                self.assertEqual(process.wait(timeout=10), 0)
                index = json.loads((root / 'state/backups.json').read_text())
                current = index[next(iter(hub.repositories()))]
                self.assertNotEqual(current['archive'], prior['archive'])
                self.assertEqual(hashlib.sha256(Path(current['archive']).read_bytes()).hexdigest(), current['sha256'])
                self.assertEqual(prior_path.read_bytes(), prior_bytes)
            finally:
                (root / 'finish').touch()
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        # Failure cleanup owns only this disposable child. Product
                        # shutdown still never force-kills an active backup.
                        process.kill()
                        process.wait(timeout=5)
                log.close()
