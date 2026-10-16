"""Evidence about observed changes and displayed status; never changes backup policy."""
from collections import OrderedDict
import hashlib
import json
import math
from datetime import datetime
from pathlib import Path
import threading
from diagnostics import diagnostic_ref

PHASES = {'background', 'stale', 'error', 'copying', 'changed', 'verifying', 'ready', 'uploading', 'pending', 'unknown'}
LABELS = {'Project files match', 'Status outdated', 'Needs attention', 'Backing up', 'Checking for changes',
          'Files changing', 'First backup pending', 'Files changed', 'Finder metadata changed', 'Git data changed',
          'Finder / Git data changed', 'Backup needs updating', 'Verifying', 'Backed up',
          'Uploading', 'Waiting for iCloud', 'Awaiting confirmation'}


# Fixed, shareable UI vocabulary. No repo names, paths or exception text enter it.
PRESENTATION_TEXT = {
    'ready': ('backed_up', 'Backed up', 'Your files are backed up.'),
    'background': ('backed_up', 'Files match', 'Your project files and Git match the backup.'),
    'finder': ('backed_up', 'Only Finder metadata changed', 'Only Finder metadata changed.'),
    'finder_pending': ('backup_pending', 'Only Finder metadata changed', 'Only Finder metadata changed.'),
    'git': ('backup_pending', 'Only Git data changed', 'Only Git data changed.'),
    'git_finder': ('backup_pending', 'Only Git and Finder metadata changed', 'Only Git and Finder metadata changed.'),
    'view_settings': ('backed_up', 'Only Finder view settings changed', 'Only Finder view settings changed.'),
    'metadata': ('backup_pending', 'Only file metadata changed', 'Only file metadata changed.'),
    'git_metadata': ('backup_pending', 'Only Git and file metadata changed', 'Only Git and file metadata changed.'),
    'unclassified': ('backup_pending', 'Changes need verification', 'RepoHub hasn’t established which files changed.'),
    'first': ('backup_pending', 'First backup pending', 'Your first backup is pending.'),
    'edits': ('backup_pending', 'Edits confirmed', 'RepoHub confirmed edits.'),
    'changed': ('backup_pending', 'Backup pending', 'RepoHub is waiting to back up this repo.'),
    'changing': ('working', 'Checking again', 'Files changed during the scan.'),
    'verifying': ('working', 'Scanning', 'RepoHub is scanning for changes…'),
    'copying': ('working', 'Creating backup', 'RepoHub is creating your backup…'),
    'uploading': ('working', 'Uploading', 'macOS is uploading your backup…'),
    'pending': ('upload_unconfirmed', 'Awaiting upload confirmation', 'macOS hasn’t confirmed the upload yet.'),
    'stale': ('status_unavailable', 'Current status unavailable', 'RepoHub can’t get current backup status.'),
    'error': ('failure', 'Needs attention — failure', 'Needs attention — failure.'),
    'unknown': ('upload_unconfirmed', 'Upload status unavailable', 'RepoHub can’t read the upload status.'),
}


def presentation_text(facts, phase, version='status-clarity-1'):
    code = phase
    if phase in {'uploading', 'pending'} and (not facts['archive_ref']
            or facts['cloud_archive_ref'] != facts['archive_ref']):
        code = 'unknown'
    if phase == 'changed':
        same_archive = facts['verification_archive_ref'] == facts['archive_ref']
        counts = facts['counts']
        confirmed = (facts['verification_state'] == 'different' and same_archive
                     and (counts['repo_files'] > 0 or counts['git_data'] > 0))
        code = 'first' if not facts['has_backup'] else 'edits' if confirmed else 'changed'
    elif phase == 'verifying' and facts['verification_state'] == 'changing':
        code = 'changing'
    if version == 'status-clarity-2':
        if phase == 'background':
            code = 'finder'
        elif (phase == 'changed' and facts['has_backup'] and facts['archive_ref']
              and facts['verification_state'] == 'different'
              and facts['verification_archive_ref'] == facts['archive_ref']
              and facts['counts_complete'] and facts['counts']['repo_files'] == 0):
            counts = facts['counts']
            if counts['git_data'] > 0:
                code = 'git_finder' if counts['finder_metadata'] > 0 else 'git'
            elif counts['finder_metadata'] > 0:
                code = 'finder_pending'
    if version in {'status-clarity-3', 'status-clarity-4'}:
        if phase == 'background':
            code = 'view_settings'
        elif phase == 'changed' and facts['has_backup']:
            counts = facts['counts']
            complete = (facts['counts_complete'] and facts['archive_ref']
                        and facts['verification_archive_ref'] == facts['archive_ref']
                        and facts['verification_state'] == 'different' and any(counts.values()))
            if not complete:
                code = 'unclassified'
            elif counts['repo_files'] == 0:
                code = ('git_metadata' if counts['finder_metadata'] else 'git') if counts['git_data'] else 'metadata'
    category, label, headline = PRESENTATION_TEXT.get(code, PRESENTATION_TEXT['unknown'])
    return {'category': category, 'display_label': label, 'display_headline': headline}


