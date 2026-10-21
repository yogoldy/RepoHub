import Foundation

@main enum UpdateChannelTests {
    static func main() {
        if CommandLine.arguments.count == 4 && CommandLine.arguments[1] == "--read" {
            let defaults = UserDefaults(suiteName: CommandLine.arguments[2])!
            precondition(UpdateChannelSettings.selected(in: defaults).rawValue == CommandLine.arguments[3])
            return
        }
        let domain = "com.leogoldberg.repohub.test.channels-" + UUID().uuidString
        let mismatch = UpdateCycleOutcome.result(isSparkle: false, isBackupBusy: false,
                                                 code: 1, isChannelMismatch: true)
        precondition(mismatch.0 == "failed" && mismatch.1 == "channel_mismatch")
        let defaults = UserDefaults(suiteName: domain)!
        defer { defaults.removePersistentDomain(forName: domain) }
        precondition(UpdateChannelSettings.selected(in: defaults) == .stable)
        precondition(UpdateChannelSettings.settings(in: defaults)["revision"] == "initial")
        for channel in UpdateChannel.allCases {
            let expected = [
                "stable": "https://github.com/yogoldy/RepoHub/releases/latest/download/appcast.xml",
                "testing": "https://github.com/yogoldy/RepoHub/releases/download/repohub-channel-testing/appcast.xml",
                "dev": "https://github.com/yogoldy/RepoHub/releases/download/repohub-channel-dev/appcast.xml",
            ]
            precondition(channel.feedURL == expected[channel.rawValue])
            let url = URL(string: channel.feedURL)!
            precondition(url.scheme == "https" && url.host == "github.com")
            precondition(url.path.hasPrefix("/yogoldy/RepoHub/releases/"))
            for item in [nil, "", "dev", "testing", "stable", "foreign"] as [String?] {
                let expected = channel == .stable ? item == nil || item == "" : item == channel.rawValue
                precondition(channel.accepts(item) == expected)
            }
        }
        let original = UpdateChannelSettings.settings(in: defaults)
        precondition(UpdateChannelSettings.save(channel: "dev", revision: original["revision"]!, in: defaults) == "saved")
        let dev = UpdateChannelSettings.settings(in: defaults)
        precondition(dev["channel"] == "dev" && dev["revision"] != original["revision"])
        precondition(defaults.synchronize())
        let reader = Process()
        reader.executableURL = URL(fileURLWithPath: CommandLine.arguments[0])
        reader.arguments = ["--read", domain, "dev"]
        do { try reader.run() } catch { preconditionFailure("Cannot launch isolated preference reader") }
        reader.waitUntilExit()
        precondition(reader.terminationStatus == 0)
        precondition(UpdateChannelSettings.save(channel: "testing", revision: "initial", in: defaults) == "conflict")
        precondition(UpdateChannelSettings.save(channel: "outside", revision: dev["revision"]!, in: defaults) == "invalid")
        precondition(UpdateChannelSettings.settings(in: defaults) == dev)
        precondition(UpdateChannelSettings.save(channel: "stable", revision: dev["revision"]!, in: defaults) == "saved")
        precondition(UpdateChannelSettings.save(channel: "dev", revision: dev["revision"]!, in: defaults) == "conflict")
        defaults.set(["channel": "foreign", "revision": UUID().uuidString], forKey: UpdateChannelSettings.key)
        precondition(UpdateChannelSettings.selected(in: defaults) == .stable)
        print("Channel defaults, fixed feeds, item isolation, explicit save, stale/ABA revisions and corrupt preferences passed")
    }
}
