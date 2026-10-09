import AppKit
import WebKit
import UserNotifications

final class HubDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, UNUserNotificationCenterDelegate {
    var statusItem: NSStatusItem!
    var window: NSWindow?
    var webView: WKWebView?
    var summaryItem: NSMenuItem!
    var detailItem: NSMenuItem!
    var backupItem: NSMenuItem!
    var cloudItem: NSMenuItem!
    var notificationItem: NSMenuItem!
    var notificationInFlight = false
    var notificationsEnabled: Bool { UserDefaults.standard.object(forKey: "notificationsEnabled") as? Bool ?? true }
    var polling: Timer?
    let address = URL(string: "http://127.0.0.1:8767/")!

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        statusItem = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength)
        statusItem.button?.image = NSImage(systemSymbolName: "square.stack.3d.up", accessibilityDescription: "Repo Hub")
        statusItem.button?.setAccessibilityLabel("Repo Hub backup status")
        let menu = NSMenu()
        menu.autoenablesItems = false
        summaryItem = NSMenuItem(title: "Checking backups…", action: nil, keyEquivalent: "")
        summaryItem.isEnabled = false
        detailItem = NSMenuItem(title: "Local helper starting", action: nil, keyEquivalent: "")
        detailItem.isEnabled = false
        menu.addItem(summaryItem)
        menu.addItem(detailItem)
        cloudItem = NSMenuItem(title: "iCloud status: checking", action: nil, keyEquivalent: "")
        cloudItem.isEnabled = false
        menu.addItem(cloudItem)
        menu.addItem(.separator())
        menu.addItem(withTitle: "Open Repo Hub", action: #selector(showHub), keyEquivalent: "h").target = self
        backupItem = menu.addItem(withTitle: "Back up now", action: #selector(backupNow), keyEquivalent: "")
        backupItem.target = self
        backupItem.isEnabled = false
        menu.addItem(withTitle: "Open Repository Backups", action: #selector(openBackups), keyEquivalent: "").target = self
        notificationItem = menu.addItem(withTitle: "Notify when backups are ready", action: #selector(toggleNotifications), keyEquivalent: "")
        notificationItem.target = self
        notificationItem.state = notificationsEnabled ? .on : .off
        menu.addItem(.separator())
        menu.addItem(withTitle: "Quit menu-bar app", action: #selector(quit), keyEquivalent: "q").target = self
        statusItem.menu = menu
        UNUserNotificationCenter.current().delegate = self
        if notificationsEnabled { requestNotifications() }
        pollStatus()
        polling = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in self?.pollStatus() }
        if !CommandLine.arguments.contains("--background") { showHub() }
    }

    func pollStatus() {
        updateNotificationStatus()
        let url = address.appendingPathComponent("api/status")
        URLSession.shared.dataTask(with: url) { [weak self] data, _, error in
            guard let self = self else { return }
            let status = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            DispatchQueue.main.async {
                guard error == nil, let status = status else {
                    self.summaryItem.title = "Backup helper unavailable"
                    self.detailItem.title = "Open the hub to check its connection"
                    self.cloudItem.title = "iCloud status: unavailable"
                    self.statusItem.button?.title = " !"
                    self.statusItem.button?.toolTip = "Repo Hub: helper unavailable"
                    self.backupItem.isEnabled = false
                    return
                }
                let repos = status["repos"] as? [[String: Any]] ?? []
                let backup = status["backup"] as? [String: Any] ?? [:]
                let running = backup["running"] as? Bool ?? false
                let pending = repos.filter { $0["needs_backup"] as? Bool ?? true }.count
                let errors = backup["errors"] as? [[String: Any]] ?? []
                let verified = repos.filter { ($0["verification"] as? [String: Any])?["state"] as? String == "matched" }.count
                let verificationErrors = repos.filter { ($0["verification"] as? [String: Any])?["state"] as? String == "error" }.count
                let uploaded = repos.filter { ($0["cloud"] as? [String: Any])?["state"] as? String == "uploaded" }.count
                let cloudErrors = repos.filter { ($0["cloud"] as? [String: Any])?["state"] as? String == "error" }.count
                let uploading = repos.filter { ($0["cloud"] as? [String: Any])?["state"] as? String == "uploading" }
                let dataError = (status["data_cloud"] as? [String: Any])?["state"] as? String == "error"
                self.cloudItem.title = "iCloud: \(uploaded)/\(repos.count) uploads confirmed" + (cloudErrors > 0 ? " · \(cloudErrors) error(s)" : "") + (dataError ? " · saved data error" : "")
                if let active = uploading.first(where: { repo in
                    let percent = (repo["cloud"] as? [String: Any])?["percent"] as? Double ?? 0
                    return percent > 0 && percent < 99
                }) ?? uploading.first {
                    let cloud = active["cloud"] as? [String: Any] ?? [:]
                    let percent = (cloud["percent"] as? Double).map { " \(Int($0))%" } ?? ""
                    self.cloudItem.title += " · \(active["name"] as? String ?? "Repo")\(percent) uploading"
                }
                let count = repos.filter { $0["last_backup"] is [String: Any] }.count
                self.summaryItem.title = running ? "Backing up: \(backup["current_repo"] as? String ?? "repos")" :
                    !errors.isEmpty ? "\(errors.count) backup issue(s) — check hub" :
                    verificationErrors > 0 ? "\(verificationErrors) verification issue(s) — check hub" :
                    pending > 0 ? "\(pending) repo(s) changed since backup" : verified < repos.count ? "Verifying hashes: \(verified)/\(repos.count) checked" : "All \(repos.count) repo hashes verified"
                let parser = ISO8601DateFormatter()
                parser.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
                let newest = repos.compactMap { ($0["last_backup"] as? [String: Any])?["completed_at"] as? String }
                    .compactMap { parser.date(from: $0) }.max()
                let last = newest.map { DateFormatter.localizedString(from: $0, dateStyle: .short, timeStyle: .short) }
                self.detailItem.title = "\(count)/\(repos.count) backed up" + (last.map { " · Latest \($0)" } ?? "")
                self.statusItem.button?.title = running ? " ↻" : (!errors.isEmpty || verificationErrors > 0 || cloudErrors > 0 || dataError) ? " !" : pending > 0 ? " \(pending)" : uploaded < repos.count ? " ↑" : ""
                self.statusItem.button?.toolTip = "Repo Hub: " + self.summaryItem.title + " · " + self.cloudItem.title
                self.backupItem.isEnabled = !running
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
                if let data = try? JSONSerialization.data(withJSONObject: status) { try? data.write(to: path, options: .atomic) }
                self.notificationItem.title = "Notify when backups are ready" + (permission == "denied" ? " (macOS permission needed)" : "")
            }
        }
    }

    @objc func toggleNotifications() {
        UserDefaults.standard.set(!notificationsEnabled, forKey: "notificationsEnabled")
        notificationItem.state = notificationsEnabled ? .on : .off
        if notificationsEnabled { requestNotifications(); pollStatus() }
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

    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([.banner, .sound])
    }

    @objc func backupNow() {
        backupItem.isEnabled = false
        URLSession.shared.dataTask(with: address.appendingPathComponent("api/session")) { [weak self] data, _, _ in
            guard let self = self, let data = data,
                  let value = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
                  let token = value["token"] as? String else { return }
            var request = URLRequest(url: self.address.appendingPathComponent("api/backup"))
            request.httpMethod = "POST"
            request.httpBody = Data("{}".utf8)
            request.setValue("application/json", forHTTPHeaderField: "Content-Type")
            request.setValue("http://127.0.0.1:8767", forHTTPHeaderField: "Origin")
            request.setValue(token, forHTTPHeaderField: "X-RepoHub-Token")
            URLSession.shared.dataTask(with: request) { _, _, _ in self.pollStatus() }.resume()
        }.resume()
    }

    @objc func showHub() {
        if window == nil {
            let configuration = WKWebViewConfiguration()
            let view = WKWebView(frame: .zero, configuration: configuration)
            view.navigationDelegate = self
            let win = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1250, height: 830),
                               styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
            win.title = "Repo Hub"
            win.minSize = NSSize(width: 750, height: 540)
            win.contentView = view
            win.isReleasedWhenClosed = false
            win.center()
            webView = view
            window = win
            view.load(URLRequest(url: address))
        }
        window?.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
    }

    func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction, decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
        guard let url = navigationAction.request.url else { decisionHandler(.cancel); return }
        decisionHandler(url.host == "127.0.0.1" && url.port == 8767 ? .allow : .cancel)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
            guard let self = self else { return }
            webView.load(URLRequest(url: self.address))
        }
    }

    @objc func openBackups() {
        let path = FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Mobile Documents/com~apple~CloudDocs/Repository Backups")
        NSWorkspace.shared.open(path)
    }
    @objc func quit() { NSApp.terminate(nil) }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        showHub()
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
