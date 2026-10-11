import Foundation
import Darwin

// Enter through this bundle's native executable before replacing it with Python.
// execv preserves the launchd PID, exit status, environment and signal ownership.
enum HelperLaunch {
    static func valid(_ arguments: [String]) -> Bool {
        guard arguments.count == 6, arguments[1] == "--helper",
              arguments[4] == "--config" else { return false }
        let paths = [arguments[2], arguments[3], arguments[5]]
        return paths.allSatisfy { $0.hasPrefix("/") && !$0.contains("\0") }
            && URL(fileURLWithPath: arguments[3]).lastPathComponent == "repohub.py"
    }

    static func run(_ arguments: [String]) -> Int32? {
        guard arguments.dropFirst().first == "--helper" else { return nil }
        guard valid(arguments) else { return 64 }
        let command = Array(arguments.dropFirst(2))
        let copied = command.map { strdup($0) }
        guard copied.allSatisfy({ $0 != nil }) else {
            copied.forEach { free($0) }
            return 71
        }
        var argv: [UnsafeMutablePointer<CChar>?] = copied + [nil]
        _ = command[0].withCString { executable in
            argv.withUnsafeMutableBufferPointer { execv(executable, $0.baseAddress!) }
        }
        let code = errno
        copied.forEach { free($0) }
        // Paths and configuration contents are not included in this message.
        FileHandle.standardError.write(Data("Helper launch failed (errno \(code)).\n".utf8))
        return 74
    }
}
