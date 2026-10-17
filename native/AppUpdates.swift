import AppKit
#if canImport(Sparkle)
import Sparkle
#endif

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

    func record(_ phase: String, reason: String) {
        let evidence: [String: String] = ["update_phase": phase, "update_reason": reason,
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
    func updater(_ updater: SPUUpdater, mayPerform updateCheck: SPUUpdateCheck) throws {
        try requireIdle()
    }

    func updater(_ updater: SPUUpdater, shouldProceedWithUpdate item: SUAppcastItem,
                 updateCheck: SPUUpdateCheck) throws {
        try requireIdle()
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
        record("failed", reason: "sparkle_aborted")
    }
}
#endif
