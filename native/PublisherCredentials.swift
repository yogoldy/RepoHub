import Foundation
import Security
import Darwin

@main enum PublisherCredentials {
    static func requireSignedHelper() throws {
        let text = "anchor apple generic and identifier \"com.leogoldberg.repohub.dev-publisher.credentials\""
            + " and certificate leaf[subject.OU] = LJM5FKB7DY"
            + " and certificate leaf[field.1.2.840.113635.100.6.1.13]"
        var requirement: SecRequirement?
        var code: SecCode?
        guard SecRequirementCreateWithString(text as CFString, [], &requirement) == errSecSuccess,
              SecCodeCopySelf([], &code) == errSecSuccess, let code = code,
              SecCodeCheckValidity(code, [], requirement) == errSecSuccess else {
            throw PublisherKeychain.Failure.unavailable
        }
    }

    static func main() {
        do {
            try requireSignedHelper()
            let store = PublisherKeychain()
            switch Array(CommandLine.arguments.dropFirst()) {
            case ["status"]:
                print(try store.contains() ? "{\"configured\":true}" : "{\"configured\":false}")
            case ["save"]:
                let data = try PublisherKeychain.readPayload(from: FileHandle.standardInput)
                try store.save(data)
                print("{\"configured\":true}")
            case ["load"]:
                // Only the developer wrapper consumes this private subprocess pipe.
                // An accidental direct Terminal invocation must not display secrets.
                guard isatty(STDOUT_FILENO) == 0 else { throw PublisherKeychain.Failure.invalidData }
                try FileHandle.standardOutput.write(contentsOf: store.load())
            default:
                throw PublisherKeychain.Failure.invalidData
            }
        } catch {
            let reason: String
            switch error {
            case PublisherKeychain.Failure.alreadyConfigured: reason = "already_configured"
            case PublisherKeychain.Failure.cancelledOrLocked: reason = "keychain_cancelled_or_locked"
            default: reason = "publisher_credentials_unavailable"
            }
            FileHandle.standardError.write(Data((reason + "\n").utf8))
            exit(1)
        }
    }
}
