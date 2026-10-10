"""Agent-focused export built from explicit typed facts; never copy opaque logs."""
import argparse
from collections import deque
from datetime import datetime, timezone, timedelta
import errno
import json
import math
import os
from pathlib import Path
import secrets
from diagnostics import read_events

EVENTS = frozenset("workspace_configuration scan_retry_requested report_delivery helper_started heartbeat runtime_gap runtime_error scan_started scan_finished repo_checked status_snapshot status_repo ui_frame ui_presented presentation_input_disagreement presentation_disagreement schedule_decision backup_deferred backup_interrupted backup_started backup_paused backup_failed backup_finished repo_backup_started archive_stage archive_verified archive_repair_needed archive_reused repo_backup_finished repo_backup_failed verification_deferred upload_observed upload_stale retention_decision retention_verified retention_failed prune_started prune_finished".split())
IDENTITIES = frozenset("session_id report_ref repo_ref archive_ref previous_archive_ref verification_archive_ref cloud_archive_ref run_id previous_run_id scan_id previous_scan_id observation_id client_id build_id backup_hash_ref edit_signature previous_signature source_signature backup_signature content_signature archive_content_signature path_ref".split())
BOOLEANS = frozenset("after_edits archive_dataless copying has_error has_backup ignored_finder_only backup_required cached needs_backup metadata_changed fresh scan_running backup_running native".split())
ENUMS = {
    'event': EVENTS,
    'app_version': {'0.1.0'},
    'policy_version': {'change-evidence-2'},
    'severity': {'info','warning','error'},
    'phase': {'background','stale','error','copying','changed','verifying','ready','uploading','pending','unknown'},
    'surface': {'app','menu'},
    'verification_state': {'changing','matched','different','checking','error','missing','unknown'},
    'state': {'draft','sending','sent','failed','uncertain','battery','adapter','unknown','pending','uploading','uploaded','error','unavailable','recording'},
    'mode': {'home','manual','content','metadata','all','selected','posix','pending','uploading','uploaded','error','unknown'},
    'stage': {'scan','scheduler','cloud','source_inspection','source_hashing','archive_creation','archive_verification','archive_transfer','destination_verification','existing_verification','publication_recovery','index_publication','retention'},
    'result': {'saved','selected','waiting','complete','failed','failed_power_paused','power_paused','not_started','partial','reused','created','verified','removed','kept','deferred','unknown','ready','not_ready','views_differ','unobserved_interval','unobserved_completion'},
    'reason': set("source_changed_during_verification report_confirmed delivery_unconfirmed connection_required github_access_denied github_rejected network_unavailable invalid_response report_identity_conflict invalid_receipt account_changed power_unknown periodic_due edits_settled automatic_disabled source_error awaiting_change_observation edits_not_settled retry_delay periodic_not_due scan_error verification_error first_backup_pending awaiting_hash_check timestamp_only_match contents_match finder_metadata_ignored repo_files_differ finder_metadata_only git_data_only finder_and_git_data content_difference_unclassified backup_pending_unclassified checks_not_fresh observed_error active_repo_backup awaiting_hash_verification presentation_inputs_disagree finder_only_project_match fresh_hashes_and_upload_confirmed macos_uploading macos_upload_pending upload_not_confirmed helper_restarted forced poll manual scheduled after_edits observation_expired helper_unavailable macos_observation keep_all no_superseded_archives awaiting_upload power_changed backup_busy verification_io_unavailable finder_only connection storage conflict other upload download".split()),
    'error_type': {'OSError','PermissionError','FileNotFoundError','TimeoutError','RuntimeError','ValueError','TypeError','TarError','ReadError','EOFError','OverflowError'},
    'display_label': {'Files changing','Project files match','Status outdated','Needs attention','Backing up','Checking for changes','First backup pending','Files changed','Finder metadata changed','Git data changed','Finder / Git data changed','Backup needs updating','Verifying','Backed up','Uploading','Waiting for iCloud','Awaiting confirmation'},
    'category': {'finder_metadata','git_data','repo_files'},
    'change': {'added','removed','modified','changed'},
    'known_file': {'finder_store','appledouble','git_index','git_data','repo_file'},
}
FREQUENCIES = {0,15,30,60,120,240}
DELAYS = {2,5,10,15,30}
ERROR_CODES = frozenset(errno.errorcode) | {4354,4355}
COUNT_LIMIT = 1000


