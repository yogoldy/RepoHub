import Foundation
import Security

@main enum PublisherKeychainTests {
    static func main() throws {
        precondition(SecKeychainSetUserInteractionAllowed(false) == errSecSuccess)
        let path = CommandLine.arguments[1]
        let pipe = Pipe()
        let large = Data(repeating: 120, count: 20_000)
        DispatchQueue.global().async {
            try! pipe.fileHandleForWriting.write(contentsOf: large)
            try! pipe.fileHandleForWriting.close()
        }
        let received = try PublisherKeychain.readPayload(from: pipe.fileHandleForReading)
        precondition(received == large)
        let oversized = URL(fileURLWithPath: path + ".oversized")
        try Data(repeating: 120, count: PublisherKeychain.maximumBytes + 1).write(to: oversized)
        defer { try? FileManager.default.removeItem(at: oversized) }
        let handle = try FileHandle(forReadingFrom: oversized)
        defer { try? handle.close() }
        do {
            _ = try PublisherKeychain.readPayload(from: handle)
            preconditionFailure("Oversized credential input accepted")
        } catch PublisherKeychain.Failure.invalidData { }
        let password = "synthetic-keychain-password"
        var keychain: SecKeychain?
        let created = password.withCString { pointer in
            SecKeychainCreate(path, UInt32(password.utf8.count), pointer, false, nil, &keychain)
        }
        precondition(created == errSecSuccess)
        guard let keychain = keychain else { preconditionFailure("No isolated keychain") }
        defer { SecKeychainDelete(keychain) }
        let store = PublisherKeychain(isolatedKeychain: keychain)
        let initiallyPresent = try store.contains()
        precondition(!initiallyPresent)
        let value = Data("synthetic-credentials-only".utf8)
        try store.save(value)
        let saved = try store.contains()
        precondition(saved)
        let loaded = try store.load(allowInteraction: false)
        precondition(loaded == value)
        do {
            try store.save(Data("replacement-must-not-overwrite".utf8))
            preconditionFailure("Overwrote existing credentials")
        } catch PublisherKeychain.Failure.alreadyConfigured { }
        let unchanged = try store.load(allowInteraction: false)
        precondition(unchanged == value)
        precondition(SecKeychainLock(keychain) == errSecSuccess)
        do {
            _ = try store.load(allowInteraction: false)
            preconditionFailure("Read a locked keychain")
        } catch { }
        print("Isolated Keychain: save/read, no overwrite and locked-item refusal passed")
    }
}
