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
    var departures: [URL] = []
    var departureModifiers: [NSEvent.ModifierFlags] = []

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { loaded = true }

    func webView(
        _ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
        decisionHandler: @escaping @MainActor (WKNavigationActionPolicy) -> Void
    ) {
        // A link with a target of a new window asks here first, with no target frame, and
        // then for the window.
        guard action.navigationType == .linkActivated, action.targetFrame != nil, let url = action.request.url else {
            return decisionHandler(.allow)
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
    /// marked `external`, which opens a new window. Below it, a plain link to the same page,
    /// which is neither. Each link is a 200 by 100 block at a known place in a 600 by 400
    /// web view: `open` from (300, 20), `external` from (300, 120), and the plain link
    /// from (300, 250), in CSS pixels from the top left.
    private var page: String {
        """
        <body style="margin:0">
        <div data-view-on-github style="position:absolute;left:300px;top:20px">
          <a id="open" data-view-on-github="open" href="\(readme)"
            style="display:block;width:200px;height:100px"><span id="mark">View on GitHub</span></a>
          <a id="external" data-view-on-github="external" target="_blank" href="\(readme)"
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
        #expect(await eventually { watcher.departures.map(\.absoluteString) == [readme] })
        _ = try await webView.evaluateJavaScript("document.getElementById('external').click()")
        #expect(await eventually { watcher.windows == 1 })
        #expect(requests.count == 0)
        withExtendedLifetime(webView) {}
    }

    /// The user's click on the button reaches the app with its page and where the button
    /// is, and the page goes nowhere. A Command-click on it, a click on the menu's Open in
    /// Browser, and a click on a plain link to the same page are each left to the link: the
    /// marker, not the address, picks the button.
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

        // WebKit follows a Command-click on a link in place, with the modifier for the app's
        // policy to see (`NavigationPolicy.decide`, `wantsNewWindow`).
        click(webView, at: onOpen, in: window, modifiers: .command)
        #expect(await eventually(within: .seconds(10)) { watcher.departures.count == 1 })
        #expect(watcher.departures.map(\.absoluteString) == [readme])
        #expect(watcher.departureModifiers == [.command])
        click(webView, at: onExternal, in: window)
        #expect(await eventually(within: .seconds(10)) { watcher.windows == 1 })
        click(webView, at: onPlain, in: window)
        #expect(await eventually(within: .seconds(10)) { watcher.windows == 2 })
        #expect(watcher.departures.count == 1)
        #expect(requests.count == 1)
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
