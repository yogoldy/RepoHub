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
        precondition(UpdateChannelSettings.settings(in: defaults)["experimental_channels"] == "disabled")
        for channel in ["dev"] {
            precondition(UpdateChannelSettings.save(channel: channel, revision: "initial", in: defaults)
                == "experimental_disabled")
        }
        precondition(defaults.object(forKey: UpdateChannelSettings.key) == nil)
        for malformed: Any in ["true", 1, ["enabled": true], [true], false] {
            defaults.set(malformed, forKey: UpdateChannelSettings.experimentalKey)
            precondition(!UpdateChannelSettings.experimentalEnabled(in: defaults))
        }
        defaults.set(true, forKey: UpdateChannelSettings.experimentalKey)
        precondition(UpdateChannelSettings.experimentalEnabled(in: defaults))
        for channel in UpdateChannel.allCases {
            let expected = [
                "stable": "https://github.com/yogoldy/RepoHub/releases/latest/download/appcast.xml",
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
        // A retired Testing preference fails closed without rewriting daily data.
        let retired = ["channel": "testing", "revision": UUID().uuidString]
        defaults.set(retired, forKey: UpdateChannelSettings.key)
        precondition(UpdateChannelSettings.selected(in: defaults) == .stable)
        precondition(defaults.dictionary(forKey: UpdateChannelSettings.key) as? [String: String] == retired)
        precondition(UpdateChannelSettings.save(channel: "testing", revision: "initial", in: defaults) == "invalid")
        defaults.removeObject(forKey: UpdateChannelSettings.key)
        precondition(UpdateChannel.allCases.map(\.rawValue) == ["stable", "dev"])
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
        precondition(UpdateChannelSettings.save(channel: "stable", revision: "initial", in: defaults) == "conflict")
        precondition(UpdateChannelSettings.save(channel: "outside", revision: dev["revision"]!, in: defaults) == "invalid")
        precondition(UpdateChannelSettings.settings(in: defaults) == dev)

        // Removing the opt-in suppresses even an existing saved Dev preference.
        // It does not delete that preference or any unrelated application settings.
        defaults.set("untouched", forKey: "unrelatedPreference")
        defaults.removeObject(forKey: UpdateChannelSettings.experimentalKey)
        precondition(UpdateChannelSettings.selected(in: defaults) == .stable)
        precondition(UpdateChannelSettings.settings(in: defaults)["experimental_channels"] == "disabled")
        precondition(UpdateChannelSettings.save(channel: "dev", revision: dev["revision"]!,
            in: defaults) == "experimental_disabled")
        precondition((defaults.dictionary(forKey: UpdateChannelSettings.key)?["channel"] as? String) == "dev")
        precondition(defaults.synchronize())
        let stableReader = Process()
        stableReader.executableURL = reader.executableURL
        stableReader.arguments = ["--read", domain, "stable"]
        do { try stableReader.run() } catch { preconditionFailure("Cannot launch isolated Stable reader") }
        stableReader.waitUntilExit()
        precondition(stableReader.terminationStatus == 0)
        let effective = UpdateChannelSettings.selected(in: defaults)
        precondition(effective.feedURL.contains("/latest/download/"))
        precondition(!effective.accepts("dev") && !effective.accepts("testing"))
        // Running updater sessions use a launch-time policy snapshot.
        precondition(UpdateChannelSettings.selected(in: defaults, experimentalEnabled: true) == .dev)
        precondition(UpdateChannelSettings.settings(in: defaults,
            experimentalEnabled: true)["experimental_channels"] == "enabled")
        let disabled = UpdateChannelSettings.settings(in: defaults)
        let evidence = ["update_channel": disabled["channel"]!,
                        "experimental_channels": disabled["experimental_channels"]!]
        let data = try! JSONSerialization.data(withJSONObject: evidence, options: [.sortedKeys])
        print("NATIVE_CHANNEL_EVIDENCE=" + String(data: data, encoding: .utf8)!)
        defaults.set(true, forKey: UpdateChannelSettings.experimentalKey)
        precondition(UpdateChannelSettings.selected(in: defaults) == .dev)
        precondition(defaults.string(forKey: "unrelatedPreference") == "untouched")
        precondition(UpdateChannelSettings.save(channel: "stable", revision: dev["revision"]!, in: defaults) == "saved")
        precondition(UpdateChannelSettings.save(channel: "dev", revision: dev["revision"]!, in: defaults) == "conflict")
        defaults.set(["channel": "foreign", "revision": UUID().uuidString], forKey: UpdateChannelSettings.key)
        precondition(UpdateChannelSettings.selected(in: defaults) == .stable)
        print("Channel opt-in, persisted/revoked preferences, fixed feeds, item isolation, explicit save and stale revisions passed")
    }
}
