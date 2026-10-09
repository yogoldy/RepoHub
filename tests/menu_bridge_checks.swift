import Foundation

@main struct MenuBridgeTests {
    static func main() {
        let url = URL(string: "http://127.0.0.1:8767/menu.html")!
        var count = 0
        for action in ["openBackups", "toggleNotifications", "quit"] {
            precondition(MenuBridge.action(body: ["action":action], frameURL: url, isMainFrame: true)?.rawValue == action)
            count += 1
        }
        for badURL in ["https://127.0.0.1:8767/menu.html", "http://127.0.0.1:8768/menu.html",
                       "http://localhost:8767/menu.html", "http://example.com:8767/menu.html",
                       "http://127.0.0.1:8767/", "http://127.0.0.1:8767/views/123/menu.html"] {
            precondition(MenuBridge.action(body: ["action":"openBackups"], frameURL: URL(string:badURL), isMainFrame: true) == nil)
            count += 1
        }
        for body: Any in ["openBackups", ["action":"openPath"], ["action":"openBackups", "path":"/outside"],
                          ["action":42], [:] as [String:Any]] {
            precondition(MenuBridge.action(body: body, frameURL: url, isMainFrame: true) == nil)
            count += 1
        }
        precondition(MenuBridge.action(body: ["action":"quit"], frameURL: url, isMainFrame: false) == nil)
        precondition(MenuBridge.action(body: ["action":"quit"], frameURL: nil, isMainFrame: true) == nil)
        count += 2
        let repoBody: [String: Any] = ["action":"openRepo", "repo_id":"Example-1234567890"]
        precondition(MenuBridge.action(body: repoBody, frameURL: url, isMainFrame: true) == .openRepo)
        count += 1
        for body: Any in [["action":"openRepo"], ["action":"openRepo", "repo_id":"../outside"],
                          ["action":"openRepo", "repo_id":"/Users/private"],
                          ["action":"openRepo", "repo_id":""], ["action":"openRepo", "repo_id":42],
                          ["action":"openRepo", "repo_id":String(repeating:"a",count:129)],
                          ["action":"openRepo", "repo_id":"Example", "path":"/outside"]] {
            precondition(MenuBridge.action(body: body, frameURL: url, isMainFrame: true) == nil)
            count += 1
        }
        precondition(MenuBridge.action(body: repoBody, frameURL: url, isMainFrame: false) == nil)
        count += 1
        let fixture = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("repohub-finder-" + UUID().uuidString)
        let root = fixture.appendingPathComponent("repos"), repo = root.appendingPathComponent("Example")
        let outside = fixture.appendingPathComponent("Outside"), linked = root.appendingPathComponent("Linked")
        let files = FileManager.default
        try! files.createDirectory(at: repo, withIntermediateDirectories: true)
        try! files.createDirectory(at: outside, withIntermediateDirectories: true)
        try! files.createSymbolicLink(at: linked, withDestinationURL: outside)
        defer { try? files.removeItem(at: fixture) }
        func status(_ name: String, _ path: String, _ rootPath: String? = nil) -> [String:Any] {
            ["repos_root":rootPath ?? root.path, "repos":[["id":"Example", "name":name, "path":path]]]
        }
        precondition(MenuBridge.repositoryURL(id: "Example", status: status("Example",repo.path))?.path == repo.path)
        count += 1
        for value in [status("Example",outside.path), status("../Outside",outside.path),
                      status("Linked",linked.path), status("Missing",root.appendingPathComponent("Missing").path),
                      status("Example",repo.path,"relative"), status("Example","relative"),
                      status("..",root.path), status("",root.path)] {
            precondition(MenuBridge.repositoryURL(id:"Example", status:value) == nil)
            count += 1
        }
        precondition(MenuBridge.repositoryURL(id:"missing",status:status("Example",repo.path)) == nil)
        count += 1
        print("\(count) menu bridge checks passed")
    }
}
