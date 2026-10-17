import Foundation
import JavaScriptCore

@main struct MenuAppearanceChecks {
    static func main() throws {
        if CommandLine.arguments.count == 3 && CommandLine.arguments[1] == "--read-preference" {
            let defaults = UserDefaults(suiteName: CommandLine.arguments[2])!
            print(MenuAppearance.saved(in: defaults).rawValue)
            return
        }
        let suite = "com.leogoldberg.repohub.test.appearance." + UUID().uuidString
        let defaults = UserDefaults(suiteName: suite)!
        defer { defaults.removePersistentDomain(forName: suite) }
        precondition(MenuAppearance.saved(in: defaults) == .pending)
        precondition(MenuAppearance.save(mode: "edits", revision: "pending", in: defaults) == "saved")
        precondition(MenuAppearance.saved(in: UserDefaults(suiteName: suite)!) == .edits)
        let child = Process()
        let pipe = Pipe()
        child.executableURL = URL(fileURLWithPath: CommandLine.arguments[0])
        child.arguments = ["--read-preference", suite]
        child.standardOutput = pipe
        try child.run()
        let readback = pipe.fileHandleForReading.readDataToEndOfFile()
        child.waitUntilExit()
        precondition(child.terminationStatus == 0)
        precondition(String(data: readback, encoding: .utf8)?.trimmingCharacters(in: .whitespacesAndNewlines) == "edits")
        precondition(MenuAppearance.save(mode: "none", revision: "pending", in: defaults) == "conflict")
        precondition(MenuAppearance.saved(in: defaults) == .edits)
        precondition(MenuAppearance.save(mode: "outside", revision: "edits", in: defaults) == "invalid")
        precondition(MenuAppearance.save(mode: "none", revision: "edits", in: defaults) == "saved")
        let url = URL(string: "http://127.0.0.1:8767/menu.html")!
        for action in ["getMenuAppearance", "saveMenuAppearance"] {
            var body: [String: Any] = ["action": action, "request_id": String(repeating: "a", count: 24)]
            if action == "saveMenuAppearance" {
                body["mode"] = "edits"
                body["revision"] = "pending"
            }
            precondition(MenuBridge.action(body: body, frameURL: url, isMainFrame: true)?.rawValue == action)
            precondition(MenuBridge.action(body: body, frameURL: url, isMainFrame: false) == nil)
            precondition(MenuBridge.action(body: body, frameURL: URL(string: "http://127.0.0.1:8772/menu.html"), isMainFrame: true) == nil)
            body["path"] = "/outside"
            precondition(MenuBridge.action(body: body, frameURL: url, isMainFrame: true) == nil)
            body.removeValue(forKey: "path")
            body["request_id"] = "invalid"
            precondition(MenuBridge.action(body: body, frameURL: url, isMainFrame: true) == nil)
        }
        for bad: Any in [true, -1, 5000, 1.5, "1"] {
            precondition(MenuAppearance.rendered(["mode": "pending", "count": bad,
                "title": " 1", "tooltip": "RepoHub: test"], mode: .pending) == nil)
        }
        for bad: Any in [true, "outside", "", ["pending"]] {
            let body: [String: Any] = ["action": "saveMenuAppearance",
                "request_id": String(repeating: "a", count: 24), "mode": bad, "revision": "pending"]
            precondition(MenuBridge.action(body: body, frameURL: url, isMainFrame: true) == nil)
        }
        precondition(MenuAppearance.rendered(["mode": "none", "count": 1,
            "title": " 1", "tooltip": "RepoHub: test"], mode: .none) == nil)
        precondition(MenuAppearance.rendered(["mode": "pending", "count": 1,
            "title": " 2", "tooltip": "RepoHub: test"], mode: .pending) == nil)

        let context = JSContext()!
        let source = try String(contentsOfFile: CommandLine.arguments[1], encoding: .utf8)
        context.evaluateScript(source)
        precondition(context.exception == nil)
        let input = FileHandle.standardInput.readDataToEndOfFile()
        let fixtures = try JSONSerialization.jsonObject(with: input) as! [[String: Any]]
        var results = [[String: Any]]()
        for fixture in fixtures {
            let status = fixture["status"] as! [String: Any]
            let mode = MenuBarCountMode(rawValue: fixture["mode"] as! String)!
            let expression = MenuAppearance.expression(status: status, mode: mode)!
            let value = context.evaluateScript(expression)!.toDictionary() as! [String: Any]
            precondition(context.exception == nil)
            precondition(MenuAppearance.rendered(value, mode: mode) != nil)
            results.append(value)
        }
        let output = try JSONSerialization.data(withJSONObject: results, options: [.sortedKeys])
        FileHandle.standardOutput.write(output)
    }
}
