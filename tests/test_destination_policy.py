from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from destination_policy import inspect_destination, require_destination


class DestinationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.cloud = self.base / 'cloud'; self.cloud.mkdir()
        self.target = self.cloud / 'Backups'; self.target.mkdir()
        self.source = self.base / 'repos/Project'; self.source.mkdir(parents=True)
        self.state = self.base / 'state'; self.state.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def inspect(self, path=None, **options):
        return inspect_destination(str(path or self.target), [self.source], self.state,
                                   cloud_root=self.cloud, **options)

    def test_one_cloud_destination_and_probe_leave_contents_unchanged(self):
        (self.target / 'keep').write_text('existing archive')
        record = self.inspect()
        self.assertEqual(require_destination(record), self.target)
        self.assertEqual(sorted(p.name for p in self.target.iterdir()), ['keep'])
        self.assertEqual((self.target / 'keep').read_text(), 'existing archive')

    def test_outside_alias_overlap_missing_and_disk_full_are_rejected(self):
        outside = self.base / 'outside'; outside.mkdir()
        alias = self.cloud / 'alias'; alias.symlink_to(outside)
        for path in [outside, alias]:
            with self.assertRaises(ValueError):
                self.inspect(path)
        with self.assertRaises(ValueError):
            inspect_destination(str(self.cloud), [self.target], self.state, cloud_root=self.cloud)
        with self.assertRaises(FileNotFoundError):
            self.inspect(self.cloud / 'missing')
        with patch('destination_policy.shutil.disk_usage') as usage:
            usage.return_value.free = 0
            with self.assertRaises(OSError):
                self.inspect()

    def test_replaced_or_disconnected_destination_never_recreates_or_rebinds(self):
        record = self.inspect()
        self.target.rename(self.cloud / 'Original')
        with self.assertRaises(FileNotFoundError):
            require_destination(record)
        self.assertFalse(self.target.exists())
        self.target.mkdir()
        with self.assertRaises(OSError):
            require_destination(record)
        with self.assertRaises(OSError):
            self.inspect(expected=record['identity'])
