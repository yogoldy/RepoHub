import Foundation

enum MenuAction: String {
    case openBackups, toggleNotifications, quit
}

enum MenuBridge {
    // Only the app's exact top-level menu page gets these three fixed actions.
    // No URLs, paths, shell commands or arbitrary filesystem writes are accepted.
    static func action(body: Any, frameURL: URL?, isMainFrame: Bool) -> MenuAction? {
        guard isMainFrame, let url = frameURL, url.scheme == "http",
              url.host == "127.0.0.1", url.port == 8767, url.path == "/menu.html",
              let payload = body as? [String: Any], payload.count == 1,
              let raw = payload["action"] as? String else { return nil }
        return MenuAction(rawValue: raw)
    }
}
