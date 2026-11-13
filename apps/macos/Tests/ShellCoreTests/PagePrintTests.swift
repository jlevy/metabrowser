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
/// Review G1: a page print is authorized by the document's security origin, through the
/// same check the window uses (`PagePrintRequests.allows`). A `/raw` response has the
/// server's URL but, under its CSP sandbox, an opaque origin.
@Suite struct PagePrintAuthorizationTests {
    init() { ignoreSIGPIPELikeTheApp() }

    /// The header `/raw` sends with active content on: `capabilities.raw_sandbox_csp`.
    private let rawSandbox = "Content-Security-Policy: sandbox allow-scripts allow-popups allow-forms allow-downloads"

    /// Loads `body` from a local server under `headers` and counts the print requests the
    /// window's check accepts, against a policy whose origin is that server's.
    private func serve(_ body: String, headers: [String]) async throws
        -> (webView: WKWebView, server: LocalHTTPServer, received: Recorder<Bool>, accepted: Recorder<Bool>)
    {
        let server = try LocalHTTPServer(body: Data(body.utf8), contentType: "text/html; charset=utf-8", headers: headers)
        let url = server.start()
        let port = try #require(url.port)
        let policy = NavigationPolicy(origin: URL(string: "http://127.0.0.1:\(port)"))
        let received = Recorder<Bool>()
        let accepted = Recorder<Bool>()
        let requests = PagePrintRequests { _, frame in
            received.append(frame.isMainFrame)
            if PagePrintRequests.allows(frame, under: policy, sheetOpen: false) { accepted.append(true) }
        }
        let configuration = WebConfiguration.make(pagePrints: requests)
        configuration.websiteDataStore = .nonPersistent()
        let webView = WKWebView(frame: .zero, configuration: configuration)
        let watcher = LoadWatcher()
        webView.navigationDelegate = watcher
        webView.load(URLRequest(url: url))
        #expect(await eventually { watcher.loaded })
        withExtendedLifetime(watcher) {}
        return (webView, server, received, accepted)
    }

    /// The defect: a sandboxed raw document, opened as a top-level window, called the
    /// handler directly, again and again, and every call opened a print panel.
    @Test func aSandboxedRawDocumentIsRefusedHoweverOftenItAsks() async throws {
        let page = """
            <script>
            const ask = () => window.webkit.messageHandlers.metabrowserPrint.postMessage(null);
            ask(); ask(); setTimeout(ask, 0);
            </script>
            """
        let (webView, server, received, accepted) = try await serve(page, headers: [rawSandbox])
        defer { server.stop() }
        _ = try await webView.evaluateJavaScript("for (let i = 0; i < 3; i++) window.webkit.messageHandlers.metabrowserPrint.postMessage(null); 0")
        #expect(await eventually { received.count >= 6 }, "the requests reach the handler: \(received.count)")
        #expect(received.all.allSatisfy { $0 }, "from the main frame")
        #expect(accepted.count == 0)
        withExtendedLifetime(webView) {}
    }

    /// The control: the server's own page, through the same check, prints.
    @Test func theServersOwnPagePrintsThroughTheSameCheck() async throws {
        let page = #"<button id="print" onclick="window.print()">Print</button>"#
        let (webView, server, received, accepted) = try await serve(page, headers: [])
        defer { server.stop() }
        _ = try await webView.evaluateJavaScript("document.getElementById('print').click(); 0")
        #expect(await eventually { accepted.count == 1 })
        #expect(received.count == 1)
        withExtendedLifetime(webView) {}
    }
}

/// Which page print requests a folder window answers, by the requesting document's origin.
@Suite struct PagePrintPolicyTests {
    private let policy = NavigationPolicy(origin: URL(string: "http://127.0.0.1:8412")!)

    @Test func theServersOwnOriginMayPrintFromTheMainFrameWhenNoSheetIsOpen() {
        #expect(policy.allowsPagePrint(scheme: "http", host: "127.0.0.1", port: 8412, isMainFrame: true, sheetOpen: false))
        #expect(!policy.allowsPagePrint(scheme: "http", host: "127.0.0.1", port: 8412, isMainFrame: true, sheetOpen: true))
        #expect(!policy.allowsPagePrint(scheme: "http", host: "127.0.0.1", port: 8412, isMainFrame: false, sheetOpen: false))
    }

    /// WebKit reports an opaque origin, such as a sandboxed document's, with no scheme and
    /// no host.
    @Test func anOpaqueOriginNeverPrints() {
        #expect(!policy.allowsPagePrint(scheme: "", host: "", port: 0, isMainFrame: true, sheetOpen: false))
        #expect(!policy.allowsPagePrint(scheme: "http", host: "", port: 8412, isMainFrame: true, sheetOpen: false))
    }

    @Test func noOtherOriginPrints() {
        for (scheme, host, port) in [
            ("http", "127.0.0.1", 8413), ("https", "127.0.0.1", 8412), ("http", "localhost", 8412),
            ("data", "", 0), ("http", "127.0.0.1", 0),
        ] {
            #expect(!policy.allowsPagePrint(scheme: scheme, host: host, port: port, isMainFrame: true, sheetOpen: false),
                "\(scheme)://\(host):\(port)")
        }
        #expect(!NavigationPolicy().allowsPagePrint(
            scheme: "http", host: "127.0.0.1", port: 8412, isMainFrame: true, sheetOpen: false))
    }

    /// WebKit reports a default port as 0.
    @Test func aDefaultPortIsTheSchemesOwn() {
        let standard = NavigationPolicy(origin: URL(string: "http://127.0.0.1")!)
        #expect(standard.allowsPagePrint(scheme: "http", host: "127.0.0.1", port: 0, isMainFrame: true, sheetOpen: false))
        #expect(standard.allowsPagePrint(scheme: "HTTP", host: "127.0.0.1", port: 80, isMainFrame: true, sheetOpen: false))
    }
}
