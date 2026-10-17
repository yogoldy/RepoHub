import Foundation
import Sparkle
import Darwin

@main enum UpdaterSettingsCheck {
    @MainActor static func main() {
        guard CommandLine.arguments.count == 3,
              let bundle = Bundle(path: CommandLine.arguments[1]) else { exit(64) }
        let settings = SPUUpdaterSettings(hostBundle: bundle)
        let expectedChecks = CommandLine.arguments[2] == "on"
        guard settings.automaticallyChecksForUpdates == expectedChecks,
              settings.updateCheckInterval == 3600,
              !settings.automaticallyDownloadsUpdates,
              settings.allowsAutomaticUpdatesOption?.boolValue == false,
              !settings.sendsSystemProfile else { exit(78) }
        print("Actual Sparkle settings: automatic discovery verified; user-controlled install; no profiling")
    }
}