TIMING_STATES = {'scheduled', 'due', 'busy', 'manual', 'unavailable', 'awaiting_edits', 'blocked', 'creating'}
TIMING_REASONS = {'periodic', 'edits', 'manual', 'power_unknown', 'awaiting_edits', 'blocked', 'checks_unavailable', 'active_backup'}
LOCATION_STATES = {'cloud_confirmed', 'local', 'none', 'unavailable'}
INCLUSION_STATES = {'none', 'confirmed_changes', 'git_data', 'metadata', 'git_metadata'}
TIMING_FIELDS = {'schedule_state', 'timing_reason', 'location_state', 'created_at', 'due_at', 'remaining_minutes', 'inclusion_state'}


def timing_receipt(facts, freshness='current'):
    """Expected secondary-line meaning from the immutable observed projection.

    Exact dates stay in memory for comparison only; emitted diagnostics use
    fixed codes and bounded relative minutes, never dates or arbitrary prose.
    """
    schedule = facts.get('schedule_evidence') or {}
    location = facts.get('backup_location') or {}
    result = {'schedule_state': schedule.get('state', 'unavailable'),
              'timing_reason': schedule.get('reason', 'power_unknown'),
              'location_state': location.get('state', 'unavailable'),
              'created_at': location.get('created_at'), 'due_at': schedule.get('due_at'),
              'remaining_minutes': None, 'inclusion_state': 'none'}
    seconds = schedule.get('due_in_seconds')
    if type(seconds) in (int, float) and math.isfinite(seconds) and 0 <= seconds <= 86400:
        result['remaining_minutes'] = math.ceil(seconds / 60)
    if facts['copying']:
        result.update(schedule_state='creating', timing_reason='active_backup', due_at=None, remaining_minutes=None)
    if not facts['fresh']:
        result.update(schedule_state='unavailable', timing_reason='checks_unavailable', due_at=None, remaining_minutes=None)
    if freshness != 'current':
        result.update(schedule_state='unavailable', timing_reason='checks_unavailable', due_at=None,
                      remaining_minutes=None, location_state='unavailable', created_at=None)
    counts = facts['counts']
    confirmed = (freshness == 'current' and facts['fresh'] and not facts['has_error'] and facts['needs_backup']
                 and facts['cloud_state'] != 'error'
                 and facts['has_backup'] and facts['archive_ref'] and facts['counts_complete']
                 and facts['verification_state'] == 'different'
                 and facts['verification_archive_ref'] == facts['archive_ref'])
    if confirmed and not facts['copying']:
        if counts['repo_files']:
            result['inclusion_state'] = 'confirmed_changes'
        elif counts['git_data']:
            result['inclusion_state'] = 'git_metadata' if counts['finder_metadata'] else 'git_data'
        elif counts['finder_metadata']:
            result['inclusion_state'] = 'metadata'
    return result


def validate_timing(row):
    if not isinstance(row, dict) or set(row) != TIMING_FIELDS:
        raise ValueError('Invalid timing receipt fields')
    for field, allowed in [('schedule_state', TIMING_STATES), ('timing_reason', TIMING_REASONS),
                           ('location_state', LOCATION_STATES), ('inclusion_state', INCLUSION_STATES)]:
        if not isinstance(row[field], str) or row[field] not in allowed:
            raise ValueError('Invalid timing code')
    minutes = row['remaining_minutes']
    if minutes is not None and (type(minutes) is not int or not 0 <= minutes <= 1440):
        raise ValueError('Invalid relative timing')
    for field in ('created_at', 'due_at'):
        value = row[field]
        if value is not None:
            if not isinstance(value, str) or len(value) > 64:
                raise ValueError('Invalid timing date')
            try:
                if datetime.fromisoformat(value).tzinfo is None:
                    raise ValueError('Missing timing timezone')
            except ValueError:
                raise ValueError('Invalid timing date') from None


