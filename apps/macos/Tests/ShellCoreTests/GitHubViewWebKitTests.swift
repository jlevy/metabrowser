import AppKit
import Foundation
import Testing
import WebKit
@testable import ShellCore

/// Counts the windows a page asks for, and whether it loaded.
private final class PageWatcher: NSObject, WKUIDelegate, WKNavigationDelegate {
    var loaded = false
    var windows = 0

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { loaded = true }

    func webView(
        _ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
        for action: WKNavigationAction, windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        windows += 1
        return nil
    }
}

/// The GitHub view's store and the toggle's script in a real `WKWebView` (mb-lxgw). Runs in
/// a process of its own, with the other WebKit suites; see `ignoreSIGPIPELikeTheApp`.
@Suite struct GitHubViewWebKitTests {
    init() { ignoreSIGPIPELikeTheApp() }

    private let origin = URL(string: "http://127.0.0.1:8411/view/")!
    /// A view header's toggle, as `static/github-page.js` draws it, and a plain link to the
    /// same page, which is not the toggle.
    private let page = """
        <span class="view-header-toggle"><a id="toggle" data-view-toggle="github" target="_blank"
          href="https://github.com/octo/demo/blob/main/README.md" style="display:block;width:400px;height:300px"
          ><span id="mark">GitHub</span></a></span>
        <a id="plain" target="_blank" href="https://github.com/octo/demo/blob/main/README.md">README</a>
        """

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

    // MARK: - The store

    /// Every GitHub view is built on the one persistent store, never a fresh or an
    /// ephemeral one, so a sign-in holds in every tab and window and after a relaunch.
    @Test func everyGitHubViewSharesOnePersistentStore() {
        let first = WebConfiguration.makeGitHub().websiteDataStore
        let second = WebConfiguration.makeGitHub().websiteDataStore
        #expect(first === second)
        #expect(first === GitHubDataStore.shared)
        #expect(first.isPersistent && second.isPersistent)
        #expect(first.identifier == GitHubDataStore.identifier)
        #expect(GitHubDataStore.identifier.uuidString == "5DE648DD-D5B9-4F54-8403-7DAF088E158C")
    }

    /// The folders' pages keep the default store, apart from GitHub's.
    @Test func thePagesKeepTheDefaultStore() {
        let pages = WebConfiguration.make().websiteDataStore
        #expect(pages === WKWebsiteDataStore.default())
        #expect(pages.isPersistent)
        #expect(pages !== GitHubDataStore.shared)
        #expect(pages.identifier == nil)
    }

    /// A cookie a GitHub view keeps is every GitHub view's, and never a page's; clearing
    /// the store removes it.
    @Test func aCookieInOneGitHubViewIsInEveryOtherAndNotInThePages() async throws {
        let name = "mb-lxgw-test-\(UUID().uuidString)"
        let cookie = try #require(HTTPCookie(properties: [
            .domain: "github-view-test.invalid", .path: "/", .name: name, .value: "signed-in",
            .expires: Date().addingTimeInterval(3600),
        ]))
        let first = WebConfiguration.makeGitHub().websiteDataStore.httpCookieStore
        await first.setCookie(cookie)
        let second = WebConfiguration.makeGitHub().websiteDataStore.httpCookieStore
        #expect(await second.allCookies().contains { $0.name == name })
        #expect(await !WebConfiguration.make().websiteDataStore.httpCookieStore.allCookies().contains { $0.name == name })
        await second.deleteCookie(cookie)
        #expect(await !first.allCookies().contains { $0.name == name })
    }

    // MARK: - The toggle

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
    /// does what it would without the app, asking for a window.
    @Test func aScriptedClickIsLeftToTheLink() async throws {
        let hrefs = Recorder<String>()
        let requests = GitHubViewRequests { _, _, href in hrefs.append(href) }
        let (webView, watcher) = await load(page, requests: requests)
        _ = try await webView.evaluateJavaScript("document.getElementById('mark').click()")
        #expect(await eventually { watcher.windows == 1 })
        #expect(hrefs.count == 0)
        withExtendedLifetime(webView) {}
    }

    /// The user's click on the toggle reaches the app with its page, and nothing opens; a
    /// Command-click, and a click on a plain link to the same page, are left to the link.
    @Test func theUsersClickOnTheToggleReachesTheAppAlone() async throws {
        let hrefs = Recorder<String>()
        let requests = GitHubViewRequests { _, frame, href in
            if frame.isMainFrame { hrefs.append(href) }
        }
        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 600, height: 400), styleMask: [.titled], backing: .buffered,
            defer: false)
        let (webView, watcher) = await load(page, requests: requests, in: NSRect(x: 0, y: 0, width: 600, height: 400))
        window.contentView = webView
        window.orderFrontRegardless()
        defer { window.orderOut(nil) }

        // Inside the toggle's link, near the page's top left.
        click(webView, at: NSPoint(x: 100, y: 300), in: window)
        #expect(await eventually(within: .seconds(10)) { hrefs.count == 1 })
        #expect(hrefs.all == ["https://github.com/octo/demo/blob/main/README.md"])
        #expect(watcher.windows == 0)

        click(webView, at: NSPoint(x: 100, y: 300), in: window, modifiers: .command)
        #expect(await eventually(within: .seconds(10)) { watcher.windows == 1 })
        #expect(hrefs.count == 1)
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

    /// View > Show GitHub View asks the page, in the app's world, for its toggle's page.
    @Test func theQueryFindsTheTogglesPageOrNone() async throws {
        let requests = GitHubViewRequests { _, _, _ in }
        let (webView, _) = await load(page, requests: requests)
        let found = try await webView.evaluateJavaScript(
            GitHubViewRequests.query, in: nil, contentWorld: GitHubViewRequests.world)
        #expect(found as? String == "https://github.com/octo/demo/blob/main/README.md")

        let (plain, _) = await load("<a href='https://github.com/octo/demo'>demo</a>", requests: requests)
        let none = try await plain.evaluateJavaScript(
            GitHubViewRequests.query, in: nil, contentWorld: GitHubViewRequests.world)
        #expect(none as? String == "")
    }
}
