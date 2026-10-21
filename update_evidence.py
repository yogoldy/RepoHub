"""Bounded native update facts, independent of backup and upload success."""
import re

PHASES = frozenset({'checking', 'waiting', 'downloading', 'installing', 'relaunching', 'ready', 'failed'})
REASONS = frozenset({'user_requested', 'scheduled_check', 'backup_busy', 'helper_shutdown', 'helper_stopped',
                     'verified_update', 'update_available', 'sparkle_aborted',
                     'component_mismatch', 'matching_helper', 'recovery_unavailable',
                     'no_update', 'user_cancelled', 'check_finished', 'channel_changed', 'channel_mismatch'})


def update_evidence(value, release):
    if not isinstance(value, dict) or not isinstance(release, dict):
        return None
    fields = {'update_phase', 'update_reason', 'source_revision', 'build'}
    optional = {'update_channel', 'experimental_channels'}
    if not fields.issubset(value) or not set(value).issubset(fields | optional):
        return None
    if 'update_channel' in value and value['update_channel'] not in ('stable', 'testing', 'dev'):
        return None
    if 'experimental_channels' in value:
        if value['experimental_channels'] not in ('enabled', 'disabled') or 'update_channel' not in value:
            return None
        if value['experimental_channels'] == 'disabled' and value['update_channel'] != 'stable':
            return None
    if (not isinstance(value.get('update_phase'), str)
            or not isinstance(value.get('update_reason'), str)
            or value['update_phase'] not in PHASES or value['update_reason'] not in REASONS):
        return None
    if (value.get('source_revision') != release.get('source_revision')
            or value.get('build') != release.get('build')
            or not re.fullmatch('[0-9a-f]{40}', str(value.get('source_revision', '')))
            or not re.fullmatch('[1-9][0-9]*', str(value.get('build', '')))):
        return None
    result = {'update_phase': value['update_phase'], 'update_reason': value['update_reason']}
    if 'update_channel' in value:
        result['update_channel'] = value['update_channel']
    if 'experimental_channels' in value:
        result['experimental_channels'] = value['experimental_channels']
    return result