def repo_facts(row):
    backup, verification, cloud = row.get('last_backup') or {}, row.get('verification') or {}, row.get('cloud') or {}
    counts = verification.get('changes', {}).get('counts', {})
    counts = {kind: counts.get(kind, 0) for kind in ('finder_metadata', 'git_data', 'repo_files')}
    return {'repo_ref': diagnostic_ref(row['id']), 'archive_ref': diagnostic_ref(backup.get('archive')), 'run_id': backup.get('run_id'),
            'source_signature': row.get('signature'), 'backup_signature': backup.get('signature'),
            'content_signature': verification.get('content_signature'),
            'archive_content_signature': verification.get('archive_content_signature'),
            'verification_state': verification.get('state'),
            'needs_backup': row.get('needs_backup'),
            'ignored_finder_only': verification.get('ignored_finder_only') is True,
            'backup_required': verification.get('backup_required'), 'edit_signature': row.get('edit_signature'), 'metadata_changed': row.get('signature') != backup.get('signature'),
            'counts': counts}


def change_reason(row, facts):
    state, counts = facts['verification_state'], facts['counts']
    if row.get('error'):
        return 'scan_error'
    if state == 'changing':
        return 'source_changed_during_verification'
    if state == 'error':
        return 'verification_error'
    if not row.get('last_backup'):
        return 'first_backup_pending'
    if state == 'checking':
        return 'awaiting_hash_check'
    if state == 'matched' and not facts['needs_backup']:
        return 'timestamp_only_match' if facts['metadata_changed'] else 'contents_match'
    if state == 'different':
        if facts['ignored_finder_only']:
            return 'finder_metadata_ignored'
        if counts['repo_files']:
            return 'repo_files_differ'
        if counts['finder_metadata'] and not counts['git_data']:
            return 'finder_metadata_only'
        if counts['git_data'] and not counts['finder_metadata']:
            return 'git_data_only'
        if counts['finder_metadata'] or counts['git_data']:
            return 'finder_and_git_data'
        return 'content_difference_unclassified'
    return 'backup_pending_unclassified'


def icon_reason(rendered, facts):
    """Explain the reported presentation; inputs remain recorded independently."""
    # This checks the logged inputs independently of the submitted icon. A claimed
    # green icon never becomes proof of a verified/uploaded archive.
    same_verification = facts['verification_archive_ref'] == facts['archive_ref']
    same_cloud = facts['cloud_archive_ref'] == facts['archive_ref']
    if facts['fresh'] is not True:
        expected, reason = 'stale', 'checks_not_fresh'
    elif facts['has_error'] or facts['cloud_state'] == 'error':
        expected, reason = 'error', 'observed_error'
    elif facts['verification_state'] == 'changing':
        expected, reason = 'verifying', 'source_changed_during_verification'
    elif facts['copying']:
        expected, reason = 'copying', 'active_repo_backup'
    elif facts['needs_backup']:
        if facts['has_backup'] and facts['verification_state'] == 'checking':
            expected, reason = 'verifying', 'awaiting_hash_verification'
        else:
            expected, reason = 'changed', facts['change_reason']
    elif (facts['needs_backup'] is False and facts['ignored_finder_only'] and facts['backup_required'] is False
          and facts['has_backup'] and facts['backup_hash_ref'] and same_verification
          and facts['verification_state'] == 'different'):
        expected, reason = cloud_icon(facts, same_cloud, finder=True)
    elif facts['verification_state'] != 'matched' or not same_verification:
        expected, reason = 'verifying', 'awaiting_hash_verification'
    else:
        expected, reason = cloud_icon(facts, same_cloud)
    if rendered['phase'] != expected or rendered['ready'] != (expected == 'ready'):
        return 'presentation_inputs_disagree'
    return reason


