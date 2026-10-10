"""Evidence about observed changes and displayed status; never changes backup policy."""
from collections import OrderedDict
import hashlib
import json
from pathlib import Path
import threading
from diagnostics import diagnostic_ref

PHASES = {'background', 'stale', 'error', 'copying', 'changed', 'verifying', 'ready', 'uploading', 'pending', 'unknown'}
LABELS = {'Project files match', 'Status outdated', 'Needs attention', 'Backing up', 'Checking for changes',
          'Files changing', 'First backup pending', 'Files changed', 'Finder metadata changed', 'Git data changed',
          'Finder / Git data changed', 'Backup needs updating', 'Verifying', 'Backed up',
          'Uploading', 'Waiting for iCloud', 'Awaiting confirmation'}


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
        for row in status['repos']:
            verification, cloud = row.get('verification', {}), row.get('cloud', {})
            projection[row['id']] = {**repo_facts(row),
                'change_reason': change_reason(row, repo_facts(row)),
                'active_run_id': status.get('backup', {}).get('run_id') if status.get('backup', {}).get('running') and status['backup'].get('current_repo') == row['name'] else None,
                'verification_archive_ref': diagnostic_ref(verification.get('archive')),
                'verification_signature': verification.get('signature'),
                'verification_checked_at': verification.get('checked_at'),
                'backup_hash_ref': diagnostic_ref((row.get('last_backup') or {}).get('sha256')),
                'has_backup': row.get('last_backup') is not None,
                'fresh': row.get('health', {}).get('fresh'),
                'cloud_state': cloud.get('state'), 'cloud_archive_ref': diagnostic_ref(cloud.get('archive')),
                'percent': cloud.get('percent'), 'has_error': bool(row.get('error') or verification.get('error') or any(
                    error.get('repo') == row['name'] and error.get('error') for error in status.get('backup', {}).get('errors', []))),
                'copying': bool(status.get('backup', {}).get('running') and status['backup'].get('current_repo') == row['name'])}
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
        if not isinstance(payload, dict) or set(payload) != {'surface', 'native', 'client_id', 'observation_id', 'policy_version', 'rows'}:
            raise ValueError('Invalid presentation diagnostic fields')
        if (not isinstance(payload['surface'], str) or payload['surface'] not in {'menu', 'app'} or type(payload['native']) is not bool
                or not isinstance(payload['client_id'], str) or not re.fullmatch(r'[0-9a-f]{24}', payload['client_id'])
                or not isinstance(payload['observation_id'], str) or not re.fullmatch(r'[0-9a-f]{24}', payload['observation_id'])
                or payload['policy_version'] != 'change-evidence-2'
                or not isinstance(payload['rows'], list) or len(payload['rows']) > 4096):
            raise ValueError('Invalid presentation diagnostic values')
        with self.lock:
            snapshot = self.snapshots.get(payload['observation_id'])
            if snapshot is None:
                raise FileExistsError('Observed status expired; request fresh status')
            rows = payload['rows']
            for row in rows:
                if (not isinstance(row, dict) or set(row) != {'repo_id', 'phase', 'display_label', 'ready'}
                        or not isinstance(row['repo_id'], str) or row['repo_id'] not in snapshot
                        or not isinstance(row['phase'], str) or row['phase'] not in PHASES
                        or not isinstance(row['display_label'], str) or row['display_label'] not in LABELS or type(row['ready']) is not bool):
                    raise ValueError('Invalid rendered diagnostic row')
            if len(rows) != len(snapshot) or len({r['repo_id'] for r in rows}) != len(snapshot):
                raise ValueError('Presentation must describe the observed repo list')
            client, observation = payload['client_id'], payload['observation_id']
            self.log.emit('ui_frame', client_id=client, observation_id=observation,
                          surface=payload['surface'], native=payload['native'], policy_version=payload['policy_version'], repo_count=len(rows))
            previous = self.clients.pop(client, {})
            current = {}
            displays = self.displays.setdefault(observation, {})
            for row in rows:
                key = row['repo_id']
                signature = (observation, row['phase'], row['display_label'], row['ready'])
                current[key] = signature
                repo_ref = snapshot[key]['repo_ref']
                if previous.get(key) != signature:
                    reason = icon_reason(row, snapshot[key])
                    if reason == 'presentation_inputs_disagree':
                        self.log.emit('presentation_input_disagreement', severity='warning', repo_ref=repo_ref,
                                      observation_id=observation, surface=payload['surface'], native=payload['native'],
                                      phase=row['phase'], display_label=row['display_label'], reason=reason)
                    self.log.emit('ui_presented', repo_ref=repo_ref, client_id=client, observation_id=observation,
                                  surface=payload['surface'], native=payload['native'], policy_version=payload['policy_version'],
                                  phase=row['phase'], display_label=row['display_label'], result='ready' if row['ready'] else 'not_ready',
                                  run_id=snapshot[key]['active_run_id'] or snapshot[key]['run_id'], archive_ref=snapshot[key]['archive_ref'],
                                  reason=reason)
                peers = displays.setdefault(key, {})
                view = (payload['surface'], payload['native'])
                rendered = (row['phase'], row['display_label'], row['ready'])
                for peer, peer_value in peers.items():
                    if peer != view and peer_value != rendered and previous.get(key) != signature:
                        self.log.emit('presentation_disagreement', severity='warning', repo_ref=repo_ref,
                                      observation_id=observation, client_id=client, surface=payload['surface'], native=payload['native'],
                                      phase=row['phase'], display_label=row['display_label'], result='views_differ')
                peers[view] = rendered
            self.clients[client] = current
            while len(self.clients) > 32:
                self.clients.popitem(last=False)
        return {'recorded': True}
