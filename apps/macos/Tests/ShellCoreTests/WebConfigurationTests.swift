import Foundation
import Testing
import WebKit
@testable import ShellCore

/// Counts the windows a page asks for.
private final class WindowRequests: NSObject, WKUIDelegate, WKNavigationDelegate {
    var count = 0
    var loaded = false

    func webView(
        _ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
        for action: WKNavigationAction, windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        count += 1
        return nil
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { loaded = true }
}

/// The popup rule in a real `WKWebView`: the navigation policy's tests cannot see it,
/// since WebKit decides before it asks the app (review finding B2 on #341). Runs in a
/// process of its own; see `ignoreSIGPIPELikeTheApp`.
@Suite struct WebConfigurationTests {
    init() { ignoreSIGPIPELikeTheApp() }

    /// A page of the folder's own server that opens two more of its pages as it loads.
    private let selfOpeningPage = """
        <script>
        window.open('/view/one');
        setTimeout(() => window.open('/view/two'), 0);
        </script>
        <button id="open" onclick="window.open('/view/three')">Open</button>
        """
    private let origin = URL(string: "http://127.0.0.1:8411/view/")!

    private func load(_ configuration: WKWebViewConfiguration) async -> (WKWebView, WindowRequests) {
        let webView = WKWebView(frame: .zero, configuration: configuration)
        let requests = WindowRequests()
        webView.uiDelegate = requests
        webView.navigationDelegate = requests
        webView.loadHTMLString(selfOpeningPage, baseURL: origin)
        #expect(await eventually { requests.loaded })
        try? await Task.sleep(for: .milliseconds(200))  // the timer's window.open
        return (webView, requests)
    }

    private static func ephemeral(_ configuration: WKWebViewConfiguration) -> WKWebViewConfiguration {
        configuration.websiteDataStore = .nonPersistent()  // tests leave no cookies behind
        return configuration
    }

    @Test func aPageCannotOpenWindowsByItself() async {
        let (webView, requests) = await load(Self.ephemeral(WebConfiguration.make()))
        #expect(requests.count == 0)
        withExtendedLifetime(webView) {}
    }

    /// The control: WebKit's own default lets the same page open both windows, so the
    /// test above sees the setting and not a page that never ran.
    @Test func macOSWouldLetItWithoutTheRule() async {
        let (webView, requests) = await load(Self.ephemeral(WKWebViewConfiguration()))
        #expect(requests.count == 2)
        withExtendedLifetime(webView) {}
    }

    /// Script the app evaluates runs with a user gesture, as a click does, so a page's
    /// own button still opens its window.
    @Test func aUserActivatedWindowStillOpens() async throws {
        let (webView, requests) = await load(Self.ephemeral(WebConfiguration.make()))
        _ = try await webView.evaluateJavaScript("document.getElementById('open').click()")
        #expect(await eventually { requests.count == 1 })
    }

    @Test func aChildWindowsConfigurationIsRestrictedToo() {
        let configuration = WKWebViewConfiguration()
        #expect(configuration.preferences.javaScriptCanOpenWindowsAutomatically)  // the macOS default
        WebConfiguration.restrict(configuration)
        #expect(!configuration.preferences.javaScriptCanOpenWindowsAutomatically)
    }
}
