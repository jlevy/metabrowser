import Foundation
import Testing
import WebKit
@testable import ShellCore

private final class LoadWatcher: NSObject, WKNavigationDelegate {
    var loaded = false
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { loaded = true }
}

/// The page's Print button in a real `WKWebView` (mb-j3eu). WebKit on macOS hands a
/// page's `window.print()` only to private delegate methods, so it did nothing; the
/// configuration's script hands it to the app instead. Runs in a process of its own,
/// with the other WebKit suites; see `ignoreSIGPIPELikeTheApp`.
@Suite struct PagePrintTests {
    init() { ignoreSIGPIPELikeTheApp() }

    private let page = """
        <button id="print" onclick="window.print()">Print</button>
        <iframe srcdoc="<p>inner</p>"></iframe>
        """

    @Test func thePagesPrintReachesTheAppFromItsMainFrameOnly() async throws {
        let frames = Recorder<Bool>()
        let requests = PagePrintRequests { _, frame in frames.append(frame.isMainFrame) }
        let configuration = WebConfiguration.make(pagePrints: requests)
        configuration.websiteDataStore = .nonPersistent()  // tests leave no cookies behind
        let webView = WKWebView(frame: .zero, configuration: configuration)
        let watcher = LoadWatcher()
        webView.navigationDelegate = watcher
        webView.loadHTMLString(page, baseURL: URL(string: "http://127.0.0.1:8411/view/")!)
        #expect(await eventually { watcher.loaded })

        _ = try await webView.evaluateJavaScript("document.getElementById('print').click()")
        #expect(await eventually { frames.count == 1 })
        #expect(frames.all == [true])

        // A frame inside the page keeps WebKit's own print, which reaches nothing.
        _ = try await webView.evaluateJavaScript("document.querySelector('iframe').contentWindow.print()")
        try await Task.sleep(for: .milliseconds(200))
        #expect(frames.count == 1)
        withExtendedLifetime(webView) {}
    }

    /// Without the script, as before the fix: the page's print reaches no handler.
    @Test func withoutTheScriptThePagesPrintReachesNothing() async throws {
        let frames = Recorder<Bool>()
        let requests = PagePrintRequests { _, frame in frames.append(frame.isMainFrame) }
        let configuration = WebConfiguration.make()
        configuration.websiteDataStore = .nonPersistent()
        configuration.userContentController.add(requests, name: PagePrintRequests.handlerName)
        let webView = WKWebView(frame: .zero, configuration: configuration)
        let watcher = LoadWatcher()
        webView.navigationDelegate = watcher
        webView.loadHTMLString(page, baseURL: URL(string: "http://127.0.0.1:8411/view/")!)
        #expect(await eventually { watcher.loaded })
        _ = try await webView.evaluateJavaScript("document.getElementById('print').click()")
        try await Task.sleep(for: .milliseconds(200))
        #expect(frames.count == 0)
        withExtendedLifetime(webView) {}
    }
}

/// Which page print requests a folder window answers.
@Suite struct PagePrintPolicyTests {
    private let policy = NavigationPolicy(origin: URL(string: "http://127.0.0.1:8412")!)

    @Test func theServersOwnPageMayPrintWhenNoSheetIsOpen() {
        let page = URL(string: "http://127.0.0.1:8412/view/docs/a.md")!
        #expect(policy.allowsPagePrint(from: page, isMainFrame: true, sheetOpen: false))
        #expect(!policy.allowsPagePrint(from: page, isMainFrame: true, sheetOpen: true), "one print at a time")
        #expect(!policy.allowsPagePrint(from: page, isMainFrame: false, sheetOpen: false))
    }

    @Test func noOtherPageMay() {
        for other in ["data:text/html,<p>x", "about:blank", "http://127.0.0.1:8413/view/", "https://example.com/"] {
            #expect(!policy.allowsPagePrint(from: URL(string: other), isMainFrame: true, sheetOpen: false), "\(other)")
        }
        #expect(!policy.allowsPagePrint(from: nil, isMainFrame: true, sheetOpen: false))
        #expect(!NavigationPolicy().allowsPagePrint(
            from: URL(string: "http://127.0.0.1:8412/view/"), isMainFrame: true, sheetOpen: false))
    }
}
