"""Bounded native update facts, independent of backup and upload success."""
import re

PHASES = frozenset({'checking', 'waiting', 'downloading', 'installing', 'relaunching', 'ready', 'failed'})
REASONS = frozenset({'user_requested', 'backup_busy', 'helper_shutdown', 'helper_stopped',
                     'verified_update', 'update_available', 'sparkle_aborted',
                     'component_mismatch', 'matching_helper'})


def update_evidence(value, release):
    if not isinstance(value, dict) or not isinstance(release, dict):
        return None
    if set(value) != {'update_phase', 'update_reason', 'source_revision', 'build'}:
        return None
    if value.get('update_phase') not in PHASES or value.get('update_reason') not in REASONS:
        return None
    if (value.get('source_revision') != release.get('source_revision')
            or value.get('build') != release.get('build')
            or not re.fullmatch('[0-9a-f]{40}', str(value.get('source_revision', '')))
            or not re.fullmatch('[1-9][0-9]*', str(value.get('build', '')))):
        return None
    return {'update_phase': value['update_phase'], 'update_reason': value['update_reason']}
