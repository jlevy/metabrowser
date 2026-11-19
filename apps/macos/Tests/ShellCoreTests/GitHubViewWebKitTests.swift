import AppKit
import Foundation
import Testing
import WebKit
@testable import ShellCore

/// Counts the windows a page asks for, records the links it follows away from the fixture in
/// its own frame, which it cancels, and says whether the fixture loaded.
private final class PageWatcher: NSObject, WKUIDelegate, WKNavigationDelegate {
    var loaded = false
    var windows = 0
    /// The modifier keys of each new window's request, in order.
    var windowModifiers: [NSEvent.ModifierFlags] = []
    var departures: [URL] = []
    var departureModifiers: [NSEvent.ModifierFlags] = []
    /// Other loads away from the fixture, such as a GitHub view loading a page in place,
    /// which it cancels.
    var elsewhere: [URL] = []

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { loaded = true }

    func webView(
        _ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
        decisionHandler: @escaping @MainActor (WKNavigationActionPolicy) -> Void
    ) {
        // A link with a target of a new window asks here first, with no target frame, and
        // then for the window.
        guard let url = action.request.url, action.targetFrame != nil else { return decisionHandler(.allow) }
        guard action.navigationType == .linkActivated else {
            guard url.host() != nil, url.host() != "127.0.0.1" else { return decisionHandler(.allow) }
            elsewhere.append(url)
            return decisionHandler(.cancel)
        }
        departures.append(url)
        departureModifiers.append(action.modifierFlags)
        decisionHandler(.cancel)
    }

    func webView(
        _ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
        for action: WKNavigationAction, windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        windows += 1
        windowModifiers.append(action.modifierFlags)
        return nil
    }
}

/// View on GitHub's store and the button's script in a real `WKWebView` (mb-4wqh). Runs in
/// a process of its own, with the other WebKit suites; see `ignoreSIGPIPELikeTheApp`.
@Suite struct GitHubViewWebKitTests {
    init() { ignoreSIGPIPELikeTheApp() }

    private let origin = URL(string: "http://127.0.0.1:8411/view/")!
    private let readme = "https://github.com/octo/demo/blob/main/README.md"
    /// The View on GitHub button as the page's contract has it: a root marked
    /// `data-view-on-github`, its main link marked `open`, and its menu's Open in Browser
    /// marked `external`, each a link that opens a new window, as in the page's own markup.
    /// Below it, a plain link to the same page, which is neither. Each link is a 200 by 100
    /// block at a known place in a 600 by 400 web view: `open` from (300, 20), `external`
    /// from (300, 120), and the plain link from (300, 250), in CSS pixels from the top left.
    private var page: String { buttonPage(opening: readme) }

    /// `page`, with `href` as the `open` link's.
    private func buttonPage(opening href: String) -> String {
        """
        <body style="margin:0">
        <div data-view-on-github style="position:absolute;left:300px;top:20px">
          <a id="open" data-view-on-github="open" target="_blank" rel="noopener" href="\(href)"
            style="display:block;width:200px;height:100px"><span id="mark">View on GitHub</span></a>
          <a id="external" data-view-on-github="external" target="_blank" rel="noopener" href="\(readme)"
            style="display:block;width:200px;height:100px">Open in Browser</a>
        </div>
        <a id="plain" target="_blank" href="\(readme)"
          style="position:absolute;left:300px;top:250px;display:block;width:200px;height:100px">README</a>
        </body>
        """
    }

    private func load(
        _ html: String, requests: GitHubViewRequests, in frame: NSRect = .zero
    ) async -> (WKWebView, PageWatcher) {
        let configuration = WebConfiguration.make(gitHubViews: requests)
        configuration.websiteDataStore = .nonPersistent()  // tests leave no cookies behind
        let webView = WKWebView(frame: frame, configuration: configuration)
        let watcher = PageWatcher()
        webView.navigationDelegate = watcher
        webView.uiDelegate = watcher
        webView.loadHTMLString(html, baseURL: origin)
        #expect(await eventually { watcher.loaded })
        return (webView, watcher)
    }

    // MARK: - The store and the web view

