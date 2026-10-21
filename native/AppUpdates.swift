import AppKit
#if canImport(Sparkle)
import Sparkle
#endif

enum UpdateChannel: String, CaseIterable {
    case stable, testing, dev

    var feedURL: String {
        let base = "https://github.com/yogoldy/RepoHub/releases/"
        return self == .stable ? base + "latest/download/appcast.xml"
            : base + "download/repohub-channel-" + rawValue + "/appcast.xml"
    }

    func accepts(_ itemChannel: String?) -> Bool {
        self == .stable ? itemChannel == nil || itemChannel == "" : itemChannel == rawValue
    }
}

enum UpdateChannelSettings {
    static let key = "updateChannelSelection"

    static func settings(in defaults: UserDefaults = .standard) -> [String: String] {
        guard let saved = defaults.dictionary(forKey: key) as? [String: String],
              let channel = saved["channel"], UpdateChannel(rawValue: channel) != nil,
              let revision = saved["revision"], UUID(uuidString: revision) != nil else {
            return ["channel": "stable", "revision": "initial"]
        }
        return ["channel": channel, "revision": revision]
    }

    static func selected(in defaults: UserDefaults = .standard) -> UpdateChannel {
        UpdateChannel(rawValue: settings(in: defaults)["channel"]!)!
    }

    static func save(channel: String, revision: String,
                     in defaults: UserDefaults = .standard) -> String {
        guard UpdateChannel(rawValue: channel) != nil else { return "invalid" }
        guard settings(in: defaults)["revision"] == revision else { return "conflict" }
        defaults.set(["channel": channel, "revision": UUID().uuidString], forKey: key)
        return "saved"
    }
}

enum UpdateCycleOutcome {
    static func result(isSparkle: Bool, isBackupBusy: Bool, code: Int?,
                       isChannelMismatch: Bool = false) -> (String, String) {
        if isBackupBusy { return ("waiting", "backup_busy") }
        if isChannelMismatch { return ("failed", "channel_mismatch") }
        // Values from the pinned Sparkle SUErrors.h. These are normal outcomes,
        // despite Sparkle reporting them through its error callback.
        if code == nil { return ("ready", "check_finished") }
        if isSparkle && code == 1001 { return ("ready", "no_update") }
        if isSparkle && code == 4007 { return ("ready", "user_cancelled") }
        return ("failed", "sparkle_aborted")
    }
}

// Sparkle handles archive authentication and replacement. This adapter owns the
// helper shutdown boundary; a successful download alone is not an installed app.
final class AppUpdates: NSObject {
    let application: PackagedApplication
    #if canImport(Sparkle)
    private var controller: SPUStandardUpdaterController!
    #endif

    init(application: PackagedApplication) {
        self.application = application
        super.init()
        #if canImport(Sparkle)
        controller = SPUStandardUpdaterController(startingUpdater: true, updaterDelegate: self, userDriverDelegate: nil)
        #endif
    }

    @objc func checkForUpdates() {
        #if canImport(Sparkle)
        record("checking", reason: "user_requested")
        controller.checkForUpdates(nil)
        #else
        let alert = NSAlert()
        alert.messageText = "Updates are unavailable in this development build."
        alert.runModal()
        #endif
    }

    func channelSettings() -> [String: String] {
        UpdateChannelSettings.settings()
    }

    func saveChannel(_ channel: String, revision: String) -> String {
        #if canImport(Sparkle)
        guard !controller.updater.sessionInProgress else { return "busy" }
        do { try requireIdle() } catch { return "busy" }
        let result = UpdateChannelSettings.save(channel: channel, revision: revision)
        if result == "saved" {
            record("ready", reason: "channel_changed")
            controller.updater.resetUpdateCycleAfterShortDelay()
        }
        return result
        #else
        return "unavailable"
        #endif
    }

    func record(_ phase: String, reason: String) {
        let evidence: [String: String] = ["update_phase": phase, "update_reason": reason,
            "update_channel": UpdateChannelSettings.selected().rawValue,
            "source_revision": application.release.source_revision,
            "build": application.release.build]
        if let data = try? JSONSerialization.data(withJSONObject: evidence, options: [.sortedKeys]) {
            try? data.write(to: application.stateDirectory.appendingPathComponent("update-status.json"), options: .atomic)
        }
    }

