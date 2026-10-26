import Foundation
import CryptoKit

// Public verification only. This utility never accepts or loads a private key.
@main enum VerifyUpdate {
    static func main() {
        let args = CommandLine.arguments
        guard args.count == 4,
              let key = Data(base64Encoded: args[1]), key.count == 32,
              let signature = Data(base64Encoded: args[2]), signature.count == 64,
              let publicKey = try? Curve25519.Signing.PublicKey(rawRepresentation: key),
              let archive = try? Data(contentsOf: URL(fileURLWithPath: args[3])),
              publicKey.isValidSignature(signature, for: archive) else { exit(1) }
    }
}
