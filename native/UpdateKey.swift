import Foundation
import CryptoKit
import Darwin

// A private seed stays in its protected file. Only a match result leaves this tool.
@main enum UpdateKey {
    static func main() {
        guard CommandLine.arguments.count == 3 else { exit(64) }
        do {
            let encoded = try String(contentsOfFile: CommandLine.arguments[1], encoding: .utf8)
                .trimmingCharacters(in: .whitespacesAndNewlines)
            guard let seed = Data(base64Encoded: encoded), seed.count == 32 else { exit(78) }
            let key = try Curve25519.Signing.PrivateKey(rawRepresentation: seed)
            guard key.publicKey.rawRepresentation.base64EncodedString() == CommandLine.arguments[2] else { exit(78) }
        } catch { exit(78) }
    }
}