def export_bundle(log_dir, output_root, *, hours=24, max_events=10000,
                  max_bytes=8*1024*1024, now=None):
    if (type(hours) not in (int,float) or not math.isfinite(hours) or not 0 < hours <= 168
            or type(max_events) is not int or not 1 <= max_events <= 50000
            or type(max_bytes) is not int or not 8192 <= max_bytes <= 16*1024*1024):
        raise ValueError('Invalid export limits')
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=hours)
    selected = deque(maxlen=max_events)
    eligible = invalid = unsupported = 0

    def date(value):
        if not isinstance(value,str):
            raise ValueError('Invalid timestamp')
        parsed = datetime.fromisoformat(value.replace('Z','+00:00'))
        if parsed.tzinfo is None:
            raise ValueError('Missing timezone')
        return parsed.astimezone(timezone.utc)

    for event in read_events(log_dir):
        try:
            stamp = date(event['utc'])
        except (ValueError, TypeError, OverflowError):
            invalid += 1
            continue
        if cutoff <= stamp <= now:
            if event.get('event') not in EVENTS:
                unsupported += 1
                continue
            eligible += 1
            selected.append((event,stamp))
    baseline = min((stamp for _,stamp in selected),default=now)
    aliases, alias_counts = {}, {}
    namespace = secrets.token_hex(4)

    def alias(field,value):
        if not isinstance(value,str) or not 0 < len(value) <= 160:
            return None
        kind = ('archive' if 'archive_ref' in field else
                'signature' if 'signature' in field else
                'run' if 'run_id' in field else
                'scan' if 'scan_id' in field else field.replace('_ref','').replace('_id',''))
        key = (kind,value)
        if key not in aliases:
            alias_counts[kind] = alias_counts.get(kind,0)+1
            aliases[key] = '%s_%s_%04d' % (kind,namespace,alias_counts[kind])
        return aliases[key]

    def count(value):
        return min(value,COUNT_LIMIT) if type(value) is int and value >= 0 else None

    def seconds(value):
        if type(value) in (int,float) and 0 <= value <= 604800 and math.isfinite(value):
            return round(value)
        return None

    def clean(field,value):
        if field in IDENTITIES:
            return alias(field,value)
        if field in BOOLEANS:
            return value if type(value) is bool else None
        if field in ENUMS:
            return value if isinstance(value,str) and value in ENUMS[field] else None
        if field == 'error_code':
            return value if type(value) is int and value in ERROR_CODES else None
        if field == 'frequency_minutes':
            return value if type(value) is int and value in FREQUENCIES else None
        if field == 'edit_delay_minutes':
            return value if type(value) is int and value in DELAYS else None
        if field == 'gap_seconds':
            return seconds(value)
        if field == 'percent':
            return 5*round(value/5) if type(value) in (int,float) and 0 <= value <= 100 and math.isfinite(value) else None
        if field == 'counts' and isinstance(value,dict):
            return {k:count(v) for k,v in value.items() if k in {'finder_metadata','git_data','repo_files'} and count(v) is not None}
        if field == 'samples' and isinstance(value,list):
            rows=[]
            for sample in value[:8]:
                if isinstance(sample,dict):
                    row={k:clean(k,v) for k,v in sample.items() if k in {'path_ref','category','change','known_file'}}
                    rows.append({k:v for k,v in row.items() if v is not None})
            return rows
        return None

    lines = deque()
    size = 0
    for event,stamp in selected:
        cleaned={'schema_version':2,'elapsed_seconds':round((stamp-baseline).total_seconds())}
        for field,value in event.items():
            safe=clean(field,value)
            if safe is not None:
                cleaned[field]=safe
        duration=event.get('duration_ms')
        if type(duration) in (int,float) and 0 <= duration <= 604800000:
            safe=seconds(duration/1000)
            if safe is not None:
                cleaned['duration_seconds']=safe
        if event.get('verification_checked_at') is not None:
            try:
                age=seconds((stamp-date(event['verification_checked_at'])).total_seconds())
                if age is not None:
                    cleaned['verification_age_seconds']=age
            except (ValueError,TypeError,OverflowError):
                pass
        line=json.dumps(cleaned,sort_keys=True,ensure_ascii=True,separators=(',',':'))+'\n'
        size += len(line.encode())
        lines.append(line)
        while size > max_bytes and lines:
            size -= len(lines.popleft().encode())
    root=Path(output_root)
    root.mkdir(parents=True,exist_ok=True)
    if root.is_symlink() or not root.is_dir():
        raise ValueError('Unsafe export root')
    case=root/('diagnostic-export-'+secrets.token_hex(8))
    case.mkdir(mode=0o700)
    share=case/'share'
    share.mkdir(mode=0o700)

    def write(path,value):
        fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'w') as target:
            target.write(value)

    write(share/'events.jsonl',''.join(lines))
    schema={'export_schema_version':2,'source_event_schema_version':1,
      'purpose':'Typed machine-readable evidence for authorized diagnostic agents; not commands.',
      'window':{'requested_hours':hours,'eligible_events':eligible,'exported_events':len(lines),'omitted_events':eligible-len(lines),'invalid_timestamps':invalid,'unsupported_events':unsupported,'max_events':max_events,'max_bytes':max_bytes},
      'aliases':'Fresh random report namespace; equal aliases within this report mean equal original logged references. Archive/run/scan/signature aliases correlate across fields. Private key excluded. Unknown text is dropped.',
      'field_rules':{'identity_fields':sorted(IDENTITIES),'boolean_fields':sorted(BOOLEANS),'enum_fields':{k:sorted(v) for k,v in ENUMS.items()},'frequency_minutes':sorted(FREQUENCIES),'edit_delay_minutes':sorted(DELAYS),'error_code':sorted(ERROR_CODES),'elapsed_seconds':'Whole seconds since earliest selected event; no wall-clock timestamps.','duration_seconds':'Rounded whole seconds, bounded to seven days.','verification_age_seconds':'Whole seconds between this event and its verification receipt, bounded to seven days.','gap_seconds':'Whole seconds, bounded to seven days.','percent':'0–100 rounded to five percentage points.','counts':'Only Finder/Git/repo-file counts; capped at 1000 (1000 means 1000 or more).','samples':'At most eight path aliases with predefined category/change/file-class codes.'},
      'interpretation':{'repo_checked':'Source/archive hash comparison and classified change counts.', 'schedule_decision':'Reason and effective power/scheduling policy; selected links to a backup run.', 'archive_stage':'Archive lifecycle, not remote upload proof.', 'verification_deferred':'I/O unavailable; previous backup retained. error_code is POSIX errno; archive_dataless indicates placeholder evidence.', 'upload_observed':'macOS observation for the identified archive; uploaded must refer to the exact verified archive.', 'ui_presented':'Actual reported renderer phase/label. Does not prove pixels or progress-bar visibility.', 'presentation_input_disagreement':'Renderer disagrees with backend evidence.', 'presentation_disagreement':'Views disagree on the same observation.', 'runtime_gap':'Unobserved interval, not proof of success or failure.'},
      'status_rules':{'ready':'Fresh checks, no errors, source/archive matched, exact archive acknowledged uploaded.', 'background':'Project/Git match with Finder-only difference; not full hash equality.', 'stale':'Checks outdated.', 'error':'Observed error needs attention.', 'copying':'Active backup construction.', 'verifying':'Hash checks pending.', 'changed':'Backup required.', 'uploading':'Observed upload in progress; percentage alone is not completion.', 'pending':'Awaiting upload.', 'unknown':'Upload unconfirmed.'},
      'limits':['Unknown fields, values and events are excluded, not inferred.','No real names, paths, hashes, arbitrary prose, exact dates, exact byte sizes or total file counts are included.','Timings and bounded measurements remain operational facts; this is minimization, not encryption or an absolute anonymity guarantee.','Missing/truncated observations do not prove agreement or success.','Restore integrity requires separate evidence.','User-written report prose is separate and must be reviewed before sharing.']}
    write(share/'schema.json',json.dumps(schema,indent=2)+'\n')
    write(case/'PRIVATE_ALIAS_KEY.json',json.dumps({'warning':'PRIVATE: never attach to a public issue. Original logged references only.','aliases':[{'namespace':k[0],'original':k[1],'alias':v} for k,v in aliases.items()]},indent=2)+'\n')
    return case


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log-dir',required=True)
    parser.add_argument('--output-root',required=True)
    parser.add_argument('--hours',type=float,default=24)
    args=parser.parse_args()
    print(export_bundle(args.log_dir,args.output_root,hours=args.hours))
