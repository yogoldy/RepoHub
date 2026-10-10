import Foundation

@main struct MenuBridgeTests {
    static func main() {
        let url = URL(string: "http://127.0.0.1:8767/menu.html")!
        var count = 0
        precondition(MenuBridge.isReportIssueURL(URL(string:"https://github.com/yogoldy/RepoHub/issues/12")!))
        for bad in ["http://github.com/yogoldy/RepoHub/issues/12", "https://github.com/other/RepoHub/issues/12",
                    "https://github.com/yogoldy/RepoHub/pull/12", "https://evil.example/yogoldy/RepoHub/issues/12",
                    "https://github.com/yogoldy/RepoHub/issues/12?secret=value", "https://github.com/yogoldy/RepoHub/issues/12#fragment",
                    "https://user@github.com/yogoldy/RepoHub/issues/12", "https://github.com:443/yogoldy/RepoHub/issues/12"] {
            precondition(!MenuBridge.isReportIssueURL(URL(string:bad)!)); count += 1
        }
        for action in ["requestNotifications", "notificationSettings", "privacySettings", "loginSettings", "openBackups", "toggleNotifications", "connectGitHub", "quit"] {
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
        precondition(MenuBridge.action(body:["action":"connectGitHub", "token":"forbidden"], frameURL:url, isMainFrame:true) == nil)
        for picker in ["chooseRepoHome", "chooseRepoFolders"] {
            let valid: [String:Any] = ["action":picker, "request_id":String(repeating:"a",count:24)]
            precondition(MenuBridge.action(body:valid,frameURL:url,isMainFrame:true)?.rawValue == picker); count += 1
            for bad: Any in [["action":picker], ["action":picker,"request_id":"../path"],
                             ["action":picker,"request_id":42], ["action":picker,"request_id":String(repeating:"a",count:24),"path":"/outside"]] {
                precondition(MenuBridge.action(body:bad,frameURL:url,isMainFrame:true) == nil); count += 1
            }
            precondition(MenuBridge.action(body:valid,frameURL:url,isMainFrame:false) == nil); count += 1
            precondition(MenuBridge.action(body:valid,frameURL:URL(string:"http://127.0.0.1:8767/views/test/index.html"),isMainFrame:true) == nil); count += 1
        }
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
        let manualPath = outside.resolvingSymlinksInPath().path
        var manual: [String: Any] = ["source_mode":"manual", "repos":[["id":"Outside-id", "name":"Outside", "path":manualPath]],
                                    "workspace_sources":[["id":"Outside-id", "path":manualPath]]]
        precondition(MenuBridge.repositoryURL(id:"Outside-id",status:manual)?.path == manualPath)
        manual["workspace_sources"] = [["id":"Other-id", "path":manualPath]]
        precondition(MenuBridge.repositoryURL(id:"Outside-id",status:manual) == nil)
        manual["workspace_sources"] = [["id":"Outside-id", "path":repo.path]]
        precondition(MenuBridge.repositoryURL(id:"Outside-id",status:manual) == nil)
        manual["workspace_sources"] = [["id":"Outside-id", "path":manualPath], ["id":"Outside-id", "path":manualPath]]
        precondition(MenuBridge.repositoryURL(id:"Outside-id",status:manual) == nil)
        manual["workspace_sources"] = [["id":"Outside-id", "path":manualPath], ["id":"Outside-id", "path":repo.path]]
        precondition(MenuBridge.repositoryURL(id:"Outside-id",status:manual) == nil)
        manual["workspace_sources"] = "invalid"
        precondition(MenuBridge.repositoryURL(id:"Outside-id",status:manual) == nil)
        count += 6
        print("\(count) menu bridge checks passed")
    }
}