    private func status() throws -> [String: Any] {
        let semaphore = DispatchSemaphore(value: 0)
        let box = StatusResult()
        var request = URLRequest(url: application.address.appendingPathComponent("api/status"))
        request.timeoutInterval = 3
        URLSession.shared.dataTask(with: request) { data, response, error in
            if error == nil, (response as? HTTPURLResponse)?.statusCode == 200, let data = data {
                box.value = (try? JSONSerialization.jsonObject(with: data)) as? [String: Any]
            }
            semaphore.signal()
        }.resume()
        guard semaphore.wait(timeout: .now() + 4) == .success, let value = box.value,
              application.matches(value) else { throw PackagedApplication.Failure.helperUnavailable }
        return value
    }

    private func requireIdle() throws {
        let value = try status()
        guard let backup = value["backup"] as? [String: Any], backup["running"] as? Bool == false else {
            record("waiting", reason: "backup_busy")
            throw NSError(domain: "RepoHubUpdate", code: 1,
                userInfo: [NSLocalizedDescriptionKey: "A backup is running. Check for updates after it finishes."])
        }
    }

    private final class StatusResult: @unchecked Sendable {
        var value: [String: Any]?
    }
}

#if canImport(Sparkle)
extension AppUpdates: SPUUpdaterDelegate {
    func feedURLString(for updater: SPUUpdater) -> String? {
        // Disposable test bundles must keep their explicitly configured fixture feed.
        application.testMode ? nil : UpdateChannelSettings.selected().feedURL
    }

    func allowedChannels(for updater: SPUUpdater) -> Set<String> {
        let selected = UpdateChannelSettings.selected()
        return selected == .stable ? [] : [selected.rawValue]
    }

    func updater(_ updater: SPUUpdater, mayPerform updateCheck: SPUUpdateCheck) throws {
        try requireIdle()
        record("checking", reason: updateCheck == .updatesInBackground ? "scheduled_check" : "user_requested")
    }

    func updater(_ updater: SPUUpdater, shouldProceedWithUpdate item: SUAppcastItem,
                 updateCheck: SPUUpdateCheck) throws {
        try requireIdle()
        guard application.testMode || UpdateChannelSettings.selected().accepts(item.channel) else {
            record("failed", reason: "channel_mismatch")
            throw NSError(domain: "RepoHubUpdateChannel", code: 1,
                userInfo: [NSLocalizedDescriptionKey: "This update does not match this Mac's selected channel."])
        }
        record("downloading", reason: "update_available")
    }

    func updater(_ updater: SPUUpdater, shouldPostponeRelaunchForUpdate item: SUAppcastItem,
                 untilInvokingBlock installHandler: @escaping () -> Void) -> Bool {
        record("waiting", reason: "helper_shutdown")
        // SIGTERM in bundled mode waits for the backup lock. It never kills a
        // backup that started after the last status request.
        DispatchQueue.global().async {
            do {
                let recovery = try self.application.prepareRecovery(targetBuild: item.versionString)
                self.application.stopHelper()
                try recovery.run()
                DispatchQueue.main.async {
                    self.record("installing", reason: "helper_stopped")
                    installHandler()
                }
            } catch {
                DispatchQueue.main.async {
                    self.record("failed", reason: "recovery_unavailable")
                    let alert = NSAlert()
                    alert.messageText = "The update is paused because a rollback copy could not be prepared."
                    alert.informativeText = "Your installed app and backups have not been replaced. Quit and reopen RepoHub before retrying."
                    alert.runModal()
                }
            }
        }
        return true
    }

    func updater(_ updater: SPUUpdater, willInstallUpdate item: SUAppcastItem) {
        record("installing", reason: "verified_update")
    }

    func updaterWillRelaunchApplication(_ updater: SPUUpdater) {
        record("relaunching", reason: "verified_update")
    }

    func updater(_ updater: SPUUpdater, didAbortWithError error: Error) {
        // Sparkle owns the detailed native error dialog. Shareable evidence is bounded.
        recordOutcome(error)
    }

    func updater(_ updater: SPUUpdater, didFinishUpdateCycleFor updateCheck: SPUUpdateCheck, error: Error?) {
        recordOutcome(error)
    }

    func userDidCancelDownload(_ updater: SPUUpdater) {
        record("ready", reason: "user_cancelled")
    }

    private func recordOutcome(_ error: Error?) {
        let value = error as NSError?
        let outcome = UpdateCycleOutcome.result(
            isSparkle: value?.domain == SUSparkleErrorDomain,
            isBackupBusy: value?.domain == "RepoHubUpdate" && value?.code == 1,
            code: value?.code,
            isChannelMismatch: value?.domain == "RepoHubUpdateChannel")
        record(outcome.0, reason: outcome.1)
    }
}
#endif
