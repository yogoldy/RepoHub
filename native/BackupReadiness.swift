import Foundation

struct ReadyBackup {
    let name: String
    let key: String
}

enum BackupReadiness {
    // The receipt must belong to the exact locally verified archive. Neither a
    // progress percentage nor an old archive's acknowledgement is sufficient.
    static func pendingNotifications(_ repos: [[String: Any]], seen: Set<String>) -> [ReadyBackup] {
        repos.compactMap { repo in
            guard repo["needs_backup"] as? Bool == false, repo["error"] == nil,
                  (repo["health"] as? [String: Any])?["fresh"] as? Bool == true,
                  let backup = repo["last_backup"] as? [String: Any],
                  let archive = backup["archive"] as? String, let hash = backup["sha256"] as? String,
                  let verification = repo["verification"] as? [String: Any],
                  verification["state"] as? String == "matched", verification["archive"] as? String == archive,
                  let cloud = repo["cloud"] as? [String: Any], cloud["state"] as? String == "uploaded",
                  cloud["archive"] as? String == archive else { return nil }
            let key = archive + "|" + hash
            guard !seen.contains(key) else { return nil }
            return ReadyBackup(name: repo["name"] as? String ?? "Repo", key: key)
        }
    }
}
