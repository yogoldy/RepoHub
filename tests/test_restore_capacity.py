"""Restore budgets must follow selected data and receiver capacity."""
import json
import errno
import hashlib
import io
import tracemalloc
from contextlib import redirect_stderr
from types import SimpleNamespace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from repohub import snapshot
import restore_audit as audit


class RestoreCapacityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / 'Plain'
        self.root.mkdir()
        (self.root / 'data').write_bytes(b'fixture bytes' * 2000)
        self.archive = Path(snapshot(self.root, self.base / 'archives',
                                     self.base / 'stage')['archive'])
        self.capture = self.base / 'capture'
        self.assertEqual(audit.main([
            'capture', '--source', str(self.root), '--archive-sha256',
            audit.digest(self.archive), '--out', str(self.capture),
        ]), 0)
        self.expected = self.capture / 'expected.json'

    def tearDown(self):
        self.temp.cleanup()

    def verify(self, name='verify', extra=()):
        return audit.main([
            'verify', '--archive', str(self.archive), '--expected', str(self.expected),
            '--manifest-sha256', audit.digest(self.expected), '--out', str(self.base / name),
            *extra,
        ])

    def result(self, name='verify'):
        return json.loads((self.base / name / 'result.json').read_text())

    def test_valid_manifest_above_eight_gib_has_no_fixed_byte_ceiling(self):
        size = 9 * 1024**3
        entries = {'large.bin': {'kind': 'file', 'mode': 0o600, 'size': size,
                                 'sha256': '0' * 64}}
        self.assertEqual(audit.validate_entries(entries), size)

    def test_insufficient_capacity_fails_before_any_extracted_file(self):
        before = (audit.digest(self.archive), audit.digest(self.expected))
        with patch.object(audit.shutil, 'disk_usage', return_value=(1, 1, 0)):
            self.assertEqual(self.verify(), 1)
        self.assertEqual(self.result()['reason'], 'restore_capacity_insufficient')
        self.assertFalse((self.base / 'verify/restored').exists())
        self.assertEqual((audit.digest(self.archive), audit.digest(self.expected)), before)

    def test_large_plan_uses_allocation_fragments_and_explicit_budget(self):
        size = 9 * 1024**3
        entries = {'large.bin': {'kind': 'file', 'mode': 0o600, 'size': size,
                                 'sha256': '0' * 64}}
        evidence = audit.Evidence(self.base / 'large-plan')
        required = size + 2 * 4096 + audit.DEFAULT_FREE_RESERVE
        with patch.object(audit.os, 'statvfs', return_value=SimpleNamespace(
                f_frsize=4096, f_bsize=1024**2)), patch.object(
                audit.shutil, 'disk_usage', return_value=(required, 0, required)):
            budget = audit.RestoreBudget(evidence.output / 'restored', entries, evidence)
        self.assertEqual(budget.entry_bytes, 4096)
        self.assertEqual(budget.remaining_bytes, size)
        self.assertEqual(audit.validate_entries(entries, max_bytes=size), size)
        with self.assertRaisesRegex(audit.AuditError, 'byte_budget_exceeded'):
            audit.validate_entries(entries, max_bytes=size - 1)
        with patch.object(audit.shutil, 'disk_usage', return_value=(required, 1, required - 1)):
            with self.assertRaisesRegex(audit.AuditError, 'restore_capacity_insufficient'):
                budget.check()
        self.assertFalse((evidence.output / 'restored').exists())

    def test_operator_budget_and_reserve_are_recorded_on_a_real_restore(self):
        size = (self.root / 'data').stat().st_size
        self.assertEqual(self.verify(extra=('--max-bytes', str(size),
                                           '--reserve-bytes', '0')), 0)
        result = self.result()
        self.assertEqual(result['restored_bytes'], size)
        self.assertEqual(result['byte_budget'], size)
        self.assertEqual(result['free_space_reserve_bytes'], 0)
        self.assertEqual(audit.manifest(self.base / 'verify/restored'), audit.manifest(self.root))
        events = (self.base / 'verify/events.jsonl').read_text()
        self.assertIn('restore_capacity', events)
        self.assertNotIn(str(self.root), events)

    def test_operator_budget_refuses_capture_and_restore_without_extraction(self):
        self.assertEqual(self.verify(extra=('--max-bytes', '1')), 1)
        self.assertEqual(self.result()['reason'], 'byte_budget_exceeded')
        self.assertFalse((self.base / 'verify/restored').exists())
        output = self.base / 'bounded-capture'
        self.assertEqual(audit.main([
            'capture', '--source', str(self.root), '--archive-sha256',
            audit.digest(self.archive), '--out', str(output), '--max-bytes', '1',
        ]), 1)
        self.assertEqual(json.loads((output / 'result.json').read_text())['reason'],
                         'byte_budget_exceeded')
        self.assertFalse((output / 'expected.json').exists())

    def test_space_loss_mid_copy_retains_failure_receipt_and_unchanged_inputs(self):
        block = b'bounded fixture contents' * 40000
        with (self.root / 'data').open('wb') as target:
            for _ in range(24):
                target.write(block)
        self.archive = Path(snapshot(self.root, self.base / 'new-archives',
                                     self.base / 'new-stage')['archive'])
        capture = self.base / 'new-capture'
        self.assertEqual(audit.main([
            'capture', '--source', str(self.root), '--archive-sha256',
            audit.digest(self.archive), '--out', str(capture),
        ]), 0)
        self.expected = capture / 'expected.json'
        before = (audit.digest(self.archive), audit.digest(self.expected))
        partial = self.base / 'verify/restored/data'

        def available(directory):
            # Capacity disappears after actual bytes have reached the isolated destination.
            used = partial.stat().st_size if partial.exists() else 0
            free = 0 if used >= audit.SPACE_CHECK_INTERVAL else 1024**4
            return (1024**4, used, free)

        with patch.object(audit.shutil, 'disk_usage', side_effect=available):
            self.assertEqual(self.verify(), 1)
        self.assertEqual(self.result()['reason'], 'restore_capacity_insufficient')
        self.assertGreater(partial.stat().st_size, 0)
        self.assertLess(partial.stat().st_size, (self.root / 'data').stat().st_size)
        self.assertEqual((audit.digest(self.archive), audit.digest(self.expected)), before)

    def test_filesystem_space_error_never_becomes_a_pass(self):
        before = (audit.digest(self.archive), audit.digest(self.expected))
        with patch.object(audit, 'copy_member', side_effect=OSError(errno.ENOSPC, 'private path')):
            self.assertEqual(self.verify(), 1)
        self.assertEqual(self.result()['reason'], 'restore_capacity_exhausted')
        self.assertEqual((audit.digest(self.archive), audit.digest(self.expected)), before)
        self.assertNotIn('private path', (self.base / 'verify/events.jsonl').read_text())

    def test_copy_uses_bounded_memory_and_detects_short_or_overlong_streams(self):
        size = 32 * 1024**2

        class GeneratedSource:
            remaining = size
            largest_request = 0

            def read(self, count):
                self.largest_request = max(self.largest_request, count)
                if count < 0 or count > audit.COPY_CHUNK_BYTES:
                    raise AssertionError('unbounded source read')
                amount = min(count, self.remaining)
                self.remaining -= amount
                return b'x' * amount

        class HashSink:
            def __init__(self):
                self.digest = hashlib.sha256()

            def write(self, block):
                self.digest.update(block)
                return len(block)

        class Budget:
            copied_bytes = 0
            checks = 0

            def copied(self, count):
                self.copied_bytes += count

            def check(self):
                self.checks += 1

        source, sink, budget = GeneratedSource(), HashSink(), Budget()
        tracemalloc.start()
        try:
            audit.copy_member(source, sink, size, budget)
            peak = tracemalloc.get_traced_memory()[1]
        finally:
            tracemalloc.stop()
        expected = hashlib.sha256()
        for _ in range(32):
            expected.update(b'x' * 1024**2)
        self.assertEqual(sink.digest.hexdigest(), expected.hexdigest())
        self.assertEqual(budget.copied_bytes, size)
        self.assertLessEqual(source.largest_request, audit.COPY_CHUNK_BYTES)
        self.assertLess(peak, 5 * 1024**2)
        self.assertGreater(budget.checks, 2)
        with self.assertRaisesRegex(audit.AuditError, 'truncated_archive_member'):
            audit.copy_member(io.BytesIO(b''), io.BytesIO(), 1, Budget())
        with self.assertRaisesRegex(audit.AuditError, 'short_restore_write'):
            audit.copy_member(io.BytesIO(b'x'), SimpleNamespace(write=lambda _: 0), 1, Budget())
        with self.assertRaisesRegex(audit.AuditError, 'archive_size_overrun'):
            audit.copy_member(SimpleNamespace(read=lambda _: b'xx'), io.BytesIO(), 1, Budget())

    def test_invalid_budget_arguments_and_entry_guard_still_fail_closed(self):
        for argument, value in (('--max-bytes', '0'), ('--max-bytes', '-1'),
                                ('--reserve-bytes', '-1')):
            with self.subTest(argument=argument, value=value), redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    self.verify('invalid', extra=(argument, value))
                self.assertEqual(error.exception.code, 2)
        self.assertFalse((self.base / 'invalid').exists())
        entries = {name: {'kind': 'directory', 'mode': 0o700} for name in ('a', 'b')}
        with patch.object(audit, 'MAX_ENTRIES', 1):
            with self.assertRaisesRegex(audit.AuditError, 'invalid_manifest'):
                audit.validate_entries(entries)

    def test_inventory_entry_limit_stops_before_building_an_unbounded_manifest(self):
        (self.root / 'another').write_text('second entry')
        with patch.object(audit, 'MAX_ENTRIES', 1):
            with self.assertRaisesRegex(audit.AuditError, 'resource_limit'):
                audit.inventory(self.root)
