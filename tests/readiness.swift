import Foundation

@main struct ReadinessTests {
    static func main() {
        let archive = "/backups/current.tar.gz"
        let good: [String: Any] = ["name":"Example", "needs_backup":false,
            "last_backup":["archive":archive, "sha256":"abc"],
            "verification":["state":"matched", "archive":archive],
            "cloud":["state":"uploaded", "archive":archive]]
        let ready = BackupReadiness.pendingNotifications([good], seen: [])
        precondition(ready.count == 1)
        precondition(BackupReadiness.pendingNotifications([good], seen: [ready[0].key]).isEmpty)
        for cloud in [["state":"uploading", "percent":100, "archive":archive] as [String:Any],
                      ["state":"pending", "percent":100, "archive":archive],
                      ["state":"uploaded", "archive":"/backups/old.tar.gz"],
                      ["state":"unknown", "archive":archive]] {
            var repo = good; repo["cloud"] = cloud
            precondition(BackupReadiness.pendingNotifications([repo], seen: []).isEmpty)
        }
        var changed = good; changed["needs_backup"] = true
        precondition(BackupReadiness.pendingNotifications([changed], seen: []).isEmpty)
        changed = good; changed["verification"] = ["state":"matched", "archive":"/backups/old.tar.gz"]
        precondition(BackupReadiness.pendingNotifications([changed], seen: []).isEmpty)
        print("8 notification-readiness checks passed")
    }
}