    /// Every popover's web view is built on the one persistent store, never a fresh or an
    /// ephemeral one, so a sign-in holds in every tab and window and after a relaunch.
    @Test func everyGitHubViewSharesOnePersistentStore() {
        let first = WebConfiguration.makeGitHub().websiteDataStore
        let second = WebConfiguration.makeGitHub().websiteDataStore
        let view = WebConfiguration.makeGitHubWebView(isInspectable: false).configuration.websiteDataStore
        #expect(first === second && second === view)
        #expect(first === GitHubDataStore.shared)
        #expect(first.isPersistent && second.isPersistent && view.isPersistent)
        #expect(first.identifier == GitHubDataStore.identifier)
        #expect(GitHubDataStore.identifier.uuidString == "5DE648DD-D5B9-4F54-8403-7DAF088E158C")
    }

    /// The popover's web view is a plain `WKWebView`, with no file-drop handler of the app's
    /// (`DropAwareWebView.onFileDrop`), so a file dropped on github.com's comment box
    /// reaches github.com; and its zoom is its own, never the pages' remembered one.
    @Test func theGitHubViewTakesItsOwnDropsAndZoom() {
        UserDefaults.standard.set(1.5, forKey: "pageZoom")
        defer { UserDefaults.standard.removeObject(forKey: "pageZoom") }
        let view = WebConfiguration.makeGitHubWebView(isInspectable: false)
        #expect(type(of: view) == WKWebView.self)
        #expect(view.pageZoom == 1)
    }

    /// The folders' pages keep the default store, apart from GitHub's.
    @Test func thePagesKeepTheDefaultStore() {
        let pages = WebConfiguration.make().websiteDataStore
        #expect(pages === WKWebsiteDataStore.default())
        #expect(pages.isPersistent)
        #expect(pages !== GitHubDataStore.shared)
        #expect(pages.identifier == nil)
    }

