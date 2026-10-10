import AppKit
import WebKit
import UserNotifications

final class HubDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, UNUserNotificationCenterDelegate, WKScriptMessageHandler {
    var statusItem: NSStatusItem!
    let popover = NSPopover()
    var popoverWebView: WKWebView!
    var lastNotificationData: Data?
    var notificationInFlight = false
    var unavailableSince: Date?
    var notificationsEnabled: Bool { UserDefaults.standard.object(forKey: "notificationsEnabled") as? Bool ?? true }
    var polling: Timer?
    var sourcePicker: NSOpenPanel?
    let address = URL(string: "http://127.0.0.1:8767/")!

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.image = NSImage(systemSymbolName: "square.stack.3d.up", accessibilityDescription: "Repo Hub")
        statusItem.button?.setAccessibilityLabel("Repo Hub backup status")
        statusItem.button?.target = self
        statusItem.button?.action = #selector(togglePopover)
        let configuration = WKWebViewConfiguration()
        configuration.userContentController.add(self, name: "repoHub")
        let view = WKWebView(frame: NSRect(x: 0, y: 0, width: 580, height: 640), configuration: configuration)
        view.navigationDelegate = self
        view.underPageBackgroundColor = NSColor(calibratedRed: 0.063, green: 0.082, blue: 0.114, alpha: 1)
        let controller = NSViewController()
        controller.view = view
        popover.contentViewController = controller
        popover.contentSize = NSSize(width: 580, height: 640)
        popover.appearance = NSAppearance(named: .darkAqua)
        popover.behavior = .transient
        popoverWebView = view
        view.load(URLRequest(url: address.appendingPathComponent("menu.html")))
        UNUserNotificationCenter.current().delegate = self
        if notificationsEnabled { requestNotifications() }
        pollStatus()
        polling = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in self?.pollStatus() }
        if !CommandLine.arguments.contains("--background") { showPopover() }
    }

    func pollStatus() {
        updateNotificationStatus()
        var statusRequest = URLRequest(url: address.appendingPathComponent("api/status"))
        statusRequest.timeoutInterval = 8
        URLSession.shared.dataTask(with: statusRequest) { [weak self] data, _, error in
            guard let self = self else { return }
            let status = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            DispatchQueue.main.async {
                guard error == nil, let status = status else {
                    self.statusItem.button?.title = " !"
                    self.statusItem.button?.toolTip = "Repo Hub: backup helper unavailable"
                    if self.unavailableSince == nil { self.unavailableSince = Date() }
                    if let since = self.unavailableSince, Date().timeIntervalSince(since) >= 120 {
                        self.notifyProblems([["id":"helper:" + String(since.timeIntervalSince1970), "name":"Repo Hub", "detail":"The backup helper has been unavailable for two minutes."]])
                    }
                    return
                }
                self.unavailableSince = nil
                let repos = status["repos"] as? [[String: Any]] ?? []
                let backup = status["backup"] as? [String: Any] ?? [:]
                let running = backup["running"] as? Bool ?? false
                let pending = repos.filter { $0["needs_backup"] as? Bool ?? true }.count
                let errors = backup["errors"] as? [[String: Any]] ?? []
                let stale = repos.contains { ($0["health"] as? [String: Any])?["fresh"] as? Bool != true }
                let copyError = repos.contains { $0["error"] != nil || ($0["verification"] as? [String: Any])?["state"] as? String == "error" }
                let cloudError = repos.contains { ($0["cloud"] as? [String: Any])?["state"] as? String == "error" }
                let dataError = (status["data_cloud"] as? [String: Any])?["state"] as? String == "error"
                let ready = BackupReadiness.pendingNotifications(repos, seen: []).count
                self.statusItem.button?.title = running ? " ↻" : (stale || copyError || cloudError || dataError || !errors.isEmpty) ? " !" : pending > 0 ? " \(pending)" : ready < repos.count ? " ↑" : ""
                self.statusItem.button?.toolTip = "Repo Hub: \(ready) of \(repos.count) repo backups verified and uploaded"
                self.notifyProblems(status["problems"] as? [[String: Any]] ?? [])
                self.notifyReadyBackups(repos)
            }
        }.resume()
    }

    func requestNotifications() {
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { _, error in
            if let error = error { print("Notification authorization:", error.localizedDescription) }
            DispatchQueue.main.async { self.updateNotificationStatus() }
        }
    }

    func updateNotificationStatus() {
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            DispatchQueue.main.async {
                let permission: String
                switch settings.authorizationStatus {
                case .authorized, .provisional: permission = "allowed"
                case .denied: permission = "denied"
                case .notDetermined: permission = "waiting"
                default: permission = "unknown"
                }
                let status: [String: Any] = ["enabled": self.notificationsEnabled, "permission": permission]
                let path = FileManager.default.homeDirectoryForCurrentUser
                    .appendingPathComponent("Library/Application Support/RepoHub/notifications.json")
                if let data = try? JSONSerialization.data(withJSONObject: status, options: [.sortedKeys]), data != self.lastNotificationData {
                    do {
                        try data.write(to: path, options: .atomic)
                        self.lastNotificationData = data
                        self.popoverWebView.evaluateJavaScript("window.dispatchEvent(new Event('repoHubNotificationsChanged'))")
                    } catch { print("Notification preference save failed:", error.localizedDescription) }
                }
            }
        }
    }

    @objc func toggleNotifications() {
        UserDefaults.standard.set(!notificationsEnabled, forKey: "notificationsEnabled")
        if notificationsEnabled { requestNotifications() }
        updateNotificationStatus()
        pollStatus()
    }

    func notifyReadyBackups(_ repos: [[String: Any]]) {
        guard notificationsEnabled, !notificationInFlight else { return }
        let seen = Set(UserDefaults.standard.stringArray(forKey: "notifiedBackups") ?? [])
        let ready = BackupReadiness.pendingNotifications(repos, seen: seen)
        guard !ready.isEmpty else { return }
        notificationInFlight = true
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            DispatchQueue.main.async {
                guard settings.authorizationStatus == .authorized || settings.authorizationStatus == .provisional else {
                    self.notificationInFlight = false
                    return
                }
                let content = UNMutableNotificationContent()
                content.title = ready.count == 1 ? "\(ready[0].name) backup ready" : "\(ready.count) backups ready"
                content.body = "Hashes verified. macOS confirmed the iCloud upload." + (ready.count > 1 ? "\n" + ready.map { $0.name }.joined(separator: ", ") : "")
                content.sound = .default
                let request = UNNotificationRequest(identifier: "repohub-ready-" + UUID().uuidString, content: content, trigger: nil)
                UNUserNotificationCenter.current().add(request) { error in
                    DispatchQueue.main.async {
                        self.notificationInFlight = false
                        if error == nil {
                            UserDefaults.standard.set(Array(seen.union(ready.map { $0.key })), forKey: "notifiedBackups")
                        } else { print("Completion notification failed:", error!.localizedDescription) }
                    }
                }
            }
        }
    }

    func notifyProblems(_ problems: [[String: Any]]) {
        guard notificationsEnabled, !notificationInFlight else { return }
        let defaults = UserDefaults.standard
        let seen = Set(defaults.stringArray(forKey: "notifiedProblems") ?? [])
        let ready = ProblemAlerts.pending(problems, seen: seen,
            lastNotice: defaults.double(forKey: "lastProblemNotice"), now: Date().timeIntervalSince1970)
        guard !ready.isEmpty else { return }
        notificationInFlight = true
        UNUserNotificationCenter.current().getNotificationSettings { settings in
            DispatchQueue.main.async {
                guard settings.authorizationStatus == .authorized || settings.authorizationStatus == .provisional else {
                    self.notificationInFlight = false
                    return
                }
                let content = UNMutableNotificationContent()
                content.title = "Repo Hub needs attention"
                content.body = ready.prefix(3).map { "\($0["name"] as? String ?? "Repo"): \($0["detail"] as? String ?? "Check backups")" }.joined(separator: "\n")
                content.sound = .default
                let request = UNNotificationRequest(identifier: "repohub-problem-" + UUID().uuidString, content: content, trigger: nil)
                UNUserNotificationCenter.current().add(request) { error in
                    DispatchQueue.main.async {
                        self.notificationInFlight = false
                        if error == nil {
                            defaults.set(Array(seen.union(ready.compactMap { $0["id"] as? String })), forKey: "notifiedProblems")
                            defaults.set(Date().timeIntervalSince1970, forKey: "lastProblemNotice")
                        } else { print("Problem notification failed:", error!.localizedDescription) }
                    }
                }
            }
        }
    }

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound])
    }

    @objc func togglePopover() {
        if popover.isShown { popover.performClose(nil) } else { showPopover() }
    }

    func showPopover() {
        guard let button = statusItem.button else { return }
        NSApp.activate(ignoringOtherApps: true)
        popover.show(relativeTo: button.bounds, of: button, preferredEdge: .minY)
        popoverWebView.window?.title = "Repo Hub Backups"
        popoverWebView.window?.makeKey()
        popoverWebView.window?.makeFirstResponder(popoverWebView)
    }

    func userContentController(_ userContentController: WKUserContentController, didReceive message: WKScriptMessage) {
        guard message.webView === popoverWebView,
              let action = MenuBridge.action(body: message.body, frameURL: message.frameInfo.request.url,
                                             isMainFrame: message.frameInfo.isMainFrame) else { return }
        switch action {
        case .openBackups: openBackups()
        case .openRepo:
            if let body = message.body as? [String: Any], let id = body["repo_id"] as? String { openRepository(id) }
        case .toggleNotifications: toggleNotifications()
        case .connectGitHub: GitHubConnection.configure()
        case .chooseRepoHome, .chooseRepoFolders:
            if let body = message.body as? [String: Any], let id = body["request_id"] as? String {
                chooseSources(multiple: action == .chooseRepoFolders, requestID: id)
            }
        case .quit: quit()
        }
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        if navigationAction.navigationType == .linkActivated && MenuBridge.isReportIssueURL(url) {
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
            return
        }
        decisionHandler(url.scheme == "http" && url.host == "127.0.0.1" && url.port == 8767 && url.path == "/menu.html" ? .allow : .cancel)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
            guard let self = self else { return }
            webView.load(URLRequest(url: self.address.appendingPathComponent("menu.html")))
        }
    }

    func chooseSources(multiple: Bool, requestID: String) {
        guard sourcePicker == nil else { return }
        let panel = NSOpenPanel()
        sourcePicker = panel
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = multiple
        panel.canCreateDirectories = false
        panel.title = multiple ? "Choose individual repo folders" : "Choose a repo-home folder"
        panel.message = multiple ? "Each selected folder is one repo. You can add more in setup." : "Immediate subfolders of this folder will be monitored as repos."
        panel.prompt = "Choose"
        popover.behavior = .applicationDefined
        NSApp.activate(ignoringOtherApps: true)
        panel.begin { [weak self] response in
            guard let self = self else { return }
            let detail: [String: Any] = ["request_id": requestID, "cancelled": response != .OK,
                                        "paths": response == .OK ? panel.urls.map { $0.resolvingSymlinksInPath().path } : []]
            self.sourcePicker = nil
            self.popover.behavior = .transient
            self.showPopover()
            guard let data = try? JSONSerialization.data(withJSONObject: detail),
                  let json = String(data: data, encoding: .utf8) else { return }
            self.popoverWebView.evaluateJavaScript("window.dispatchEvent(new CustomEvent('repoHubSourcesPicked',{detail:" + json + "}))")
        }
    }

    func finderNotice(_ message: String) {
        guard let data = try? JSONSerialization.data(withJSONObject: [message]),
              let json = String(data: data, encoding: .utf8) else { return }
        popoverWebView.evaluateJavaScript("window.dispatchEvent(new CustomEvent('repoHubFinderError',{detail: " + json + "[0]}))")
    }

    func openRepository(_ id: String) {
        var request = URLRequest(url: address.appendingPathComponent("api/status"))
        request.timeoutInterval = 8
        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            let status = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            let target = status.flatMap { MenuBridge.repositoryURL(id: id, status: $0) }
            DispatchQueue.main.async {
                guard let self = self else { return }
                guard error == nil, (response as? HTTPURLResponse)?.statusCode == 200, let target = target else {
                    self.finderNotice("Could not find this repo on your Mac. Refresh its status and try again.")
                    return
                }
                if !NSWorkspace.shared.open(target) { self.finderNotice("Finder could not open this repo.") }
            }
        }.resume()
    }

    @objc func openBackups() {
        let path = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Mobile Documents/com~apple~CloudDocs/Repository Backups")
        NSWorkspace.shared.open(path)
    }
    @objc func quit() { NSApp.terminate(nil) }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        showPopover()
        return true
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }
}

@main enum RepoHubMain {
    static func main() {
        let application = NSApplication.shared
        let delegate = HubDelegate()
        application.delegate = delegate
        withExtendedLifetime(delegate) { application.run() }
    }
}
