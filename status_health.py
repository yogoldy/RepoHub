"""Freshness and persistent problems, independent of archive verification."""
from datetime import datetime


def age(value, now):
    try:
        stamp = datetime.fromisoformat(value).timestamp()
        return max(0, now - stamp) if stamp <= now + 30 else float("inf")
    except (TypeError, ValueError, AttributeError):
        return float("inf")


def annotate_health(status, config, now):
    scan_limit = max(120, config.get("scan_seconds", 30) * 4)
    cloud_limit = max(45, config.get("cloud_seconds", 5) * 6)
    hash_limit = config.get("verification_seconds", 900) + 120
    scan_old = age(status.get("scanned_at"), now) > scan_limit
    for row in status.get("repos", []):
        cloud = row.get("cloud", {})
        verification = row.get("verification", {})
        reasons = []
        if scan_old:
            reasons.append("Repo checks stopped updating")
        if age(cloud.get("checked_at"), now) > cloud_limit:
            reasons.append("Upload status needs a fresh check")
        if (verification.get("state") == "matched" or verification.get("ignored_finder_only") is True) and age(verification.get("checked_at"), now) > hash_limit:
            reasons.append("Hash verification is outdated")
        row["health"] = {"fresh": not reasons, "reasons": reasons}
    status["health"] = {"fresh": not scan_old, "scan_max_age_seconds": scan_limit,
                        "cloud_max_age_seconds": cloud_limit, "hash_max_age_seconds": hash_limit}


class ProblemTracker:
    """Persist one episode per problem; reset only on observed recovery."""
    def __init__(self, saved=None):
        self.episodes = saved or {}

    def update(self, status, now):
        observed = {}
        if not status.get("repos") and not status.get("health", {}).get("fresh", False):
            observed["hub:stale"] = ("Repo Hub", "Repo checks stopped updating", 120, None)
        for row in status.get("repos", []):
            key, name = row["id"], row["name"]
            health = row.get("health", {})
            if not health.get("fresh", False):
                observed[key + ":stale"] = (name, "Status outdated", 120, None)
            if row.get("error") or row.get("verification", {}).get("state") == "error":
                observed[key + ":copy"] = (name, "Backup verification needs attention", 120, None)
            cloud = row.get("cloud", {})
            if cloud.get("state") == "error":
                observed[key + ":upload"] = (name, "iCloud reports an upload problem", 120, cloud.get("archive"))
            elif cloud.get("state") in {"uploading", "pending", "unknown"}:
                # A changing percentage is evidence of progress, even with 4355.
                observed[key + ":upload"] = (name, "Upload has not shown progress for 30 minutes", 1800,
                                               (cloud.get("archive"), cloud.get("percent")))
        for error in status.get("backup", {}).get("errors", []):
            name = error.get("repo", "Repo Hub")
            observed["backup:" + name] = (name, "Backup failed; open Repo Hub for details", 120, None)
        backup = status.get("backup", {})
        if backup.get("running"):
            observed["copy:running"] = (backup.get("current_repo") or "Repo Hub",
                                        "Copying the same repo for 30 minutes; check backup progress", 1800,
                                        (backup.get("started_at"), backup.get("current_repo")))
        data = status.get("data_cloud", {})
        if data.get("state") == "error":
            observed["saved-data"] = ("Saved app data", "iCloud reports an upload problem", 120, data.get("archive"))
        self.episodes = {key: item for key, item in self.episodes.items() if key in observed}
        issues = []
        for key, (name, detail, delay, marker) in observed.items():
            marker = list(marker) if isinstance(marker, tuple) else marker
            item = self.episodes.get(key)
            if not item or item.get("marker") != marker or item.get("detail") != detail:
                item = {"since": now, "marker": marker, "detail": detail,
                        "id": key + ":" + str(now)}
                self.episodes[key] = item
            if now - item["since"] >= delay:
                issues.append({"id": item["id"], "name": name, "detail": detail})
        return issues
