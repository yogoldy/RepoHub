import CoreServices
import Foundation
import ServiceManagement

/// Where this app stands as a "start at login" item.
enum LoginItemState: String {
    /// Registered with macOS (System Settings > General > Login Items).
    case enabled
    /// Not registered; backups stop after a restart until the app is opened again.
    case notRegistered
    /// Registered, but macOS is waiting for the user to approve it in System Settings.
    case requiresApproval
    /// A launch agent from an earlier installation already starts this app at login.
    case legacyAgent
    /// macOS could not tell (for example a development build outside an app bundle).
    case unavailable
}

/// Decides when the app registers itself. Kept free of side effects so it can be tested.
enum LoginItemPolicy {
    enum Action { case none, register }

    /// Register once, the first time setup is complete, and never again on its own.
    /// If the user later turns the login item off in System Settings, the app respects that:
    /// `handled` stays true, so it is not switched back on.
    static func action(setupComplete: Bool, handled: Bool, state: LoginItemState) -> Action {
        guard setupComplete, !handled else { return .none }
        return state == .notRegistered ? .register : .none
    }
}

enum LoginItem {
    /// True when a launch agent for this app already exists. Registering a second login
    /// item beside it would start two copies at every login.
    static func legacyAgentPresent(bundleIdentifier: String, agentsDirectory: URL) -> Bool {
        guard let names = try? FileManager.default.contentsOfDirectory(atPath: agentsDirectory.path) else { return false }
        for name in names where name.hasPrefix(bundleIdentifier) && name.hasSuffix(".plist") {
            let url = agentsDirectory.appendingPathComponent(name)
            guard let values = try? url.resourceValues(forKeys: [.isRegularFileKey]), values.isRegularFile == true,
                  let data = try? Data(contentsOf: url), data.count < 65536,
                  let plist = (try? PropertyListSerialization.propertyList(from: data, format: nil)) as? [String: Any],
                  let label = plist["Label"] as? String, label.hasPrefix(bundleIdentifier),
                  plist["RunAtLoad"] as? Bool == true else { continue }
            return true
        }
        return false
    }

    static func currentState(bundleIdentifier: String, agentsDirectory: URL) -> LoginItemState {
        if legacyAgentPresent(bundleIdentifier: bundleIdentifier, agentsDirectory: agentsDirectory) {
            return .legacyAgent
        }
        switch SMAppService.mainApp.status {
        case .enabled: return .enabled
        case .notRegistered: return .notRegistered
        case .requiresApproval: return .requiresApproval
        default: return .unavailable
        }
    }

    static func register() throws {
        try SMAppService.mainApp.register()
    }

    /// True when macOS started this launch because the login item fired, so the app can
    /// stay quiet in the menu bar instead of opening its panel at every login.
    static func launchedAsLoginItem() -> Bool {
        guard let event = NSAppleEventManager.shared().currentAppleEvent,
              event.eventID == AEEventID(kAEOpenApplication) else { return false }
        let launchedBy = event.paramDescriptor(forKeyword: AEKeyword(keyAEPropData))?.enumCodeValue
        return launchedBy == OSType(keyAELaunchedAsLogInItem)
    }

    /// The state file the helper reads, so its readiness check reports the real login state.
    static func writeState(_ state: LoginItemState, to directory: URL) {
        let record: [String: String] = ["state": state.rawValue,
                                        "checked_at": ISO8601DateFormatter().string(from: Date())]
        guard let data = try? JSONSerialization.data(withJSONObject: record, options: [.sortedKeys]) else { return }
        try? data.write(to: directory.appendingPathComponent("login-item.json"), options: .atomic)
    }
}
