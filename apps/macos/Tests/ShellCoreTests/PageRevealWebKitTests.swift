import Foundation
import Testing
import WebKit
@testable import ShellCore

/// `PageReveal` against real WebKit navigations: the object `load` returns is the one
/// WebKit names in `didCommit` and `didFailProvisionalNavigation`, which is what lets a
/// window tell its own load's callbacks from a superseded one's. Each test holds the
/// load's response decision, so the commit or failure arrives after the window has moved
/// on, as one already on its way does. Runs in a process of its own, with the other
/// WebKit suites; see `ignoreSIGPIPELikeTheApp`.
@Suite struct PageRevealWebKitTests {
    init() { ignoreSIGPIPELikeTheApp() }

    /// The window's part of the navigation delegate: it asks `PageReveal` about each
    /// commit and provisional failure, and records the answer.
    private final class Window: NSObject, WKNavigationDelegate {
        var reveal = PageReveal<WKNavigation>()
        /// Every response decision, held until the test answers it. WebKit raises if one
        /// is released unanswered, so `answerAll` answers each.
        private(set) var heldResponses: [(WKNavigationResponsePolicy) -> Void] = []
        private(set) var commits: [(navigation: WKNavigation?, revealed: Bool)] = []
        private(set) var failures: [(navigation: WKNavigation?, reported: Bool)] = []

        func webView(
            _ webView: WKWebView, decidePolicyFor response: WKNavigationResponse,
            decisionHandler: @escaping @MainActor (WKNavigationResponsePolicy) -> Void
        ) {
            heldResponses.append(decisionHandler)
        }

        func webView(_ webView: WKWebView, didCommit navigation: WKNavigation!) {
            commits.append((navigation, reveal.reveals(onCommit: navigation)))
        }

        func webView(
            _ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: any Error
        ) {
            let cancelled = (error as NSError).code == NSURLErrorCancelled
            failures.append((navigation, reveal.reports(failureOf: navigation, cancelled: cancelled)))
        }

        func answerAll(_ policy: WKNavigationResponsePolicy) {
            let held = heldResponses
            heldResponses = []
            held.forEach { $0(policy) }
        }
    }

    private func page() throws -> (webView: WKWebView, window: Window, server: LocalHTTPServer, url: URL) {
        let server = try LocalHTTPServer(body: Data("<p>page</p>".utf8), contentType: "text/html; charset=utf-8")
        let url = server.start()
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()  // tests leave no cookies behind
        let webView = WKWebView(frame: .zero, configuration: configuration)
        let window = Window()
        webView.navigationDelegate = window
        return (webView, window, server, url)
    }

    /// The load's commit arrives after the server failed (`superseded`), or, as a
    /// control, while it still runs.
    @Test(arguments: [false, true])
    func aLoadsCommitRevealsThePageOnlyIfNothingSupersededIt(superseded: Bool) async throws {
        let (webView, window, server, url) = try page()
        defer { server.stop() }
        let load = webView.load(URLRequest(url: url))
        window.reveal.submitted(load)
        #expect(await eventually { window.heldResponses.count == 1 })
        if superseded { window.reveal.supersede() }  // showFailure, before the commit arrives
        window.answerAll(.allow)
        #expect(await eventually { window.commits.count == 1 })
        #expect(window.commits.first?.navigation === load)
        #expect(window.commits.first?.revealed == !superseded)
        withExtendedLifetime(webView) {}
    }

    /// The load fails provisionally (its response refused) after the server failed, or,
    /// as a control, while it still runs.
    @Test(arguments: [false, true])
    func aLoadsProvisionalFailureIsReportedOnlyIfNothingSupersededIt(superseded: Bool) async throws {
        let (webView, window, server, url) = try page()
        defer { server.stop() }
        let load = webView.load(URLRequest(url: url))
        window.reveal.submitted(load)
        #expect(await eventually { window.heldResponses.count == 1 })
        if superseded { window.reveal.supersede() }
        window.answerAll(.cancel)
        #expect(await eventually { window.failures.count == 1 })
        #expect(window.failures.first?.navigation === load)
        #expect(window.failures.first?.reported == !superseded)
        #expect(window.commits.isEmpty)
        withExtendedLifetime(webView) {}
    }

    /// The server restarts and a replacement load starts while the old one waits: only
    /// the replacement reveals the page, and the old one's end changes nothing. Here WebKit
    /// ends the old one with a provisional failure that is not a cancel (WebKitErrorDomain
    /// 102 on macOS 26), which the Boolean took for the window's own: it showed a page
    /// error and never revealed the replacement's page.
    @Test func onlyTheReplacementLoadRevealsThePage() async throws {
        let (webView, window, server, url) = try page()
        defer { server.stop() }
        let old = webView.load(URLRequest(url: url))
        window.reveal.submitted(old)
        #expect(await eventually { window.heldResponses.count == 1 })
        window.reveal.supersede()  // showStarting
        let new = webView.load(URLRequest(url: try #require(URL(string: url.absoluteString + "?after-restart"))))
        window.reveal.submitted(new)
        #expect(await eventually { window.heldResponses.count == 2 })
        window.answerAll(.allow)
        #expect(await eventually { window.commits.contains { $0.navigation === new } })
        #expect(window.commits.filter { $0.revealed }.map { $0.navigation } == [new])
        #expect(!window.failures.contains { $0.reported })
        withExtendedLifetime(webView) {}
    }
}
