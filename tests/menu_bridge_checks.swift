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
        print("\(count) menu bridge checks passed")
    }
}
