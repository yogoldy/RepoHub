import AppKit
import Security

// Never accept tokens, URLs or commands from web messages. Entry is a fixed
// native action; user-entered credentials stay in this secure field/Keychain.
enum GitHubConnection {
    static let service = "com.leogoldberg.repohub.github"
    static func configure() {
        let alert = NSAlert()
        alert.messageText = "Connect GitHub reporting"
        alert.informativeText = "For the tracker owner, use a fine-grained token for yogoldy/RepoHub with Issues: read and write. Other accounts currently need a classic token with public_repo scope, which grants broader public-repository access. Paste it here. It stays in your Mac’s Keychain and is never passed to the HTML view. GitHub will show your account as the report author."
        let field = NSSecureTextField(frame: NSRect(x: 0, y: 0, width: 360, height: 24))
        field.placeholderString = "GitHub token"
        alert.accessoryView = field
        alert.addButton(withTitle: "Save connection")
        alert.addButton(withTitle: "Cancel")
        alert.addButton(withTitle: "Create token")
        alert.addButton(withTitle: "Disconnect")
        NSApp.activate(ignoringOtherApps: true)
        let choice = alert.runModal()
        let query: [String:Any] = [kSecClass as String:kSecClassGenericPassword,
                                 kSecAttrService as String:service, kSecAttrAccount as String:"github.com"]
        if choice == .alertThirdButtonReturn {
            NSWorkspace.shared.open(URL(string:"https://github.com/settings/tokens")!)
            return
        }
        if choice.rawValue == NSApplication.ModalResponse.alertFirstButtonReturn.rawValue + 3 {
            let result = SecItemDelete(query as CFDictionary)
            if result != errSecSuccess && result != errSecItemNotFound { notice("Could not remove the Keychain connection.") }
            return
        }
        guard choice == .alertFirstButtonReturn else { return }
        let token = field.stringValue.trimmingCharacters(in: .whitespacesAndNewlines)
        field.stringValue = ""
        guard !token.isEmpty, token.utf8.count <= 256,
              token.range(of:"^[A-Za-z0-9_]+$", options:.regularExpression) != nil else {
            notice("Enter a valid GitHub token, or choose Cancel."); return
        }
        let data = Data(token.utf8)
        let result = SecItemUpdate(query as CFDictionary, [kSecValueData as String:data] as CFDictionary)
        var status = result
        if result == errSecItemNotFound {
            var item = query
            item[kSecValueData as String] = data
            item[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
            status = SecItemAdd(item as CFDictionary, nil)
        }
        notice(status == errSecSuccess ? "Connection saved. In the report preview, click Check connection to verify your account before sending." : "Could not save the connection in Keychain.")
    }
    private static func notice(_ message:String) {
        let alert = NSAlert(); alert.messageText = message; alert.runModal()
    }
}
