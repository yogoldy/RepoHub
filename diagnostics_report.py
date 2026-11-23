#!/usr/bin/env python3
"""Read bounded local diagnostics; print evidence, not fixes or public uploads."""
import argparse
from collections import Counter
import json
from diagnostics import read_events


def summarize(events):
    counts = Counter()
    latest, presentations, agreements = {}, {}, {}
    lifecycle = []
    mismatches = []
    input_mismatches = []
    sessions = set()
    first = last = None
    backend = {}
    for event in events:
        kind = event.get('event')
        counts[kind] += 1
        sessions.add(event.get('session_id'))
        first = first or event.get('utc'); last = event.get('utc')
        if kind in {'schedule_decision', 'backup_deferred', 'backup_interrupted', 'backup_started', 'backup_paused', 'backup_failed', 'backup_finished',
                    'repo_backup_started', 'archive_stage', 'archive_verified', 'archive_repair_needed', 'archive_reused', 'repo_backup_finished',
                    'repo_backup_failed', 'verification_deferred', 'upload_observed', 'upload_stale', 'retention_decision', 'retention_verified',
                    'retention_failed', 'prune_started', 'prune_finished'}:
            lifecycle.append(event)
            lifecycle = lifecycle[-200:]
        ref = event.get('repo_ref')
        if kind == 'repo_checked':
            latest[ref] = {key: event.get(key) for key in ('utc', 'scan_id', 'reason', 'verification_state', 'needs_backup', 'counts', 'source_signature', 'backup_signature', 'samples', 'ignored_finder_only', 'backup_required', 'edit_signature')}
        elif kind == 'status_repo':
            backend[(event.get('session_id'), event.get('observation_id'), ref)] = {key: event.get(key) for key in ('run_id', 'archive_ref', 'reason', 'copying', 'verification_archive_ref', 'cloud_archive_ref', 'verification_state', 'needs_backup', 'counts', 'fresh', 'mode', 'has_error', 'has_backup', 'backup_hash_ref', 'ignored_finder_only', 'backup_required', 'edit_signature')}
            # The report has bounded working memory even across seven days of logs.
            if len(backend) > 8192:
                backend.pop(next(iter(backend)))
        elif kind == 'ui_presented':
            surface = event.get('surface') + ('_native' if event.get('native') else '_browser')
            presented = {key: event.get(key) for key in ('utc', 'run_id', 'archive_ref', 'reason', 'observation_id', 'phase', 'display_label', 'result', 'policy_version', 'client_freshness')}
            presented['backend'] = backend.get((event.get('session_id'), event.get('observation_id'), ref))
            presentations.setdefault(ref, {})[surface] = presented
            peers = agreements.setdefault((event.get('session_id'), event.get('observation_id'), ref, event.get('client_freshness','current')), {})
            peers[surface] = (event.get('phase'), event.get('display_label'), event.get('result'))
            if len(agreements) > 4096:
                agreements.pop(next(iter(agreements)))
        elif kind == 'presentation_input_disagreement':
            input_mismatches.append({key: event.get(key) for key in ('utc', 'observation_id', 'repo_ref', 'surface', 'native', 'display_label', 'reason')})
            input_mismatches = input_mismatches[-20:]
        elif kind == 'presentation_disagreement':
            mismatches.append({key: event.get(key) for key in ('utc', 'observation_id', 'repo_ref', 'surface', 'native', 'display_label')})
            mismatches = mismatches[-20:]
    compared = [peers for peers in agreements.values() if len(peers) > 1]
    return {'schema_version': 1, 'first_utc': first, 'last_utc': last,
            'recent_lifecycle': lifecycle, 'helper_sessions': len(sessions), 'event_counts': dict(counts),
            'same_observation_comparisons': len(compared),
            'matching_comparisons': sum(len(set(peers.values())) == 1 for peers in compared),
            'input_disagreements': input_mismatches, 'disagreements': mismatches, 'repos': {ref: {'scan': latest.get(ref), 'views': presentations.get(ref, {})}
                                              for ref in latest.keys() | presentations.keys()},
            'limits': 'Only recorded observations are evidence. No view record does not prove a view agreed. No public upload or restore audit.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log-dir', required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    result = json.dumps(summarize(read_events(args.log_dir)), indent=2, sort_keys=True) + '\n'
    if args.output:
        import os
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, 'w') as target:
            target.write(result)
    else:
        print(result, end='')
