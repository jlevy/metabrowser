import Foundation
import Testing
import WebKit
@testable import ShellCore

/// `PageFind` against a real `WKWebView` (mb-jkbp): a page shaped like the shell, a
/// navigation pane before a main pane that scrolls on its own, as the Find menu searches
/// it. Runs in a process of its own, with the other WebKit suites; see
/// `ignoreSIGPIPELikeTheApp`.
@Suite @MainActor struct PageFindWebKitTests {
    init() { ignoreSIGPIPELikeTheApp() }

    private final class LoadWatcher: NSObject, WKNavigationDelegate {
        var loaded = false
        func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) { loaded = true }
    }

    private let page = """
        <body style="margin:0;display:flex;height:100vh">
        <nav id="nav" style="width:200px;overflow:auto">Supported.md</nav>
        <main id="main" style="flex:1;overflow:auto">
          <h2>Supported Versions</h2><div style="height:4000px"></div>
          <p>Only the latest release is supported.</p>
        </main></body>
        """

    private func load() async -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()  // tests leave no cookies behind
        let webView = WKWebView(frame: NSRect(x: 0, y: 0, width: 900, height: 600), configuration: configuration)
        let watcher = LoadWatcher()
        webView.navigationDelegate = watcher
        webView.loadHTMLString(page, baseURL: URL(string: "http://127.0.0.1:8411/view/")!)
        #expect(await eventually { watcher.loaded })
        withExtendedLifetime(watcher) {}
        return webView
    }

    /// The selected text and the pane it is in, or nil with nothing selected.
    private func selected(_ webView: WKWebView) async throws -> [String]? {
        let found = try await webView.evaluateJavaScript("""
            (() => {
              const selection = getSelection();
              if (!selection.rangeCount || selection.isCollapsed) return null;
              const pane = selection.anchorNode.parentElement.closest("nav, main");
              return [selection.toString(), pane?.id ?? ""];
            })()
            """)
        return found as? [String]
    }

    @Test func searchesTheWholePageFromItsStartAndStepsBothWaysWrapping() async throws {
        let webView = await load()
        let find = PageFind()
        // Browser-like: the navigation pane's match is the first in the page.
        #expect(await find.search("supported", in: webView) == true)
        #expect(try await selected(webView) == ["Supported", "nav"])
        #expect(await find.step(.next, in: webView) == true)
        #expect(try await selected(webView) == ["Supported", "main"])
        #expect(await find.step(.next, in: webView) == true)
        let last = try await selected(webView)
        #expect(last == ["supported", "main"])
        // The main pane scrolled its last match into view.
        let scrolled = try await webView.evaluateJavaScript("document.getElementById('main').scrollTop") as? Double
        #expect((scrolled ?? 0) > 1000)
        // Past the last match it wraps to the first, and Previous goes back.
        #expect(await find.step(.next, in: webView) == true)
        #expect(try await selected(webView) == ["Supported", "nav"])
        #expect(await find.step(.previous, in: webView) == true)
        #expect(try await selected(webView) == last)
    }

    @Test func typingOnExtendsTheMatchWhereItIs() async throws {
        let webView = await load()
        let find = PageFind()
        #expect(await find.search("supported", in: webView) == true)
        #expect(await find.step(.next, in: webView) == true)
        #expect(try await selected(webView) == ["Supported", "main"])
        // A longer string that the same match still holds stays on it.
        #expect(await find.search("supported v", in: webView) == true)
        #expect(try await selected(webView) == ["Supported V", "main"])
    }

    @Test func nothingFoundAndAnEmptyStringSearchNothing() async throws {
        let webView = await load()
        let find = PageFind()
        #expect(await find.search("zebra", in: webView) == false)
        #expect(await find.search("", in: webView) == nil)
        #expect(await find.step(.next, in: webView) == nil)
    }

    /// The shell swaps the main pane's content without loading a page; find reads the
    /// page as it is now, not as it was when the bar opened.
    @Test func findsContentThePageReplacedInPlace() async throws {
        let webView = await load()
        let find = PageFind()
        #expect(await find.search("vulnerability", in: webView) == false)
        _ = try await webView.evaluateJavaScript(
            "document.getElementById('main').innerHTML = '<h2>Reporting a Vulnerability</h2>'; true")
        #expect(await find.search("vulnerability", in: webView) == true)
        #expect(try await selected(webView) == ["Vulnerability", "main"])
    }

    @Test func useSelectionMakesTheSelectedTextTheSearchString() async throws {
        let webView = await load()
        let find = PageFind()
        #expect(await find.selection(in: webView) == nil)
        _ = try await webView.evaluateJavaScript("""
            (() => {
              const range = document.createRange();
              range.selectNodeContents(document.querySelector("h2"));
              getSelection().removeAllRanges();
              getSelection().addRange(range);
              return true;
            })()
            """)
        let text = await find.selection(in: webView)
        #expect(text == "Supported Versions")
        find.use(text ?? "")
        #expect(find.query == "Supported Versions")
        // Next finds it again from the selection's end, wrapping: it is the only one.
        #expect(await find.step(.next, in: webView) == true)
        #expect(try await selected(webView) == ["Supported Versions", "main"])
    }
}
