import WebKit

/// The view header's GitHub toggle, chosen in a folder window (`GitHubView`).
///
/// The toggle's GitHub mark is a link to the item's page on github.com that opens a new
/// window, which a browser opens as a tab and the app would send to the default browser
/// (`NavigationPolicy.decideNewWindow`). A user script, installed by `WebConfiguration.make`
/// in each page's main frame, takes a trusted primary click with no modifier key on a link
/// marked `data-view-toggle="github"` (`marker`), cancels the link's own action, and posts
/// its `href` to this handler, and the window shows the page in its GitHub view instead.
///
/// The script and the handler live in a content world of the app's own (`world`), so the
/// page's scripts cannot post to the handler, and a click a script dispatches is not
/// trusted: only the user's click on the page's toggle, or a key that activates it, reaches
/// the app. A click with Command, Shift, Option, or Control, or with another button, is
/// left to WebKit, which opens the page in the default browser as before. The page itself
/// only marks its link; nothing in it knows about the app.
public final class GitHubViewRequests: NSObject, WKScriptMessageHandler {
    public static let handlerName = "metabrowserGitHubView"
    /// The toggle's GitHub link, as `toggle` in `static/github-page.js` marks it.
    public static let marker = #"a[data-view-toggle="github"]"#
    /// The app's own content world, where the script runs and the handler answers.
    public static var world: WKContentWorld { .defaultClient }

    static let source = """
        window.addEventListener("click", (event) => {
            if (!event.isTrusted || event.button !== 0 || event.metaKey || event.ctrlKey
                || event.shiftKey || event.altKey) {
                return;
            }
            const link = event.target instanceof Element ? event.target.closest('\(marker)') : null;
            if (!(link instanceof HTMLAnchorElement)) {
                return;
            }
            event.preventDefault();
            window.webkit.messageHandlers.\(handlerName).postMessage(link.href);
        }, true);
        """

    /// Evaluated in `world` for View > Show GitHub View: the page's toggle's `href`, or an
    /// empty string on a page with no toggle or with an opaque origin, such as a `/raw`
    /// file's under its CSP sandbox, as `allows` refuses a click there.
    public static let query = """
        window.origin === "null" ? "" : document.querySelector('\(marker)')?.href ?? ""
        """

    private let onRequest: (WKWebView, WKFrameInfo, String) -> Void

    /// `onRequest` gets the web view, the frame that asked, and the link's `href`.
    public init(onRequest: @escaping (WKWebView, WKFrameInfo, String) -> Void) {
        self.onRequest = onRequest
    }

    func install(in configuration: WKWebViewConfiguration) {
        let controller = configuration.userContentController
        controller.addUserScript(WKUserScript(
            source: Self.source, injectionTime: .atDocumentStart, forMainFrameOnly: true, in: Self.world))
        controller.add(self, contentWorld: Self.world, name: Self.handlerName)
    }

    public func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let webView = message.webView, let href = message.body as? String else { return }
        onRequest(webView, message.frameInfo, href)
    }
}

extension GitHubViewRequests {
    /// Whether a window shows the GitHub view for a toggle in `frame`: only the main frame
    /// of a document of the server's own origin, as for the page's Print button
    /// (`PagePrintRequests.allows`), so a `/raw` HTML file, whose CSP sandbox gives it an
    /// opaque origin, cannot use a marked link of its own.
    public static func allows(_ frame: WKFrameInfo, under policy: NavigationPolicy) -> Bool {
        let origin = frame.securityOrigin
        return policy.isAppDocument(
            scheme: origin.protocol, host: origin.host, port: origin.port, isMainFrame: frame.isMainFrame)
    }
}
