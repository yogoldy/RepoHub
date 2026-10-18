import AppKit
import WebKit
import UserNotifications

final class HubDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, UNUserNotificationCenterDelegate, WKScriptMessageHandler {
    var statusItem: NSStatusItem!
    let popover = NSPopover()
    var popoverWebView: WKWebView!
    var lastNotificationData: Data?
    var notificationInFlight = false
    var permissionRequestInFlight = false
    var unavailableSince: Date?
    var notificationsEnabled: Bool { UserDefaults.standard.object(forKey: "notificationsEnabled") as? Bool ?? true }
    var polling: Timer?
    var sourcePicker: NSOpenPanel?
    var setupWindow: NSWindow?
    var setupWebView: WKWebView?
    var offeredSetup = false
    var packaged: PackagedApplication?
    var updates: AppUpdates?
    var hasLoadedMenu = false
    var statusGeneration = 0
    var lastAppliedStatusGeneration = 0
    var address = URL(string: "http://127.0.0.1:8767/")!

    func applicationDidFinishLaunching(_ notification: Notification) {
        if PackagedApplication.enabled {
            do {
                let application = try PackagedApplication()
                packaged = application
                address = application.address
                try application.startHelper()
                updates = AppUpdates(application: application)
            } catch {
                let alert = NSAlert()
                alert.messageText = "RepoHub could not start this app version."
                alert.informativeText = "Its package or configuration could not be verified. Your backups have not been changed."
                alert.runModal()
                NSApp.terminate(nil)
                return
            }
        }
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
        if packaged == nil {
            view.load(URLRequest(url: address.appendingPathComponent("menu.html")))
            hasLoadedMenu = true
        }
        let menu = NSMenu()
        let check = NSMenuItem(title: "Check for Updates…", action: #selector(checkForUpdates), keyEquivalent: "")
        check.target = self
        menu.addItem(check)
        let quit = NSMenuItem(title: "Quit RepoHub", action: #selector(quit), keyEquivalent: "q")
        quit.target = self
        menu.addItem(quit)
        let mainMenu = NSMenu()
        let appItem = NSMenuItem()
        appItem.submenu = menu
        mainMenu.addItem(appItem)
        NSApp.mainMenu = mainMenu
        UNUserNotificationCenter.current().delegate = self
        updateNotificationStatus()
        pollStatus()
        polling = Timer.scheduledTimer(withTimeInterval: 5, repeats: true) { [weak self] _ in self?.pollStatus() }
        if !CommandLine.arguments.contains("--background") { showPopover() }
    }

    func pollStatus() {
        statusGeneration += 1
        let generation = statusGeneration
        updateNotificationStatus()
        var statusRequest = URLRequest(url: address.appendingPathComponent("api/status"))
        statusRequest.timeoutInterval = 8
        URLSession.shared.dataTask(with: statusRequest) { [weak self] data, _, error in
            guard let self = self else { return }
            let status = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            DispatchQueue.main.async {
                guard generation > self.lastAppliedStatusGeneration else { return }
                self.lastAppliedStatusGeneration = generation
                guard error == nil, let status = status else {
                    self.statusItem.button?.title = " !"
                    self.statusItem.button?.toolTip = "Repo Hub: backup helper unavailable"
                    self.statusItem.button?.setAccessibilityLabel("RepoHub: backup helper unavailable")
                    if self.unavailableSince == nil { self.unavailableSince = Date() }
                    if let since = self.unavailableSince, Date().timeIntervalSince(since) >= 120 {
                        self.notifyProblems([["id":"helper:" + String(since.timeIntervalSince1970), "name":"Repo Hub", "detail":"The backup helper has been unavailable for two minutes."]])
                    }
                    return
                }
                if let packaged = self.packaged {
                    guard packaged.matches(status) else {
                        self.statusItem.button?.title = " !"
                        self.statusItem.button?.toolTip = "RepoHub: application components do not match"
                        self.statusItem.button?.setAccessibilityLabel("RepoHub: application components do not match")
                        self.updates?.record("failed", reason: "component_mismatch")
                        return
                    }
                    if !self.hasLoadedMenu {
                        self.popoverWebView.load(URLRequest(url: self.address.appendingPathComponent("menu.html")))
                        self.hasLoadedMenu = true
                        self.updates?.record("ready", reason: "matching_helper")
                    }
                }
                self.unavailableSince = nil
                if !self.offeredSetup, let setup = status["setup"] as? [String: Any],
                   setup["configured"] as? Bool != true || setup["reviewed"] as? Bool != true {
                    self.offeredSetup = true
                    self.openSetup()
                }
                let repos = status["repos"] as? [[String: Any]] ?? []
                self.renderMenuBar(status: status, generation: generation)
                self.notifyProblems(status["problems"] as? [[String: Any]] ?? [])
                self.notifyReadyBackups(repos)
            }
        }.resume()
    }

    func renderMenuBar(status: [String: Any], generation: Int) {
        let mode = MenuAppearance.saved()
        guard let expression = MenuAppearance.expression(status: status, mode: mode) else { return }
        popoverWebView.evaluateJavaScript(expression) { [weak self] value, error in
            guard let self = self, generation == self.lastAppliedStatusGeneration,
                  MenuAppearance.saved() == mode else { return }
            guard error == nil, let display = MenuAppearance.rendered(value, mode: mode) else {
                self.statusItem.button?.title = " !"
                self.statusItem.button?.toolTip = "RepoHub: menu bar status unavailable"
                self.statusItem.button?.setAccessibilityLabel("RepoHub: menu bar status unavailable")
                return
            }
            self.statusItem.button?.title = display.title
            self.statusItem.button?.toolTip = display.tooltip
            self.statusItem.button?.setAccessibilityLabel(display.tooltip)
            var observed = value as? [String: Any] ?? [:]
            observed["title"] = self.statusItem.button?.title ?? ""
            if let data = try? JSONSerialization.data(withJSONObject: [status, observed]),
               let json = String(data: data, encoding: .utf8) {
                self.popoverWebView.evaluateJavaScript(
                    "window.RepoHubMenuAppearance?.recordNative(..." + json + ")"
                )
            }
        }
    }

    func menuAppearance(action: MenuAction, body: [String: Any]) {
        guard let requestID = body["request_id"] as? String else { return }
        let result: String
        if action == .saveMenuAppearance, let mode = body["mode"] as? String,
           let revision = body["revision"] as? String {
            result = MenuAppearance.save(mode: mode, revision: revision)
        } else {
            result = "loaded"
        }
        var detail = MenuAppearance.settings()
        detail["request_id"] = requestID
        detail["result"] = result
        guard let data = try? JSONSerialization.data(withJSONObject: detail),
              let json = String(data: data, encoding: .utf8) else { return }
        popoverWebView.evaluateJavaScript(
            "window.dispatchEvent(new CustomEvent('repoHubMenuAppearance',{detail:" + json + "}))"
        )
        if result == "saved" { pollStatus() }
    }

    func requestNotifications() {
        guard !permissionRequestInFlight else { return }
        permissionRequestInFlight = true
        UserDefaults.standard.set("pending", forKey: "notificationRequest")
        updateNotificationStatus()
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound]) { _, error in
            DispatchQueue.main.async {
                self.permissionRequestInFlight = false
                UserDefaults.standard.set(error == nil ? "completed" : "failed", forKey: "notificationRequest")
                self.updateNotificationStatus()
            }
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
                let request = BackupReadiness.permissionRequest(saved: UserDefaults.standard.string(forKey: "notificationRequest"), inFlight: self.permissionRequestInFlight)
                let status: [String: Any] = ["enabled": self.notificationsEnabled, "permission": permission,
                    "request": request]
                let state = self.packaged?.stateDirectory ?? FileManager.default.homeDirectoryForCurrentUser
                    .appendingPathComponent("Library/Application Support/RepoHub")
                let path = state.appendingPathComponent("notifications.json")
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
        let isSetup = message.webView === setupWebView
        guard (message.webView === popoverWebView || isSetup),
              let action = MenuBridge.action(body: message.body, frameURL: message.frameInfo.request.url,
                                             isMainFrame: message.frameInfo.isMainFrame, expectedPort: address.port ?? 8767,
                                             expectedPage: isSetup ? "/setup.html" : "/menu.html") else { return }
        switch action {
        case .openBackups: openBackups()
        case .openRepo:
            if let body = message.body as? [String: Any], let id = body["repo_id"] as? String { openRepository(id) }
        case .requestNotifications:
            UserDefaults.standard.set(true, forKey: "notificationsEnabled")
            requestNotifications()
        case .notificationSettings: NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.Notifications-Settings.extension")!)
        case .privacySettings: NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.settings.PrivacySecurity.extension?Privacy_FilesAndFolders")!)
        case .loginSettings: NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.LoginItems-Settings.extension")!)
        case .toggleNotifications: toggleNotifications()
        case .connectGitHub:
            if packaged?.testMode != true { GitHubConnection.configure() }
        case .checkForUpdates: checkForUpdates()
        case .getMenuAppearance, .saveMenuAppearance:
            if let body = message.body as? [String: Any] { menuAppearance(action: action, body: body) }
        case .openSetup: openSetup()
        case .closeSetup:
            setupWindow?.close()
            setupWebView = nil
            setupWindow = nil
            pollStatus()
            showPopover()
        case .chooseRepoHome, .chooseRepoFolders, .chooseBackupDestination, .chooseDiscoveryParent:
            if let body = message.body as? [String: Any], let id = body["request_id"] as? String {
                chooseSources(multiple: action == .chooseRepoFolders, requestID: id,
                              sender: message.webView, purpose: action)
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
        let page = webView === setupWebView ? "/setup.html" : "/menu.html"
        decisionHandler(url.scheme == "http" && url.host == "127.0.0.1" && url.port == address.port && url.path == page ? .allow : .cancel)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
            guard let self = self else { return }
            webView.load(URLRequest(url: self.address.appendingPathComponent(webView === self.setupWebView ? "setup.html" : "menu.html")))
        }
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        pollStatus()
    }

    func openSetup() {
        if setupWindow == nil {
            let configuration = WKWebViewConfiguration()
            configuration.userContentController.add(self, name: "repoHub")
            let view = WKWebView(frame: NSRect(x: 0, y: 0, width: 740, height: 720), configuration: configuration)
            setupWebView = view
            view.navigationDelegate = self
            view.underPageBackgroundColor = NSColor(calibratedRed: 0.063, green: 0.082, blue: 0.114, alpha: 1)
            let window = NSWindow(contentRect: view.frame, styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
            window.title = "Welcome to RepoHub"
            window.minSize = NSSize(width: 580, height: 540)
            window.isReleasedWhenClosed = false
            window.contentView = view
            window.appearance = NSAppearance(named: .darkAqua)
            window.center()
            setupWindow = window
            view.load(URLRequest(url: address.appendingPathComponent("setup.html")))
        }
        popover.performClose(nil)
        NSApp.activate(ignoringOtherApps: true)
        setupWindow?.makeKeyAndOrderFront(nil)
    }

    func chooseSources(multiple: Bool, requestID: String, sender: WKWebView? = nil,
                       purpose: MenuAction = .chooseRepoFolders) {
        guard sourcePicker == nil else { return }
        let target = sender ?? popoverWebView!
        let inSetup = target === setupWebView
        let panel = NSOpenPanel()
        sourcePicker = panel
        panel.canChooseFiles = false
        panel.canChooseDirectories = true
        panel.allowsMultipleSelection = multiple
        panel.canCreateDirectories = purpose == .chooseBackupDestination
        switch purpose {
        case .chooseBackupDestination:
            panel.title = "Choose a backup folder in iCloud Drive"
            panel.message = "Your repo folders will be stored directly inside this folder."
            panel.directoryURL = packaged?.testMode == true
                ? packaged?.stateDirectory.deletingLastPathComponent().appendingPathComponent("cloud")
                : FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Mobile Documents/com~apple~CloudDocs")
        case .chooseDiscoveryParent:
            panel.title = "Choose a parent folder to scan for Git repos"
            panel.message = "Review discovered repos before adding them. Nothing is enabled automatically."
        default:
            panel.title = multiple ? "Choose individual repo folders" : "Choose a repo-home folder"
            panel.message = multiple ? "Each selected folder is one repo. You can add more in setup." : "Immediate subfolders of this folder will be monitored as repos."
        }
        panel.prompt = "Choose"
        if !inSetup { popover.behavior = .applicationDefined }
        // A popover floats above an independent NSOpenPanel. Hide it while the
        // picker is active; its WebKit draft survives and is reopened on return.
        popover.performClose(nil)
        NSApp.activate(ignoringOtherApps: true)
        let completion: (NSApplication.ModalResponse) -> Void = { [weak self] response in
            guard let self = self else { return }
            let detail: [String: Any] = ["request_id": requestID, "cancelled": response != .OK,
                                        "paths": response == .OK ? panel.urls.map { MenuBridge.canonicalSourcePath($0) } : []]
            self.sourcePicker = nil
            if !inSetup {
                self.popover.behavior = .transient
                self.showPopover()
            }
            guard let data = try? JSONSerialization.data(withJSONObject: detail),
                  let json = String(data: data, encoding: .utf8) else { return }
            let event = inSetup ? "repoHubSetupPicked" : "repoHubSourcesPicked"
            target.evaluateJavaScript("window.dispatchEvent(new CustomEvent('" + event + "',{detail:" + json + "}))")
        }
        if inSetup, let window = setupWindow { panel.beginSheetModal(for: window, completionHandler: completion) }
        else { panel.begin(completionHandler: completion) }
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
        var request = URLRequest(url: address.appendingPathComponent("api/status"))
        request.timeoutInterval = 8
        URLSession.shared.dataTask(with: request) { [weak self] data, response, error in
            let status = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            let target = status.flatMap { MenuBridge.backupDirectoryURL(status: $0) }
            DispatchQueue.main.async {
                guard let self = self else { return }
                guard error == nil, (response as? HTTPURLResponse)?.statusCode == 200, let target = target else {
                    self.finderNotice("The selected backup folder is unavailable. Review it in Settings and try again.")
                    return
                }
                if !NSWorkspace.shared.open(target) { self.finderNotice("Finder could not open your backup folder.") }
            }
        }.resume()
    }
    @objc func checkForUpdates() { updates?.checkForUpdates() }
    @objc func quit() { NSApp.terminate(nil) }
    func applicationWillTerminate(_ notification: Notification) {
        packaged?.stopHelper()
    }
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows flag: Bool) -> Bool {
        showPopover()
        return true
    }
    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }
}

@main enum RepoHubMain {
    static func main() {
        if CommandLine.arguments.dropFirst().first == "--bundled-helper" {
            guard PackagedApplication.enabled else { exit(64) }
            do { exit(try PackagedApplication().runHelper()) } catch { exit(78) }
        }
        if let code = HelperLaunch.run(CommandLine.arguments) { exit(code) }
        let application = NSApplication.shared
        let delegate = HubDelegate()
        application.delegate = delegate
        withExtendedLifetime(delegate) { application.run() }
    }
}