    /// A cookie one popover's web view keeps is every popover's, and never a page's.
    @Test func aCookieInOneGitHubViewIsInEveryOtherAndNotInThePages() async throws {
        let name = "mb-4wqh-test-\(UUID().uuidString)"
        let cookie = try #require(HTTPCookie(properties: [
            .domain: "github-view-test.invalid", .path: "/", .name: name, .value: "signed-in",
            .expires: Date().addingTimeInterval(3600),
        ]))
        let first = WebConfiguration.makeGitHubWebView(isInspectable: false).configuration.websiteDataStore
        await first.httpCookieStore.setCookie(cookie)
        let second = WebConfiguration.makeGitHubWebView(isInspectable: false).configuration.websiteDataStore
        #expect(await second.httpCookieStore.allCookies().contains { $0.name == name })
        #expect(await !WebConfiguration.make().websiteDataStore.httpCookieStore.allCookies().contains { $0.name == name })
        await second.httpCookieStore.deleteCookie(cookie)
        #expect(await !first.httpCookieStore.allCookies().contains { $0.name == name })
    }

    // MARK: - The button

    /// The handler lives in the app's own content world: the page's scripts cannot see it.
    @Test func thePageCannotReachTheHandler() async throws {
        let requests = GitHubViewRequests { _, _, _ in }
        let (webView, _) = await load(page, requests: requests)
        let fromPage = try await webView.evaluateJavaScript(
            "typeof window.webkit?.messageHandlers?.\(GitHubViewRequests.handlerName)")
        #expect(fromPage as? String == "undefined")
        let fromApp = try await webView.evaluateJavaScript(
            "typeof window.webkit.messageHandlers.\(GitHubViewRequests.handlerName)", in: nil,
            contentWorld: GitHubViewRequests.world)
        #expect(fromApp as? String == "object")
    }

    /// A click a script dispatches is not the user's: it reaches no handler, and the link
    /// does what it would without the app.
    @Test func aScriptedClickIsLeftToTheLink() async throws {
        let requests = Recorder<GitHubViewRequests.Request>()
        let (webView, watcher) = await load(page, requests: GitHubViewRequests { _, _, request in
            requests.append(request)
        })
        _ = try await webView.evaluateJavaScript("document.getElementById('mark').click()")
        #expect(await eventually { watcher.windows == 1 })
        _ = try await webView.evaluateJavaScript("document.getElementById('external').click()")
        #expect(await eventually { watcher.windows == 2 })
        #expect(watcher.departures.isEmpty)
        #expect(requests.count == 0)
        withExtendedLifetime(webView) {}
    }

    /// The user's click on the button reaches the app with its page and where the button
    /// is, and the page goes nowhere: the script cancels the link's new window. A
    /// Command-click on it, a click on the menu's Open in Browser, and a click on a plain
    /// link to the same page are each left to the link: the marker, not the address, picks
    /// the button.
    @Test func theUsersClickOnTheButtonReachesTheAppAlone() async throws {
        let requests = Recorder<GitHubViewRequests.Request>()
        let gitHubViews = GitHubViewRequests { _, frame, request in
            if frame.isMainFrame { requests.append(request) }
        }
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 600, height: 400), styleMask: [.titled], backing: .buffered,
            defer: false)
        let (webView, watcher) = await load(page, requests: gitHubViews, in: NSRect(x: 0, y: 0, width: 600, height: 400))
        window.contentView = webView
        window.orderFrontRegardless()
        defer { window.orderOut(nil) }

        // Window points, up from the bottom of the 400-point window: the middle of each link.
        let onOpen = NSPoint(x: 400, y: 400 - 70)
        let onExternal = NSPoint(x: 400, y: 400 - 170)
        let onPlain = NSPoint(x: 400, y: 400 - 300)

        click(webView, at: onOpen, in: window)
        #expect(await eventually(within: .seconds(10)) { requests.count == 1 })
        let request = try #require(requests.all.first)
        #expect(request.page.absoluteString == readme)
        #expect(request.link == CGRect(x: 300, y: 20, width: 200, height: 100))
        #expect(request.viewportWidth == 600)
        // Where the popover points: the button, wherever WebKit puts its origin.
        let anchor = GitHubPopoverLayout.anchor(
            request.link, viewportWidth: request.viewportWidth, in: webView.bounds, flipped: webView.isFlipped)
        #expect(webView.convert(anchor, to: nil) == NSRect(x: 300, y: 400 - 120, width: 200, height: 100))
        #expect(watcher.departures.isEmpty && watcher.windows == 0)

        // A Command-click on the button asks for the link's new window, with the modifier.
        click(webView, at: onOpen, in: window, modifiers: .command)
        #expect(await eventually(within: .seconds(10)) { watcher.windows == 1 })
        #expect(watcher.windowModifiers == [.command])
        click(webView, at: onExternal, in: window)
        #expect(await eventually(within: .seconds(10)) { watcher.windows == 2 })
        click(webView, at: onPlain, in: window)
        #expect(await eventually(within: .seconds(10)) { watcher.windows == 3 })
        #expect(watcher.departures.isEmpty)
        #expect(requests.count == 1)
    }

    /// A click on a button whose link the app would not open, such as one longer than
    /// `GitHubLink.maximumLength`, is left to the link, which opens a new window, as a click
    /// on the menu's Open in Browser does, rather than cancelled for a request the window
    /// would drop.
    @Test func aLinkTheAppWouldNotOpenIsLeftToTheLink() async throws {
        let requests = Recorder<GitHubViewRequests.Request>()
        let gitHubViews = GitHubViewRequests { _, _, request in requests.append(request) }
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 600, height: 400), styleMask: [.titled], backing: .buffered,
            defer: false)
        let long = "https://github.com/octo/demo/blob/main/" + String(repeating: "a", count: GitHubLink.maximumLength)
        let (webView, watcher) = await load(
            buttonPage(opening: long), requests: gitHubViews, in: NSRect(x: 0, y: 0, width: 600, height: 400))
        window.contentView = webView
        window.orderFrontRegardless()
        defer { window.orderOut(nil) }

        click(webView, at: NSPoint(x: 400, y: 400 - 70), in: window)
        #expect(await eventually(within: .seconds(10)) { watcher.windows == 1 })
        #expect(watcher.windowModifiers == [[]])
        #expect(requests.count == 0)
    }

    /// Each link the script takes is one the window opens, at the same address: the script's
    /// test (`GitHubViewRequests.opensHere`) passes only an `href`, as WebKit serializes it,
    /// that `GitHubView.page` accepts unchanged. One that test leaves to the link, which
    /// opens in the default browser: over the length, another host or scheme, a user name,
    /// or a character Foundation would encode again (`|`, `^`, `[`, a second `#`).
    @Test func everyLinkTheScriptTakesIsOneTheWindowOpens() async throws {
        let (webView, _) = await load(page, requests: GitHubViewRequests { _, _, _ in })
        let longest = "https://github.com/" + String(repeating: "a", count: GitHubLink.maximumLength - 19)
        let cases: [(href: String, taken: Bool)] = [
            (readme, true), ("https://GitHub.com:443/octo/demo/tree/main", true),
            ("https://github.com/octo/demo/blob/main/docs/a b/雪 (1).md", true),
            ("https://github.com/octo/demo/blob/main/a.md?plain=1#L3-L9", true),
            ("https://github.com/octo/demo/blob/main/a'(b)!*~_.md", true), (longest, true),
            (longest + "a", false), ("https://github.com/octo/demo/blob/main/x|y^z.md", false),
            ("https://github.com/octo/demo/pulls?q=[1]", false), ("https://github.com/octo/demo#a#b", false),
            ("https://www.github.com/octo/demo", false), ("https://example.com/octo/demo", false),
            ("http://github.com/octo/demo", false), ("https://user@github.com/octo/demo", false),
            ("https://github.com.example.com/octo/demo", false),
        ]
        for (href, taken) in cases {
            let result = try await webView.callAsyncJavaScript(
                """
                const link = document.createElement("a");
                link.href = href;
                return [link.href, (\(GitHubViewRequests.opensHere))(link.href)];
                """, arguments: ["href": href], in: nil, contentWorld: .page)
            let pair = try #require(result as? [Any])
            let serialized = try #require(pair.first as? String)
            let takes = try #require(pair.last as? Bool)
            #expect(takes == taken, "\(href.prefix(80))")
            if takes { #expect(GitHubView.page(serialized)?.absoluteString == serialized, "\(href.prefix(80))") }
        }
    }

    // MARK: - The popover's web view as a UI delegate

    /// A GitHub view, as the popover makes it but with a store that leaves nothing behind,
    /// with `ui` as its UI delegate, on `html`.
    private func gitHubView(_ html: String, ui: GitHubViewUI) async -> (WKWebView, PageWatcher) {
        let configuration = WebConfiguration.makeGitHub()
        configuration.websiteDataStore = .nonPersistent()
        let webView = WKWebView(frame: NSRect(x: 0, y: 0, width: 600, height: 400), configuration: configuration)
        let watcher = PageWatcher()
        webView.navigationDelegate = watcher
        webView.uiDelegate = ui
        webView.loadHTMLString(html, baseURL: origin)
        #expect(await eventually { watcher.loaded })
        return (webView, watcher)
    }

    /// github.com's `alert`, `confirm`, and `prompt` reach the app, which answers them;
    /// without a delegate WebKit would answer `confirm` and `prompt` with Cancel.
    @Test func theGitHubViewsDialogsAreTheApps() async throws {
        let asked = Recorder<GitHubViewUI.Request>()
        let ui = GitHubViewUI(
            present: { request, answer in
                asked.append(request)
                switch request {
                case .alert: answer(.dismissed)
                case .confirm: answer(.confirmed(true))
                case .prompt: answer(.text("typed"))
                case .openFiles: answer(.files(nil))
                }
            }, openExternally: { _ in })
        let (webView, _) = await gitHubView("<p>A comment</p>", ui: ui)
        #expect(try await webView.evaluateJavaScript("confirm('Discard your changes?')") as? Bool == true)
        #expect(try await webView.evaluateJavaScript("prompt('Name?', 'octo')") as? String == "typed")
        _ = try await webView.evaluateJavaScript("alert('Saved'); 1")
        #expect(asked.all == [
            .confirm("Discard your changes?"), .prompt("Name?", defaultText: "octo"), .alert("Saved"),
        ])
    }

    /// Cancel, or an answer of another kind, is Cancel to the page.
    @Test func cancelIsCancel() async throws {
        let ui = GitHubViewUI(present: { _, answer in answer(.dismissed) }, openExternally: { _ in })
        let (webView, _) = await gitHubView("<p>A comment</p>", ui: ui)
        #expect(try await webView.evaluateJavaScript("confirm('Discard your changes?')") as? Bool == false)
        #expect(try await webView.evaluateJavaScript("prompt('Name?') === null") as? Bool == true)
    }

    /// "Click to add files": a file input asks the app for its panel, and gets the files
    /// the user chose.
    @Test func aFileInputOpensTheAppsPanel() async throws {
        let file = FileManager.default.temporaryDirectory.appending(path: "mb-4wqh-\(UUID().uuidString).txt")
        try Data("attached".utf8).write(to: file)
        defer { try? FileManager.default.removeItem(at: file) }
        let asked = Recorder<GitHubViewUI.Request>()
        let ui = GitHubViewUI(
            present: { request, answer in
                asked.append(request)
                answer(.files([file]))
            }, openExternally: { _ in })
        let (webView, _) = await gitHubView("<input id='files' type='file' multiple>", ui: ui)
        _ = try await webView.evaluateJavaScript("document.getElementById('files').click()")
        #expect(await eventually(within: .seconds(10)) { asked.count == 1 })
        #expect(asked.all == [.openFiles(multiple: true, directories: false)])
        var name = ""
        for _ in 0..<100 where name != file.lastPathComponent {
            try await Task.sleep(for: .milliseconds(100))
            name = try await webView.evaluateJavaScript(
                "document.getElementById('files').files[0]?.name ?? ''") as? String ?? ""
        }
        #expect(name == file.lastPathComponent)
    }

    /// A new window to GitHub loads in the view itself; anything else on the web goes to the
    /// default browser.
    @Test func aNewWindowLoadsHereOrOpensTheBrowser() async throws {
        let opened = Recorder<URL>()
        let ui = GitHubViewUI(present: { _, answer in answer(.dismissed) }, openExternally: { opened.append($0) })
        let (webView, watcher) = await gitHubView("<p>A comment</p>", ui: ui)
        _ = try await webView.evaluateJavaScript("window.open('https://example.com/docs'); 1")
        #expect(await eventually(within: .seconds(10)) { opened.count == 1 })
        #expect(opened.all.map(\.absoluteString) == ["https://example.com/docs"])
        _ = try await webView.evaluateJavaScript("window.open('\(readme)'); 1")
        #expect(await eventually(within: .seconds(10)) { watcher.elsewhere.map(\.absoluteString) == [readme] })
        #expect(opened.count == 1)
    }

    /// Text the user typed and has not sent keeps a closed popover's web view; what the page
    /// put in a field, and a password, do not.
    @Test func theProbeFindsTextNotYetSent() async throws {
        let ui = GitHubViewUI(present: { _, answer in answer(.dismissed) }, openExternally: { _ in })
        let (webView, _) = await gitHubView(
            """
            <textarea id="comment"></textarea><input id="title" value="Fix"><input id="secret" type="password">
            <input id="flag" type="checkbox">
            """, ui: ui)
        func unsent() async throws -> Bool? {
            try await webView.evaluateJavaScript(
                GitHubPopoverState.unsentTextProbe, in: nil, contentWorld: .defaultClient) as? Bool
        }
        #expect(try await unsent() == false)
        _ = try await webView.evaluateJavaScript("document.getElementById('comment').value = 'A draft'; 1")
        #expect(try await unsent() == true)
        _ = try await webView.evaluateJavaScript(
            "document.getElementById('comment').value = ''; document.getElementById('title').value = 'Fix it'; 1")
        #expect(try await unsent() == true)
        _ = try await webView.evaluateJavaScript(
            """
            document.getElementById('title').value = 'Fix';
            document.getElementById('secret').value = 'hunter2';
            document.getElementById('flag').checked = true; 1
            """)
        #expect(try await unsent() == false)
    }

    private func click(
        _ webView: WKWebView, at point: NSPoint, in window: NSWindow, modifiers: NSEvent.ModifierFlags = []
    ) {
        for type in [NSEvent.EventType.leftMouseDown, .leftMouseUp] {
            guard let event = NSEvent.mouseEvent(
                with: type, location: point, modifierFlags: modifiers, timestamp: ProcessInfo.processInfo.systemUptime,
                windowNumber: window.windowNumber, context: nil, eventNumber: 0, clickCount: 1, pressure: 1)
            else { continue }
            if type == .leftMouseDown { webView.mouseDown(with: event) } else { webView.mouseUp(with: event) }
        }
    }
}
