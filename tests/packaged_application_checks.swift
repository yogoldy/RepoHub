import Foundation
import CryptoKit

@main enum Checks {
    static func main() throws {
        let root = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".app")
        defer { try? FileManager.default.removeItem(at: root) }
        let contents = root.appendingPathComponent("Contents")
        let resources = contents.appendingPathComponent("Resources")
        try FileManager.default.createDirectory(at: resources, withIntermediateDirectories: true)
        let info = ["CFBundleIdentifier": "com.leogoldberg.repohub.test.integrity",
                    "CFBundleVersion": "100", "CFBundleShortVersionString": "0.2.0"]
        let infoData = try PropertyListSerialization.data(fromPropertyList: info, format: .xml, options: 0)
        try infoData.write(to: contents.appendingPathComponent("Info.plist"))
        let data = Data("original helper".utf8)
        let helper = resources.appendingPathComponent("helper.py")
        try data.write(to: helper)
        let digest = SHA256.hash(data: data).map { String(format: "%02x", $0) }.joined()
        let manifest: [String: Any] = ["schema": 1, "source_revision": String(repeating: "a", count: 40),
            "build": "100", "version": "0.2.0", "bundle_id": info["CFBundleIdentifier"]!,
            "files": ["helper.py": ["sha256": digest]]]
        try JSONSerialization.data(withJSONObject: manifest).write(to: resources.appendingPathComponent("release.json"))
        let bundle = Bundle(url: root)!
        _ = try PackagedApplication.verify(resources: resources, bundle: bundle)
        func rejected() {
            do {
                _ = try PackagedApplication.verify(resources: resources, bundle: bundle)
                fatalError("A mixed package was accepted")
            } catch {}
        }
        try Data("changed".utf8).write(to: helper)
        rejected()
        try data.write(to: helper)
        let extra = resources.appendingPathComponent("unexpected.py")
        try Data("foreign".utf8).write(to: extra)
        rejected()
        try FileManager.default.removeItem(at: extra)
        try FileManager.default.removeItem(at: helper)
        rejected()
        try FileManager.default.createSymbolicLink(at: helper, withDestinationURL: URL(fileURLWithPath: "/etc/passwd"))
        rejected()
        print("Native package identity and altered/missing/foreign/escaping-resource checks passed")
    }
}
