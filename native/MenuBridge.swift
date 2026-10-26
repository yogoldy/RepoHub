import Foundation

enum MenuAction: String {
    case requestNotifications, notificationSettings, privacySettings, loginSettings, openBackups, openRepo, toggleNotifications, connectGitHub, chooseRepoHome, chooseRepoFolders, chooseBackupDestination, chooseDiscoveryParent, openSetup, closeSetup, checkForUpdates, getMenuAppearance, saveMenuAppearance, getUpdateChannel, saveUpdateChannel, quit
}

enum MenuBridge {
    // Foundation may rewrite /private/tmp to /tmp on macOS. Match the helper's
    // real filesystem spelling so a picked alias cannot duplicate a saved path.
    static func canonicalSourcePath(_ url: URL) -> String {
        guard let resolved = realpath(url.path, nil) else {
            return url.resolvingSymlinksInPath().path
        }
        defer { free(resolved) }
        return String(cString: resolved)
    }

    // Only the exact top-level menu page gets fixed actions. Repo IDs are resolved
    // from fresh helper status; page-supplied paths/URLs/commands are never accepted.
    static func action(body: Any, frameURL: URL?, isMainFrame: Bool, expectedPort: Int = 8767,
                       expectedPage: String = "/menu.html") -> MenuAction? {
        guard isMainFrame, let url = frameURL, url.scheme == "http",
              ["/menu.html", "/setup.html"].contains(expectedPage),
              url.host == "127.0.0.1", url.port == expectedPort, url.path == expectedPage,
              let payload = body as? [String: Any], let raw = payload["action"] as? String,
              let action = MenuAction(rawValue: raw) else { return nil }
        if expectedPage == "/setup.html" {
            let permitted: Set<MenuAction> = [.chooseRepoHome, .chooseRepoFolders, .chooseBackupDestination,
                .chooseDiscoveryParent, .privacySettings, .notificationSettings, .requestNotifications,
                .loginSettings, .closeSetup, .quit]
            guard permitted.contains(action) else { return nil }
        }
        if action == .openRepo {
            guard Set(payload.keys) == ["action", "repo_id"], let id = payload["repo_id"] as? String,
                  id.range(of: "^[a-zA-Z0-9_-]{1,128}$", options: .regularExpression) != nil else { return nil }
        } else if [.chooseRepoHome, .chooseRepoFolders, .chooseBackupDestination, .chooseDiscoveryParent].contains(action) {
            guard Set(payload.keys) == ["action", "request_id"], let id = payload["request_id"] as? String,
                  id.range(of: "^[a-f0-9]{24}$", options: .regularExpression) != nil else { return nil }
        } else if action == .getUpdateChannel || action == .saveUpdateChannel {
            let keys: Set<String> = action == .getUpdateChannel
                ? ["action", "request_id"] : ["action", "request_id", "channel", "revision"]
            guard Set(payload.keys) == keys, let id = payload["request_id"] as? String,
                  id.range(of: "^[a-f0-9]{24}$", options: .regularExpression) != nil else { return nil }
            if action == .saveUpdateChannel {
                guard let channel = payload["channel"] as? String,
                      ["stable", "dev"].contains(channel),
                      let revision = payload["revision"] as? String,
                      revision == "initial" || UUID(uuidString: revision) != nil else { return nil }
            }
        } else if action == .getMenuAppearance || action == .saveMenuAppearance {
            let keys: Set<String> = action == .getMenuAppearance
                ? ["action", "request_id"] : ["action", "request_id", "mode", "revision"]
            guard Set(payload.keys) == keys, let id = payload["request_id"] as? String,
                  id.range(of: "^[a-f0-9]{24}$", options: .regularExpression) != nil else { return nil }
            if action == .saveMenuAppearance {
                guard let mode = payload["mode"] as? String, MenuBarCountMode(rawValue: mode) != nil,
                      let revision = payload["revision"] as? String,
                      MenuBarCountMode(rawValue: revision) != nil else { return nil }
            }
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
                  canonicalSourcePath(item) == path else { return nil }
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

    static func backupDirectoryURL(status: [String: Any]) -> URL? {
        guard let setup = status["setup"] as? [String: Any], setup["configured"] as? Bool == true,
              let path = status["backup_root"] as? String,
              path.hasPrefix("/"), !path.contains("\0") else { return nil }
        let item = URL(fileURLWithPath: path)
        // The helper owns destination selection. Never substitute the old default,
        // accept a page-supplied path, or follow a redirected/unavailable directory.
        guard canonicalSourcePath(item) == path,
              let values = try? item.resourceValues(forKeys: [.isDirectoryKey, .isSymbolicLinkKey]),
              values.isDirectory == true, values.isSymbolicLink != true else { return nil }
        return item
    }
}
