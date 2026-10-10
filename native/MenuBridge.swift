import Foundation

enum MenuAction: String {
    case requestNotifications, notificationSettings, privacySettings, loginSettings, openBackups, openRepo, toggleNotifications, connectGitHub, chooseRepoHome, chooseRepoFolders, quit
}

enum MenuBridge {
    // Only the exact top-level menu page gets fixed actions. Repo IDs are resolved
    // from fresh helper status; page-supplied paths/URLs/commands are never accepted.
    static func action(body: Any, frameURL: URL?, isMainFrame: Bool) -> MenuAction? {
        guard isMainFrame, let url = frameURL, url.scheme == "http",
              url.host == "127.0.0.1", url.port == 8767, url.path == "/menu.html",
              let payload = body as? [String: Any], let raw = payload["action"] as? String,
              let action = MenuAction(rawValue: raw) else { return nil }
        if action == .openRepo {
            guard Set(payload.keys) == ["action", "repo_id"], let id = payload["repo_id"] as? String,
                  id.range(of: "^[a-zA-Z0-9_-]{1,128}$", options: .regularExpression) != nil else { return nil }
        } else if action == .chooseRepoHome || action == .chooseRepoFolders {
            guard Set(payload.keys) == ["action", "request_id"], let id = payload["request_id"] as? String,
                  id.range(of: "^[a-f0-9]{24}$", options: .regularExpression) != nil else { return nil }
        } else if payload.count != 1 { return nil }
        return action
    }

    static func isReportIssueURL(_ url: URL) -> Bool {
        url.scheme == "https" && url.host == "github.com" && url.port == nil && url.user == nil && url.password == nil
            && url.query == nil && url.fragment == nil
            && url.path.range(of: "^/yogoldy/RepoHub/issues/[1-9][0-9]*$", options: .regularExpression) != nil
    }

    static func repositoryURL(id: String, status: [String: Any]) -> URL? {
        guard let repos = status["repos"] as? [[String: Any]],
              let repo = repos.first(where: { $0["id"] as? String == id }),
              let path = repo["path"] as? String, path.hasPrefix("/"),
              let name = repo["name"] as? String, !name.isEmpty,
              name != ".", name != "..", !name.contains("/") else { return nil }
        let item = URL(fileURLWithPath: path).standardizedFileURL
        if status["workspace_sources"] != nil {
            // Registry-backed status resolves exact approved IDs; arbitrary
            // paths from web messages are still never accepted.
            guard let sources = status["workspace_sources"] as? [[String: Any]] else { return nil }
            let approved = sources.filter { $0["id"] as? String == id }
            guard approved.count == 1, approved[0]["path"] as? String == path,
                  item.resolvingSymlinksInPath() == item else { return nil }
        } else {
            // Compatibility with the installed single-root helper.
            guard let rootPath = status["repos_root"] as? String, rootPath.hasPrefix("/") else { return nil }
            let root = URL(fileURLWithPath: rootPath).standardizedFileURL
            guard item == root.appendingPathComponent(name).standardizedFileURL,
                  item.resolvingSymlinksInPath().deletingLastPathComponent() == root.resolvingSymlinksInPath() else { return nil }
        }
        guard let values = try? item.resourceValues(forKeys: [.isDirectoryKey, .isSymbolicLinkKey]),
              values.isDirectory == true, values.isSymbolicLink != true else { return nil }
        return item
    }
}
