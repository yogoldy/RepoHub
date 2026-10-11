import Foundation
import Darwin

@main struct HelperLaunchChecks {
    static func main() throws {
        if let code = HelperLaunch.run(CommandLine.arguments) { exit(code) }
        precondition(HelperLaunch.run(["app"]) == nil)
        let valid = ["app", "--helper", "/bin/sh", "/synthetic/repohub.py", "--config", "/synthetic/config with spaces"]
        precondition(HelperLaunch.valid(valid))
        for args in [Array(valid.dropLast()), valid + ["extra"], ["app", "--helper", "relative", "/synthetic/repohub.py", "--config", "/config"], ["app", "--helper", "/bin/sh", "/wrong.py", "--config", "/config"], ["app", "--helper", "/bin/sh", "/repohub.py", "--other", "/config"]] {
            precondition(!HelperLaunch.valid(args))
            precondition(HelperLaunch.run(args) == 64)
        }
        let files = FileManager.default
        let root = files.temporaryDirectory.appendingPathComponent("repohub-helper-exec-" + UUID().uuidString)
        try files.createDirectory(at: root, withIntermediateDirectories: true)
        defer { try? files.removeItem(at: root) }
        let script = root.appendingPathComponent("repohub.py")
        let config = root.appendingPathComponent("config with spaces")
        func child(_ interpreter: String = "/bin/sh") throws -> Process {
            let p = Process()
            p.executableURL = URL(fileURLWithPath: CommandLine.arguments[0])
            p.arguments = ["--helper", interpreter, script.path, "--config", config.path]
            try p.run()
            return p
        }
        try Data("test \"$1\" = --config || exit 90\necho \"$HELPER_TEST\" > \"$2\"\nexit 23\n".utf8).write(to: script)
        setenv("HELPER_TEST", "inherited", 1)
        let exitChild = try child(); exitChild.waitUntilExit()
        precondition(exitChild.terminationStatus == 23)
        let inherited = try String(contentsOf: config, encoding: .utf8)
        precondition(inherited == "inherited\n")
        let missing = try child(root.appendingPathComponent("missing-python").path); missing.waitUntilExit()
        precondition(missing.terminationStatus == 74)
        try files.removeItem(at: config)
        try Data("echo $$ > \"$2\"\nexec /bin/sleep 30\n".utf8).write(to: script)
        let signalChild = try child()
        defer { if signalChild.isRunning { signalChild.terminate() } }
        let deadline = Date().addingTimeInterval(5)
        while !files.fileExists(atPath: config.path) && Date() < deadline { Thread.sleep(forTimeInterval: 0.01) }
        precondition(files.fileExists(atPath: config.path))
        let observedPID = try String(contentsOf: config, encoding: .utf8).trimmingCharacters(in: .whitespacesAndNewlines)
        precondition(observedPID == String(signalChild.processIdentifier))
        signalChild.terminate(); signalChild.waitUntilExit()
        precondition(signalChild.terminationReason == .uncaughtSignal && signalChild.terminationStatus == SIGTERM)
        print("Native helper argument, environment, exit, failure and signal ownership checks passed")
    }
}
