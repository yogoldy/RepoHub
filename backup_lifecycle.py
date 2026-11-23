"""Local lifecycle evidence; no scheduling, backup or upload policy lives here."""
import threading
import time
from diagnostics import diagnostic_ref


class BackupLifecycle:
    def __init__(self, log, clock=time.monotonic):
        self.log, self.clock = log, clock
        self.lock = threading.RLock()
        self.observations = {}

    def emit(self, event, *, key=None, current=None, **facts):
        if key is not None:
            facts['repo_ref'] = diagnostic_ref(key)
        if current:
            facts.update(archive_ref=diagnostic_ref(current.get('archive')),
                         backup_hash_ref=diagnostic_ref(current.get('sha256')),
                         run_id=current.get('run_id'))
        return self.log.emit(event, **facts)

    def transition(self, event, *, key=None, current=None, **facts):
        """Record changes immediately, unchanged observations once per minute."""
        identity = (event, key)
        value = (diagnostic_ref((current or {}).get('archive')), facts)
        now = self.clock()
        with self.lock:
            previous = self.observations.get(identity)
            if previous and previous[0] == value and now - previous[1] < 60:
                return
            if self.emit(event, key=key, current=current, **facts):
                self.observations[identity] = (value, now)
            # Bound memory if source selection changes repeatedly.
            if len(self.observations) > 8192:
                self.observations.pop(next(iter(self.observations)))

    def schedule(self, scheduler, settings, source, rows, now, overrides, plan, run_id=None):
        selected = {r['id'] for r in rows} if plan and plan['keys'] is None else set((plan or {}).get('keys', []))
        for row in rows:
            key = row['id']
            policy = overrides.get(key, settings).get(source)
            if not policy:
                reason = 'power_unknown'
            elif key in selected:
                reason = 'periodic_due' if key in plan.get('periodic_keys', []) else 'edits_settled'
            elif not policy['frequency_minutes'] and not policy['after_edits']:
                reason = 'automatic_disabled'
            elif policy['after_edits'] and row.get('needs_backup'):
                if row.get('error'):
                    reason = 'source_error'
                elif key not in scheduler.changes:
                    reason = 'awaiting_change_observation'
                elif now - scheduler.changes[key][1] < policy['edit_delay_minutes'] * 60:
                    reason = 'edits_not_settled'
                elif now - scheduler.attempts.get(key, float('-inf')) < 300:
                    reason = 'retry_delay'
                else:
                    reason = 'periodic_not_due'
            else:
                reason = 'periodic_not_due'
            self.transition('schedule_decision', key=key, state=source, reason=reason, run_id=run_id if key in selected else None,
                            result='selected' if key in selected else 'waiting',
                            needs_backup=row.get('needs_backup'),
                            frequency_minutes=policy['frequency_minutes'] if policy else None,
                            after_edits=policy['after_edits'] if policy else None,
                            edit_delay_minutes=policy['edit_delay_minutes'] if policy else None)
