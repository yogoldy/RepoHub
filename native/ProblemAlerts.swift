import Foundation

enum ProblemAlerts {
    // Once per persisted problem episode, grouped, with a 30-minute cooldown.
    static func pending(_ problems: [[String: Any]], seen: Set<String>, lastNotice: Double, now: Double) -> [[String: Any]] {
        guard now - lastNotice >= 1800 else { return [] }
        return problems.filter { problem in
            guard let id = problem["id"] as? String, problem["name"] is String,
                  problem["detail"] is String else { return false }
            return !seen.contains(id)
        }
    }
}
