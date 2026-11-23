import Foundation

// Checks the login-item decisions and the launch-agent detection. Registering with macOS
// itself needs a real installed app, so that part is covered by live acceptance.
@main struct LoginItemChecks {
    static func main() throws {
        // Register once, only after setup, and never again once handled.
        precondition(LoginItemPolicy.action(setupComplete: true, handled: false, state: .notRegistered) == .register)
        precondition(LoginItemPolicy.action(setupComplete: false, handled: false, state: .notRegistered) == .none)
        precondition(LoginItemPolicy.action(setupComplete: true, handled: true, state: .notRegistered) == .none,
                     "A user who turned it off must stay off")
        for state in [LoginItemState.enabled, .requiresApproval, .legacyAgent, .unavailable] {
            precondition(LoginItemPolicy.action(setupComplete: true, handled: false, state: state) == .none)
        }

        // An existing launch agent for this app counts; unrelated or disabled ones do not.
        let folder = FileManager.default.temporaryDirectory.appendingPathComponent("login-item-" + UUID().uuidString)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: folder) }
        let bundle = "com.example.repohub"
        precondition(!LoginItem.legacyAgentPresent(bundleIdentifier: bundle, agentsDirectory: folder))
        func agent(_ name: String, label: String, runAtLoad: Bool) throws {
            let plist: [String: Any] = ["Label": label, "RunAtLoad": runAtLoad, "ProgramArguments": ["/bin/true"]]
            try (plist as NSDictionary).write(to: folder.appendingPathComponent(name))
        }
        try agent("com.other.tool.plist", label: "com.other.tool", runAtLoad: true)
        precondition(!LoginItem.legacyAgentPresent(bundleIdentifier: bundle, agentsDirectory: folder))
        try agent(bundle + ".app.plist", label: bundle + ".app", runAtLoad: false)
        precondition(!LoginItem.legacyAgentPresent(bundleIdentifier: bundle, agentsDirectory: folder),
                     "An agent that does not run at load does not start the app at login")
        try agent(bundle + ".app.plist", label: bundle + ".app", runAtLoad: true)
        precondition(LoginItem.legacyAgentPresent(bundleIdentifier: bundle, agentsDirectory: folder))
        precondition(!LoginItem.legacyAgentPresent(bundleIdentifier: bundle,
                                                   agentsDirectory: folder.appendingPathComponent("missing")))

        // The state file the helper reads.
        LoginItem.writeState(.requiresApproval, to: folder)
        let data = try Data(contentsOf: folder.appendingPathComponent("login-item.json"))
        let record = try JSONSerialization.jsonObject(with: data) as? [String: String]
        precondition(record?["state"] == "requiresApproval" && record?["checked_at"] != nil)
        print("Login item decision, launch-agent and state-file checks passed")
    }
}
