import Foundation
import Security

// Developer tooling only. This file is not part of the distributed app.
struct PublisherKeychain {
    static let service = "com.leogoldberg.repohub.dev-publisher"
    static let account = "release-credentials-v1"
    static let maximumBytes = 131_072
    let isolatedKeychain: SecKeychain?

    static func readPayload(from handle: FileHandle) throws -> Data {
        var data = Data()
        while let chunk = try handle.read(upToCount: 8192), !chunk.isEmpty {
            data.append(chunk)
            guard data.count <= maximumBytes else { throw Failure.invalidData }
        }
        guard !data.isEmpty else { throw Failure.invalidData }
        return data
    }

    init(isolatedKeychain: SecKeychain? = nil) {
        self.isolatedKeychain = isolatedKeychain
    }

    enum Failure: Error {
        case unavailable, cancelledOrLocked, alreadyConfigured, invalidData
    }

    private func requireSuccess(_ status: OSStatus) throws {
        if status == errSecDuplicateItem { throw Failure.alreadyConfigured }
        if [errSecUserCanceled, errSecAuthFailed, errSecInteractionNotAllowed].contains(status) {
            throw Failure.cancelledOrLocked
        }
        if status != errSecSuccess { throw Failure.unavailable }
    }

    private func query() -> [String: Any] {
        var result: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: Self.service,
            kSecAttrAccount as String: Self.account,
        ]
        if let keychain = isolatedKeychain {
            result[kSecMatchSearchList as String] = [keychain]
        }
        return result
    }

    func contains() throws -> Bool {
        var request = query()
        request[kSecReturnAttributes as String] = true
        var result: CFTypeRef?
        let status = SecItemCopyMatching(request as CFDictionary, &result)
        if status == errSecItemNotFound { return false }
        try requireSuccess(status)
        return true
    }

    func save(_ data: Data) throws {
        guard !data.isEmpty, data.count <= Self.maximumBytes else { throw Failure.invalidData }
        var request = query()
        request.removeValue(forKey: kSecMatchSearchList as String)
        if let keychain = isolatedKeychain {
            request[kSecUseKeychain as String] = keychain
        }
        // The classic macOS Keychain API supports an explicit trusted-code ACL
        // for this local command-line helper. Never allow every application (-A).
        var trusted: SecTrustedApplication?
        try requireSuccess(SecTrustedApplicationCreateFromPath(nil, &trusted))
        guard let trusted = trusted else { throw Failure.unavailable }
        var access: SecAccess?
        try requireSuccess(SecAccessCreate("RepoHub local Dev publishing" as CFString,
                                          [trusted] as CFArray, &access))
        guard let access = access else { throw Failure.unavailable }
        request[kSecAttrAccess as String] = access
        request[kSecAttrLabel as String] = "RepoHub local Dev signing credentials"
        request[kSecValueData as String] = data
        try requireSuccess(SecItemAdd(request as CFDictionary, nil))
    }

    func load(allowInteraction: Bool = true) throws -> Data {
        var request = query()
        request[kSecReturnData as String] = true
        request[kSecMatchLimit as String] = kSecMatchLimitOne
        if !allowInteraction {
            request[kSecUseAuthenticationUI as String] = kSecUseAuthenticationUIFail
        }
        var result: CFTypeRef?
        try requireSuccess(SecItemCopyMatching(request as CFDictionary, &result))
        guard let data = result as? Data, !data.isEmpty, data.count <= Self.maximumBytes else {
            throw Failure.invalidData
        }
        return data
    }
}
