"""Small, explicit backup scheduling and macOS power-source adapter."""
import copy
import math
from datetime import datetime, timezone
import subprocess

FREQUENCIES = (0, 15, 30, 60, 120, 240)
EDIT_DELAYS = (2, 5, 10, 15, 30)


def default_settings():
    return {"battery": {"frequency_minutes": 60, "after_edits": False, "edit_delay_minutes": 5},
            "adapter": {"frequency_minutes": 60, "after_edits": False, "edit_delay_minutes": 5}}


def validate_settings(value):
    if not isinstance(value, dict) or set(value) != {"battery", "adapter"}:
        raise ValueError("Choose settings for battery and power adapter")
    for source in value.values():
        if not isinstance(source, dict) or set(source) != {"frequency_minutes", "after_edits", "edit_delay_minutes"}:
            raise ValueError("Invalid backup settings")
        if type(source["frequency_minutes"]) is not int or source["frequency_minutes"] not in FREQUENCIES:
            raise ValueError("Unsupported backup frequency")
        if type(source["after_edits"]) is not bool:
            raise ValueError("After edits must be on or off")
        if type(source["edit_delay_minutes"]) is not int or source["edit_delay_minutes"] not in EDIT_DELAYS:
            raise ValueError("Unsupported delay after edits")
    return copy.deepcopy(value)


def power_source():
    try:
        result = subprocess.run(["/usr/bin/pmset", "-g", "batt"], capture_output=True,
                                text=True, check=True, timeout=3)
        # Inspect the authoritative first line, not a battery's charging state.
        line = result.stdout.splitlines()[0]
        if "'Battery Power'" in line:
            return "battery"
        if "'AC Power'" in line:
            return "adapter"
    except (OSError, subprocess.SubprocessError, IndexError):
        pass
    return "unknown"


class BackupScheduler:
    """Per-repo quiet periods; failed copies retry at most every five minutes."""
    def __init__(self, now):
        self.last_periodic = now
        self.periodic = {}
        self.changes = {}
        self.attempts = {}

    def observe(self, rows, now):
        present = {row["id"] for row in rows}
        self.changes = {key: value for key, value in self.changes.items() if key in present}
        for row in rows:
            key, signature = row["id"], row.get("edit_signature", row.get("signature"))
            previous = self.changes.get(key)
            if previous is None or signature != previous[0]:
                self.changes[key] = (signature, now)
            if not row.get("needs_backup", True):
                self.attempts.pop(key, None)

    def plan(self, settings, source, rows, now, overrides=None):
        if source not in settings:
            return None
        overrides = overrides or {}
        periodic, edited = [], []
        for row in rows:
            key = row["id"]
            policy = overrides.get(key, settings)[source]
            frequency = policy["frequency_minutes"] * 60
            if frequency and now - self.periodic.get(key, self.last_periodic) >= frequency:
                periodic.append(key)
                continue
            delay = policy["edit_delay_minutes"] * 60
            if (policy["after_edits"] and row.get("needs_backup") and not row.get("error")
                    and key in self.changes and now - self.changes[key][1] >= delay
                    and now - self.attempts.get(key, float("-inf")) >= 300):
                edited.append(key)
        if periodic:
            keys = periodic + edited
            return {"reason": "scheduled", "keys": None if len(periodic) == len(rows) else keys,
                    "periodic_keys": periodic, "power": source}
        if edited:
            return {"reason": "after_edits", "keys": edited, "power": source}
        return None

    def completed(self, plan, rows, now):
        if plan["reason"] == "scheduled":
            for key in plan.get("periodic_keys", [row["id"] for row in rows]):
                self.periodic[key] = now
            if plan["keys"] is None:
                self.last_periodic = now
        for row in rows:
            if plan["keys"] is None or row["id"] in plan["keys"]:
                self.attempts[row["id"]] = now

    def manual_completed(self, now):
        self.last_periodic = now
        self.periodic = {}


def project_schedule(scheduler, settings, source, row, wall_now, monotonic_now,
                     last_periodic_at, repo_periodic_at, busy=False, overrides=None):
    """Read-only eligibility forecast using the same plan and saved cadence clocks.

    Never advance clocks here. A due time is eligibility, not a start/completion
    promise. Manual resets and failed attempts retain the existing policy.
    """
    observed = datetime.fromtimestamp(wall_now, timezone.utc).isoformat()
    result = {"state": "unavailable", "reason": "power_unknown", "due_at": None,
              "due_in_seconds": None, "observed_at": observed}
    overrides = overrides or {}
    policy = overrides.get(row["id"], settings).get(source)
    if not policy:
        return result
    shadow = copy.copy(scheduler)
    shadow.last_periodic = monotonic_now - max(0, wall_now - last_periodic_at)
    shadow.periodic = {key: monotonic_now - max(0, wall_now - timestamp)
                       for key, timestamp in repo_periodic_at.items()}
    candidates = []
    frequency = policy["frequency_minutes"] * 60
    if frequency:
        due = shadow.periodic.get(row["id"], shadow.last_periodic) + frequency
        candidates.append((due, "periodic"))
    if policy["after_edits"] and row.get("needs_backup") and not row.get("error"):
        changed = shadow.changes.get(row["id"])
        if changed:
            quiet_due = changed[1] + policy["edit_delay_minutes"] * 60
            retry_due = shadow.attempts.get(row["id"], float("-inf")) + 300
            candidates.append((max(quiet_due, retry_due), "edits"))
    if not candidates:
        state = "manual" if not frequency and not policy["after_edits"] else "awaiting_edits"
        if policy["after_edits"] and row.get("error"):
            state = "blocked"
        result.update(state=state, reason=state)
        return result
    due, reason = min(candidates, key=lambda candidate: candidate[0])
    # Preserve periodic precedence when multiple triggers are already eligible.
    selected = shadow.plan(settings, source, [row], monotonic_now,
                           overrides)
    if selected and selected.get("periodic_keys"):
        due, reason = next(candidate for candidate in candidates if candidate[1] == "periodic")
    eligible = selected is not None
    wall_due = wall_now + due - monotonic_now
    if reason == "periodic":
        anchor = repo_periodic_at.get(row["id"], last_periodic_at)
        wall_due = max(anchor, wall_now) + frequency if anchor > wall_now else anchor + frequency
    result.update(state=("busy" if busy else "due") if eligible else "scheduled",
                  reason=reason, due_at=datetime.fromtimestamp(wall_due, timezone.utc).isoformat(),
                  due_in_seconds=max(0, math.ceil(due - monotonic_now)))
    return result
