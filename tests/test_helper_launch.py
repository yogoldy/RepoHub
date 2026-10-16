from pathlib import Path
import tempfile
import unittest
from helper_launch import service_arguments
from tools import reliability_acceptance as h
from tools import reliability_account_guard as g


class HelperLaunchTests(unittest.TestCase):
    def test_native_entry_keeps_interpreter_script_config_and_spaces(self):
        args = service_arguments('/synthetic/Repo Hub.app', '/usr/bin/python3', '/synthetic/runtime', '/synthetic/my config.json')
        self.assertEqual(args, ['/synthetic/Repo Hub.app/Contents/MacOS/RepoHub', '--helper', '/usr/bin/python3', '/synthetic/runtime/repohub.py', '--config', '/synthetic/my config.json'])
        self.assertIs(h.helper_launch.service_arguments, service_arguments)
        self.assertIs(g.h.helper_launch.service_arguments, service_arguments)

    def test_relative_and_null_paths_fail_before_any_launch(self):
        values = ['/synthetic/app', '/usr/bin/python3', '/synthetic/runtime', '/synthetic/config']
        for index in range(4):
            for bad in ['relative', '/synthetic/invalid\0value']:
                trial = values[:];trial[index] = bad
                with self.assertRaises(ValueError):service_arguments(*trial)

    def test_detached_guard_copies_the_launcher_dependency(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            g.own_scripts(base)
            self.assertEqual((base / 'helper_launch.py').read_bytes(), Path(h.helper_launch.__file__).read_bytes())
            self.assertTrue((base / 'account-guard.py').is_file())
            self.assertTrue((base / 'reliability_acceptance.py').is_file())