def cloud_icon(facts, same_cloud, finder=False):
    if facts['cloud_state'] == 'uploaded' and same_cloud and facts['archive_ref'] and facts['backup_hash_ref']:
        return ('background', 'finder_only_project_match') if finder else ('ready', 'fresh_hashes_and_upload_confirmed')
    if facts['cloud_state'] == 'uploading':
        return 'uploading', 'macos_uploading'
    if facts['cloud_state'] == 'pending':
        return 'pending', 'macos_upload_pending'
    return 'unknown', 'upload_not_confirmed'


def safe_samples(row):
    result = []
    for item in row.get('verification', {}).get('changes', {}).get('examples', [])[:8]:
        relative = item['path']
        name = Path(relative).name
        known = ('finder_store' if name == '.DS_Store' else 'appledouble' if name.startswith('._')
                 else 'git_index' if relative == '.git/index' else 'git_data' if '.git' in Path(relative).parts
                 else 'repo_file')
        result.append({'path_ref': diagnostic_ref(relative), 'category': item['category'],
                       'change': item['change'], 'known_file': known})
    return result


class ChangeEvidence:
    def __init__(self, log):
        self.log = log
        self.lock = threading.RLock()
        self.last_repo = {}
        self.snapshots = OrderedDict()
        self.clients = OrderedDict()
        self.displays = {}

    def repo_checked(self, row, scan_id, duration_ms, cached):
        facts = repo_facts(row)
        reason = change_reason(row, facts)
        details = {**facts, 'reason': reason, 'verification_checked_at': row.get('verification', {}).get('checked_at'),
                   'samples': safe_samples(row)}
        key = row['id']
        with self.lock:
            previous = self.last_repo.get(key)
            if previous != details:
                recorded = self.log.emit('repo_checked', scan_id=scan_id, duration_ms=duration_ms, cached=cached,
                              files=row.get('files'), bytes=row.get('bytes'),
                              previous_signature=previous.get('source_signature') if previous else None, **details)
                if recorded:
                    self.last_repo[key] = details

    def observe_status(self, status):
        projection = {}
        backup = status.get('backup', {})
        for row in status['repos']:
            verification, cloud = row.get('verification', {}), row.get('cloud', {})
            copying = bool(backup.get('running') and (backup.get('current_repo_id') == row['id']
                           if 'current_repo_id' in backup else backup.get('current_repo') == row['name']))
            raw_counts = verification.get('changes', {}).get('counts', {})
            counts_complete = all(type(raw_counts.get(kind)) is int and raw_counts[kind] >= 0
                                  for kind in ('finder_metadata', 'git_data', 'repo_files'))
            schedule_evidence = json.loads(json.dumps(row.get('schedule_evidence', {})))
            schedule_evidence.pop('observed_at', None)
            seconds = schedule_evidence.get('due_in_seconds')
            if type(seconds) in (int, float) and math.isfinite(seconds) and 0 <= seconds <= 86400:
                # Receipts display whole remaining minutes; sub-minute polling is not new evidence.
                schedule_evidence['due_in_seconds'] = math.ceil(seconds / 60) * 60
            projection[row['id']] = {**repo_facts(row), 'counts_complete': counts_complete,
                'change_reason': change_reason(row, repo_facts(row)),
                'active_run_id': backup.get('run_id') if copying else None,
                'verification_archive_ref': diagnostic_ref(verification.get('archive')),
                'verification_signature': verification.get('signature'),
                'verification_checked_at': verification.get('checked_at'),
                'backup_hash_ref': diagnostic_ref((row.get('last_backup') or {}).get('sha256')),
                'has_backup': row.get('last_backup') is not None,
                'fresh': row.get('health', {}).get('fresh'),
                'cloud_state': cloud.get('state'), 'cloud_archive_ref': diagnostic_ref(cloud.get('archive')),
                'percent': cloud.get('percent'), 'has_error': bool(row.get('error') or verification.get('error') or any(
                    (error.get('repo_id') == row['id'] if 'repo_id' in error else error.get('repo') == row['name'])
                    and error.get('error') for error in backup.get('errors', []))),
                'copying': copying,
                'schedule_evidence': schedule_evidence,
                'backup_location': json.loads(json.dumps(row.get('backup_location', {})))}
        identity = hashlib.sha256(json.dumps(projection, sort_keys=True, separators=(',', ':')).encode()).hexdigest()[:24]
        with self.lock:
            if identity not in self.snapshots:
                self.snapshots[identity] = projection
                self.log.emit('status_snapshot', observation_id=identity, scan_id=status.get('scan_id'), repo_count=len(projection))
                for facts in projection.values():
                    self.log.emit('status_repo', observation_id=identity, scan_id=status.get('scan_id'),
                                  repo_ref=facts['repo_ref'], archive_ref=facts['archive_ref'], run_id=facts['active_run_id'] or facts['run_id'],
                                  reason=facts['change_reason'],
                                  verification_archive_ref=facts['verification_archive_ref'], cloud_archive_ref=facts['cloud_archive_ref'], copying=facts['copying'],
                                  source_signature=facts['source_signature'], backup_signature=facts['backup_signature'],
                                  verification_state=facts['verification_state'], needs_backup=facts['needs_backup'],
                                  counts=facts['counts'], fresh=facts['fresh'], mode=facts['cloud_state'],
                                  has_error=facts['has_error'], has_backup=facts['has_backup'], backup_hash_ref=facts['backup_hash_ref'],
                                  ignored_finder_only=facts['ignored_finder_only'], backup_required=facts['backup_required'], edit_signature=facts['edit_signature'])
                while len(self.snapshots) > 16:
                    old, _ = self.snapshots.popitem(last=False)
                    self.displays.pop(old, None)
            self.last_repo = {key: value for key, value in self.last_repo.items() if key in projection}
        return identity

    def presentation(self, payload):
        import re
        if not isinstance(payload, dict) or set(payload) not in ({'surface', 'native', 'client_id', 'observation_id', 'policy_version', 'rows'}, {'surface', 'native', 'client_id', 'observation_id', 'policy_version', 'rows', 'client_freshness'}, {'surface', 'native', 'client_id', 'observation_id', 'policy_version', 'rows', 'client_freshness', 'selected_repo_id'}):
            raise ValueError('Invalid presentation diagnostic fields')
        if (not isinstance(payload['surface'], str) or payload['surface'] not in {'menu', 'app'} or type(payload['native']) is not bool
                or not isinstance(payload['client_id'], str) or not re.fullmatch(r'[0-9a-f]{24}', payload['client_id'])
                or not isinstance(payload['observation_id'], str) or not re.fullmatch(r'[0-9a-f]{24}', payload['observation_id'])
                or not isinstance(payload['policy_version'], str)
                or payload['policy_version'] not in {'change-evidence-2', 'status-clarity-1', 'status-clarity-2', 'status-clarity-3', 'status-clarity-4'}
                or not isinstance(payload['rows'], list) or len(payload['rows']) > 4096):
            raise ValueError('Invalid presentation diagnostic values')
        freshness = payload.get('client_freshness', 'current')
        if not isinstance(freshness, str) or freshness not in {'current','request_failed','response_timeout','cache_expired'}:
            raise ValueError('Invalid client freshness')
        with self.lock:
            snapshot = self.snapshots.get(payload['observation_id'])
            if snapshot is None:
                raise FileExistsError('Observed status expired; request fresh status')
            rows = payload['rows']
            timing_frame = payload['policy_version'] == 'status-clarity-4' and payload['surface'] == 'menu'
            selected = payload.get('selected_repo_id')
            if timing_frame and (not isinstance(selected, str) or selected not in snapshot):
                if snapshot or selected is not None:
                    raise ValueError('Invalid selected timing repo')
            if not timing_frame and 'selected_repo_id' in payload:
                raise ValueError('Unexpected timing selection')
            modern = payload['policy_version'] in {'status-clarity-1', 'status-clarity-2', 'status-clarity-3', 'status-clarity-4'}
            row_fields = {'repo_id', 'phase', 'display_label', 'ready'}
            if modern:
                row_fields |= {'category', 'display_headline'}
            labels = LABELS | {value[1] for value in PRESENTATION_TEXT.values()}
            for row in rows:
                expected_fields = row_fields | ({'timing'} if timing_frame and isinstance(row, dict) and row.get('repo_id') == selected else set())
                if (not isinstance(row, dict) or set(row) != expected_fields
                        or not isinstance(row['repo_id'], str) or row['repo_id'] not in snapshot
                        or not isinstance(row['phase'], str) or row['phase'] not in PHASES
                        or not isinstance(row['display_label'], str) or row['display_label'] not in labels or type(row['ready']) is not bool):
                    raise ValueError('Invalid rendered diagnostic row')
                if modern and (not isinstance(row['category'], str)
                               or row['category'] not in {value[0] for value in PRESENTATION_TEXT.values()}
                               or not isinstance(row['display_headline'], str)
                               or row['display_headline'] not in {value[2] for value in PRESENTATION_TEXT.values()}):
                    raise ValueError('Invalid presentation text')
                if 'timing' in row:
                    validate_timing(row['timing'])
            if len(rows) != len(snapshot) or len({r['repo_id'] for r in rows}) != len(snapshot):
                raise ValueError('Presentation must describe the observed repo list')
            client, observation = payload['client_id'], payload['observation_id']
            self.log.emit('ui_frame', client_id=client, observation_id=observation,
                          surface=payload['surface'], native=payload['native'], policy_version=payload['policy_version'], client_freshness=freshness, repo_count=len(rows))
            previous = self.clients.pop(client, {})
            current = {}
            displays = self.displays.setdefault(observation, {})
            for row in rows:
                key = row['repo_id']
                signature = (observation, freshness, payload['policy_version'], row['phase'], row['display_label'], row['ready'], row.get('category'), row.get('display_headline'), json.dumps(row.get('timing'), sort_keys=True))
                current[key] = signature
                repo_ref = snapshot[key]['repo_ref']
                if previous.get(key) != signature:
                    reason = (icon_reason(row, snapshot[key]) if freshness == 'current' else
                              ('client_' + freshness if row['phase'] == 'stale' and row['ready'] is False and row['display_label'] == ('Current status unavailable' if modern else 'Status outdated') else 'presentation_inputs_disagree'))
                    if modern:
                        expected = presentation_text(snapshot[key], row['phase'], payload['policy_version'])
                        if any(row[field] != value for field, value in expected.items()):
                            reason = 'presentation_inputs_disagree'
                    text_fields = ({field: row[field] for field in ('category', 'display_headline')}
                                   if modern else {})
                    if reason == 'presentation_inputs_disagree':
                        self.log.emit('presentation_input_disagreement', severity='warning', repo_ref=repo_ref,
                                      observation_id=observation, surface=payload['surface'], native=payload['native'],
                                      phase=row['phase'], display_label=row['display_label'], reason=reason)
                    self.log.emit('ui_presented', repo_ref=repo_ref, client_id=client, observation_id=observation,
                                  surface=payload['surface'], native=payload['native'], policy_version=payload['policy_version'],
                                  client_freshness=freshness, **text_fields, phase=row['phase'], display_label=row['display_label'], result='ready' if row['ready'] else 'not_ready',
                                  run_id=snapshot[key]['active_run_id'] or snapshot[key]['run_id'], archive_ref=snapshot[key]['archive_ref'],
                                  reason=reason)
                if 'timing' in row and previous.get(key) != signature:
                    expected_timing = timing_receipt(snapshot[key], freshness)
                    timing_good = row['timing'] == expected_timing
                    safe_fields = {field: row['timing'][field] for field in
                                   ('schedule_state', 'timing_reason', 'location_state', 'remaining_minutes', 'inclusion_state')}
                    self.log.emit('ui_timing', repo_ref=repo_ref, observation_id=observation,
                                  client_id=client, surface=payload['surface'], native=payload['native'],
                                  policy_version=payload['policy_version'], client_freshness=freshness,
                                  result='complete' if timing_good else 'failed', **safe_fields)
                    if not timing_good:
                        self.log.emit('timing_disagreement', severity='warning', repo_ref=repo_ref,
                                      observation_id=observation, result='failed', **safe_fields)
                peers = displays.setdefault(key, {})
                view = (payload['surface'], payload['native'], freshness, payload['policy_version'])
                rendered = (row['phase'], row['display_label'], row['ready'], row.get('category'), row.get('display_headline'))
                for peer, peer_value in peers.items():
                    if peer != view and peer[2:] == view[2:] and peer_value != rendered and previous.get(key) != signature:
                        self.log.emit('presentation_disagreement', severity='warning', repo_ref=repo_ref,
                                      observation_id=observation, client_id=client, surface=payload['surface'], native=payload['native'],
                                      phase=row['phase'], display_label=row['display_label'], result='views_differ')
                peers[view] = rendered
            self.clients[client] = current
            while len(self.clients) > 32:
                self.clients.popitem(last=False)
        return {'recorded': True}
