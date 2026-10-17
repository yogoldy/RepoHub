import Foundation
import CryptoKit
import Darwin

// Legacy installs retain their launchd helper. Coordinated bundles own only the
// helper they start, and refuse to display a different release's HTTP service.
final class PackagedApplication {
    struct FileEntry: Decodable {
        let sha256: String?
        let link: String?
    }
    struct Release: Decodable {
        let schema: Int
        let source_revision: String
        let version: String
        let build: String
        let bundle_id: String
        let files: [String: FileEntry]
    }
    enum Failure: Error { case packageInvalid, configurationInvalid, helperUnavailable }

    let bundle: Bundle
    let release: Release
    let resources: URL
    let stateDirectory: URL
    let configURL: URL
    let address: URL
    let testMode: Bool
    var helper: Process?
    private var logHandle: FileHandle?

    static var enabled: Bool { Bundle.main.object(forInfoDictionaryKey: "RepoHubPackaged") as? Bool == true }

    init(bundle: Bundle = .main) throws {
        self.bundle = bundle
        guard let resources = bundle.resourceURL else { throw Failure.packageInvalid }
        self.resources = resources
        release = try Self.verify(resources: resources, bundle: bundle)
        testMode = bundle.object(forInfoDictionaryKey: "RepoHubTestMode") as? Bool == true
        let home = FileManager.default.homeDirectoryForCurrentUser
        stateDirectory = testMode
            ? home.appendingPathComponent("Library/Application Support/RepoHub Tests/" + release.bundle_id)
            : home.appendingPathComponent("Library/Application Support/RepoHub")
        configURL = stateDirectory.appendingPathComponent("config.json")
        let data = try Data(contentsOf: configURL)
        guard let config = try JSONSerialization.jsonObject(with: data) as? [String: Any],
              let state = config["state_dir"] as? String,
              URL(fileURLWithPath: state).resolvingSymlinksInPath() == stateDirectory.resolvingSymlinksInPath(),
              let port = config["port"] as? Int, port > 1024, port <= 65535,
              (!testMode || port != 8767), (testMode || port == 8767) else {
            throw Failure.configurationInvalid
        }
        if testMode {
            guard release.bundle_id.hasPrefix("com.leogoldberg.repohub.test.") else {
                throw Failure.configurationInvalid
            }
            for key in ["repos_root", "backup_root"] {
                guard let path = config[key] as? String,
                      URL(fileURLWithPath: path).resolvingSymlinksInPath().path.hasPrefix(
                        stateDirectory.resolvingSymlinksInPath().path + "/") else {
                    throw Failure.configurationInvalid
                }
            }
        }
        address = URL(string: "http://127.0.0.1:\(port)/")!
    }

    static func verify(resources: URL, bundle: Bundle) throws -> Release {
        let release = try JSONDecoder().decode(Release.self, from: Data(contentsOf: resources.appendingPathComponent("release.json")))
        guard release.schema == 1, release.bundle_id == bundle.bundleIdentifier,
              release.build == bundle.object(forInfoDictionaryKey: "CFBundleVersion") as? String,
              release.version == bundle.object(forInfoDictionaryKey: "CFBundleShortVersionString") as? String,
              !release.files.isEmpty else { throw Failure.packageInvalid }
        let root = resources.resolvingSymlinksInPath().path + "/"
        var observed = Set<String>()
        guard let enumerator = FileManager.default.enumerator(
            at: resources, includingPropertiesForKeys: [.isRegularFileKey, .isSymbolicLinkKey]) else {
            throw Failure.packageInvalid
        }
        for case let path as URL in enumerator {
            let relative = String(path.path.dropFirst(resources.path.count + 1))
            let values = try path.resourceValues(forKeys: [.isRegularFileKey, .isSymbolicLinkKey])
            if values.isSymbolicLink == true {
                enumerator.skipDescendants()
                guard path.resolvingSymlinksInPath().path.hasPrefix(root),
                      let expected = release.files[relative], expected.sha256 == nil,
                      expected.link == (try FileManager.default.destinationOfSymbolicLink(atPath: path.path)) else {
                    throw Failure.packageInvalid
                }
                observed.insert(relative)
            } else if values.isRegularFile == true && relative != "release.json" {
                guard let expected = release.files[relative], expected.link == nil else { throw Failure.packageInvalid }
                let digest = SHA256.hash(data: try Data(contentsOf: path, options: .mappedIfSafe))
                    .map { String(format: "%02x", $0) }.joined()
                guard expected.sha256 == digest else { throw Failure.packageInvalid }
                observed.insert(relative)
            }
        }
        guard observed == Set(release.files.keys) else { throw Failure.packageInvalid }
        return release
    }

    func matches(_ status: [String: Any]) -> Bool {
        guard let identity = status["application_release"] as? [String: String] else { return false }
        return identity["source_revision"] == release.source_revision
            && identity["build"] == release.build && identity["bundle_id"] == release.bundle_id
    }

    func startHelper() throws {
        guard let executable = bundle.executableURL else { throw Failure.packageInvalid }
        let log = stateDirectory.appendingPathComponent("packaged-helper.log")
        if !FileManager.default.fileExists(atPath: log.path) {
            FileManager.default.createFile(atPath: log.path, contents: nil, attributes: [.posixPermissions: 0o600])
        }
        logHandle = try FileHandle(forWritingTo: log)
        try logHandle?.seekToEnd()
        let process = Process()
        process.executableURL = executable
        process.arguments = ["--bundled-helper"]
        process.standardOutput = logHandle
        process.standardError = logHandle
        try process.run()
        helper = process
    }

    func stopHelper() {
        guard let helper = helper, helper.isRunning else { return }
        helper.terminate()
        // The helper has no shutdown work once the backup-idle guard has passed.
        helper.waitUntilExit()
        try? logHandle?.close()
        self.helper = nil
    }

    func runHelper() -> Int32 {
        let python = resources.appendingPathComponent("python/bin/python3")
        let script = resources.appendingPathComponent("runtime/repohub.py")
        let command = [python.path, "-E", "-s", "-B", script.path, "--config", configURL.path, "--bundled"]
        let copied = command.map { strdup($0) }
        guard copied.allSatisfy({ $0 != nil }) else { return 71 }
        defer { copied.forEach { free($0) } }
        var argv: [UnsafeMutablePointer<CChar>?] = copied + [nil]
        _ = python.path.withCString { executable in
            argv.withUnsafeMutableBufferPointer { execv(executable, $0.baseAddress!) }
        }
        return 74
    }
}
