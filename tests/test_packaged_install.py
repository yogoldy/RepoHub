import json
from pathlib import Path
import plistlib
import signal
import tempfile
import unittest
from unittest.mock import patch
from tools.install_packaged import (
    FRONTEND, SERVICE, freeze_idle_legacy, interpreter_process_path, protected_hashes, require_legacy, restore,
)


class PackagedInstallTests(unittest.TestCase):
    def fixture(self, home):
        state = home / 'Library/Application Support/RepoHub'
        app = home / 'Applications/Repo Hub.app'
        agents = home / 'Library/LaunchAgents'
        state.mkdir(parents=True)
        agents.mkdir(parents=True)
        (app / 'Contents').mkdir(parents=True)
        (app / 'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier': 'com.leogoldberg.repohub'}))
        (state / 'config.json').write_text(json.dumps({'state_dir': str(state), 'port': 8767}))
        (state / 'status.json').write_text(json.dumps({'backup': {'running': False}}))
        service = {'Label': SERVICE, 'ProgramArguments': [str(app / 'Contents/MacOS/RepoHub'),
                   '--helper', '/synthetic/python3', str(state / 'runtime/repohub.py'), '--config', str(state / 'config.json')]}
        front = {'Label': FRONTEND, 'ProgramArguments': [str(app / 'Contents/MacOS/RepoHub'), '--background']}
        for label, value in ((SERVICE, service), (FRONTEND, front)):
            (agents / (label + '.plist')).write_bytes(plistlib.dumps(value))
        return state, app, agents

    def test_only_known_legacy_layout_is_accepted_and_protected_files_are_read_only(self):
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            state, app, agents = self.fixture(home)
            baseline = protected_hashes(state)
            self.assertEqual(require_legacy(home)[:3], (state, app, agents))
            self.assertEqual(protected_hashes(state), baseline)
            info = app / 'Contents/Info.plist'
            info.write_bytes(plistlib.dumps({'CFBundleIdentifier': 'com.leogoldberg.repohub', 'RepoHubPackaged': True}))
            with self.assertRaises(ValueError):
                require_legacy(home)
            info.write_bytes(plistlib.dumps({'CFBundleIdentifier': 'foreign'}))
            with self.assertRaises(ValueError):
                require_legacy(home)

    def test_backup_race_resumes_frozen_process_without_terminating_archive_write(self):
        with tempfile.TemporaryDirectory() as folder:
            state, app, agents = self.fixture(Path(folder))
            record = state / 'migration.json'
            record.write_text(json.dumps({'phase': 'prepared'}))
            (state / 'status.json').write_text(json.dumps({'backup': {'running': True}}))
            with patch('tools.install_packaged.observation', return_value={'backup': {'running': False}}), \
                 patch('tools.install_packaged.service_pid', return_value=123), \
                 patch('tools.install_packaged.pid_path', return_value=Path('/synthetic/python3')), \
                 patch('tools.install_packaged.os.kill') as kill:
                with self.assertRaises(ValueError):
                    freeze_idle_legacy(state, Path('/synthetic/python3'), record)
                self.assertEqual([call.args for call in kill.call_args_list], [(123, signal.SIGSTOP), (123, signal.SIGCONT)])

    def test_watchdog_before_service_handoff_never_restarts_or_replaces_daily_services(self):
        with tempfile.TemporaryDirectory() as folder:
            state, app, agents = self.fixture(Path(folder))
            record = state / 'migration.json'
            record.write_text(json.dumps({'phase': 'prepared', 'state': str(state), 'app': str(app),
                              'agents': str(agents), 'legacy_python': '/synthetic/python3'}))
            with patch('tools.install_packaged.command') as command:
                restore(record)
                command.assert_not_called()
            self.assertEqual(json.loads(record.read_text())['phase'], 'restored')
            self.assertTrue(app.exists())

    def test_configured_interpreter_probe_resolves_framework_launcher_without_weakening_pid_check(self):
        with tempfile.TemporaryDirectory() as folder:
            actual = Path(folder) / 'Python.app-executable'
            actual.write_bytes(b'synthetic')
            configured = Path('/synthetic/bin/python3')
            from subprocess import CompletedProcess
            with patch('tools.install_packaged.command', return_value=CompletedProcess([], 0, str(actual) + '\n', '')) as command:
                self.assertEqual(interpreter_process_path(configured), actual.resolve())
                self.assertEqual(command.call_args.args[0][:3], [str(configured), '-I', '-c'])
            with patch('tools.install_packaged.command', return_value=CompletedProcess([], 0, 'relative-path', '')):
                with self.assertRaises(ValueError):
                    interpreter_process_path(configured)
