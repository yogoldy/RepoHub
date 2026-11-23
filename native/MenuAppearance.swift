import Foundation
import CoreFoundation

enum MenuBarCountMode: String, CaseIterable {
    case pending, edits, none
}

enum MenuAppearance {
    static let preferenceKey = "menuBarCountMode"

    static func saved(in defaults: UserDefaults = .standard) -> MenuBarCountMode {
        MenuBarCountMode(rawValue: defaults.string(forKey: preferenceKey) ?? "") ?? .pending
    }

    static func settings(in defaults: UserDefaults = .standard) -> [String: Any] {
        let mode = saved(in: defaults).rawValue
        return ["mode": mode, "revision": mode]
    }

    static func save(mode: String, revision: String, in defaults: UserDefaults = .standard) -> String {
        guard let selected = MenuBarCountMode(rawValue: mode) else { return "invalid" }
        guard saved(in: defaults).rawValue == revision else { return "conflict" }
        defaults.set(selected.rawValue, forKey: preferenceKey)
        return "saved"
    }

    // Run the shipped presentation policy in the owned WebKit page. Swift never
    // decides whether a repository has edits, is pending or is backed up.
    static func expression(status: [String: Any], mode: MenuBarCountMode) -> String? {
        guard let data = try? JSONSerialization.data(withJSONObject: status),
              let json = String(data: data, encoding: .utf8) else { return nil }
        return "RepoStatus.menuBar(" + json + ", '" + mode.rawValue + "')"
    }

    static func rendered(_ value: Any?, mode: MenuBarCountMode) -> (title: String, tooltip: String)? {
        guard let summary = value as? [String: Any],
              Set(summary.keys) == ["mode", "count", "title", "tooltip"],
              summary["mode"] as? String == mode.rawValue,
              let count = summary["count"] as? NSNumber,
              CFGetTypeID(count) != CFBooleanGetTypeID(),
              count.doubleValue == Double(count.intValue), (0...4096).contains(count.intValue),
              mode != .none || count.intValue == 0,
              let title = summary["title"] as? String,
              ["", " !", " ↻", " ↑", count.intValue > 0 ? " \(count.intValue)" : ""].contains(title),
              let tooltip = summary["tooltip"] as? String,
              tooltip.hasPrefix("RepoHub: "), tooltip.count <= 256 else { return nil }
        return (title, tooltip)
    }
}
