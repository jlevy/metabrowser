import Foundation
import Testing
import WebKit
@testable import ShellCore

/// `PageReveal` against real WebKit navigations: the object `load` returns is the one
/// WebKit names in `didCommit` and `didFailProvisionalNavigation`, which is what lets a
/// window tell its own load's callbacks from a superseded one's. Each test holds the
/// load's response decision, so the commit or failure arrives after the window has moved
/// on, as one already on its way does. Runs in a process of its own, with the other
/// WebKit suites; see `ignoreSIGPIPELikeTheApp`. A test runs again on a new page if
/// WebKit's network process ends under its loads (`NetworkProcessLost`).
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
        /// Whether WebKit's network process ended under a load (`isNetworkProcessLoss`).
        private(set) var networkProcessEnded = false

        /// `eventually`, which gives up on this page once WebKit's network process ended
        /// under its loads.
        func eventually(_ condition: () -> Bool) async throws -> Bool {
            try await ShellCoreTests.eventually(unlessLost: { networkProcessEnded }, condition)
        }

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
            if isNetworkProcessLoss(error) { networkProcessEnded = true }
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

    /// Ends a page however its test ended: a run abandoned for `NetworkProcessLost` can
    /// leave response decisions held, which WebKit raises over if they go unanswered.
    private func finish(_ window: Window, _ server: LocalHTTPServer) {
        window.answerAll(.cancel)
        server.stop()
    }

    /// The load's commit arrives after the server failed (`superseded`), or, as a
    /// control, while it still runs.
    @Test(arguments: [false, true])
    func aLoadsCommitRevealsThePageOnlyIfNothingSupersededIt(superseded: Bool) async throws {
        try await rerunningIfTheNetworkProcessEnds {
            let (webView, window, server, url) = try page()
            defer { finish(window, server) }
            let load = webView.load(URLRequest(url: url))
            window.reveal.submitted(load)
            #expect(try await window.eventually { window.heldResponses.count == 1 })
            if superseded { window.reveal.supersede() }  // showFailure, before the commit arrives
            window.answerAll(.allow)
            #expect(try await window.eventually { window.commits.count == 1 })
            #expect(window.commits.first?.navigation === load)
            #expect(window.commits.first?.revealed == !superseded)
            withExtendedLifetime(webView) {}
        }
    }

    /// The load fails provisionally (its response refused) after the server failed, or,
    /// as a control, while it still runs.
    @Test(arguments: [false, true])
    func aLoadsProvisionalFailureIsReportedOnlyIfNothingSupersededIt(superseded: Bool) async throws {
        try await rerunningIfTheNetworkProcessEnds {
            let (webView, window, server, url) = try page()
            defer { finish(window, server) }
            let load = webView.load(URLRequest(url: url))
            window.reveal.submitted(load)
            #expect(try await window.eventually { window.heldResponses.count == 1 })
            if superseded { window.reveal.supersede() }
            window.answerAll(.cancel)
            #expect(try await window.eventually { window.failures.count == 1 })
            #expect(window.failures.first?.navigation === load)
            #expect(window.failures.first?.reported == !superseded)
            #expect(window.commits.isEmpty)
            withExtendedLifetime(webView) {}
        }
    }

    /// The server restarts and a replacement load starts while the old one waits: only
    /// the replacement reveals the page, and the old one's end changes nothing. Here WebKit
    /// ends the old one with a provisional failure that is not a cancel (WebKitErrorDomain
    /// 102 on macOS 26), which the Boolean took for the window's own: it showed a page
    /// error and never revealed the replacement's page.
    @Test func onlyTheReplacementLoadRevealsThePage() async throws {
        try await rerunningIfTheNetworkProcessEnds {
            let (webView, window, server, url) = try page()
            defer { finish(window, server) }
            let old = webView.load(URLRequest(url: url))
            window.reveal.submitted(old)
            #expect(try await window.eventually { window.heldResponses.count == 1 })
            window.reveal.supersede()  // showStarting
            let new = webView.load(URLRequest(url: try #require(URL(string: url.absoluteString + "?after-restart"))))
            window.reveal.submitted(new)
            #expect(try await window.eventually { window.heldResponses.count == 2 })
            window.answerAll(.allow)
            #expect(try await window.eventually { window.commits.contains { $0.navigation === new } })
            #expect(window.commits.filter { $0.revealed }.map { $0.navigation } == [new])
            #expect(!window.failures.contains { $0.reported })
            withExtendedLifetime(webView) {}
        }
    }

    /// What a window remembers of a load on its way, when Command-R loads its page again
    /// (review A5 on #433). While the load waits, `webView.url` names the page it is loading
    /// and the current history item the page committed before it, so the window remembers
    /// the page in flight before it stops the load; this records what `url` names after the
    /// stop, which is why the remembering comes first.
    @Test func aLoadOnItsWayIsTheURLUntilItStops() async throws {
        try await rerunningIfTheNetworkProcessEnds {
            let (webView, window, server, url) = try page()
            defer { finish(window, server) }
            webView.load(URLRequest(url: url))
            #expect(try await window.eventually { window.heldResponses.count == 1 })
            window.answerAll(.allow)
            #expect(try await window.eventually { window.commits.count == 1 })
            let committed = try #require(webView.url)
            let next = try #require(URL(string: url.absoluteString + "?next"))
            webView.load(URLRequest(url: next))
            #expect(webView.url == next, "the load's page, as soon as it is submitted")
            #expect(try await window.eventually { window.heldResponses.count == 1 })
            #expect(webView.url == next, "the load's page, while its response waits")
            #expect(webView.backForwardList.currentItem?.url == committed)
            webView.stopLoading()
            window.answerAll(.cancel)
            #expect(try await window.eventually { webView.url == committed }, "after the stop, the committed page again")
            withExtendedLifetime(webView) {}
        }
    }
}
