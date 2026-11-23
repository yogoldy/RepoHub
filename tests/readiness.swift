import Foundation

@main struct ReadinessTests {
    static func main() {
        precondition(BackupReadiness.permissionRequest(saved: nil, inFlight: false) == "not_requested")
        precondition(BackupReadiness.permissionRequest(saved: "pending", inFlight: false) == "failed")
        precondition(BackupReadiness.permissionRequest(saved: "completed", inFlight: false) == "completed")
        precondition(BackupReadiness.permissionRequest(saved: "failed", inFlight: true) == "pending")
        precondition(BackupReadiness.permissionRequest(saved: "arbitrary", inFlight: false) == "not_requested")
        let archive = "/backups/current.tar.gz"
        let good: [String: Any] = ["name":"Example", "needs_backup":false, "health":["fresh":true],
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
        changed = good; changed["health"] = ["fresh":false]
        precondition(BackupReadiness.pendingNotifications([changed], seen: []).isEmpty)
        changed = good; changed.removeValue(forKey: "health")
        precondition(BackupReadiness.pendingNotifications([changed], seen: []).isEmpty)
        let problem: [String: Any] = ["id":"repo:upload:1", "name":"Example", "detail":"Upload stalled"]
        precondition(ProblemAlerts.pending([problem], seen: [], lastNotice: 0, now: 2000).count == 1)
        precondition(ProblemAlerts.pending([problem], seen: ["repo:upload:1"], lastNotice: 0, now: 2000).isEmpty)
        precondition(ProblemAlerts.pending([problem], seen: [], lastNotice: 1900, now: 2000).isEmpty)
        precondition(ProblemAlerts.pending([], seen: [], lastNotice: 0, now: 2000).isEmpty)
        precondition(ProblemAlerts.pending([["id":"bad"]], seen: [], lastNotice: 0, now: 2000).isEmpty)
        print("20 notification-readiness/problem checks passed")
    }
}
