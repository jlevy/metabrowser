import CoreGraphics
import WebKit

/// A page's marked link, clicked in a folder window, which opens a web pane in a popover
/// (`WebSite`, `WebPopover`).
///
/// A page marks a link `data-web-view="open"` (`marker`), as the View on GitHub button's
/// main link is. A user script, installed by `WebConfiguration.make` in each page's main
/// frame, takes a trusted primary click with no modifier key on that link, when its `href`
/// is one the app opens (`opensHere`), cancels the link's own navigation, and posts its
/// `href` and where it sits on screen to this handler, and the window opens its pane there
/// instead (`Request`).
///
/// The script and the handler live in a content world of the app's own (`world`), so the
/// page's scripts cannot post to the handler, and a click a script dispatches is not
/// trusted: only the user's click on the page's link, or a key that activates it, reaches
/// the app. A click with Command, Shift, Option, or Control, or with another button, is
/// left to WebKit, which opens the page in the default browser. A link marked
/// `data-web-view="external"`, such as the View on GitHub menu's Open in Browser, is not
/// the marker: it opens a new window, which the app hands to the default browser. The page
/// itself only marks its links; nothing in it knows about the app.
public final class WebViewRequests: NSObject, WKScriptMessageHandler {
    public static let handlerName = "metabrowserWebView"
    /// A link that opens in a web pane, as the page marks it.
    public static let marker = #"a[data-web-view="open"]"#
    /// The app's own content world, where the script runs and the handler answers.
    public static var world: WKContentWorld { .defaultClient }

    /// Whether the script takes a click on a marked link, from its `href` as WebKit
    /// serializes it: a JavaScript function that is true only for an `href` that
    /// `WebSite.page` accepts as it is. It begins `https://` and one of a known site's
    /// `pageHosts` and a slash, is at most `WebSite.maximumPageLength` long, and holds only
    /// the characters RFC 3986 allows in a path, a query, and one fragment, so Foundation
    /// reads it without encoding any of it again, which would lengthen it. The script leaves
    /// a click on any other `href`, such as one over the length or to a site the app does
    /// not know, to the link, which opens it in the default browser
    /// (`NavigationPolicy.decideNewWindow`), rather than cancel it for a request the window
    /// would drop.
    static let opensHere = #"""
        (href) => href.length <= \#(WebSite.maximumPageLength)
            && /^https:\/\/(?:\#(hostPattern))\/(?:[\w\-.~!$&'()*+,;=:@\/?]|%[0-9A-Fa-f]{2})*(?:#(?:[\w\-.~!$&'()*+,;=:@\/?]|%[0-9A-Fa-f]{2})*)?$/.test(href)
        """#

    /// Every known site's `pageHosts`, as alternatives in a regular expression: a host is
    /// letters, digits, hyphens, and dots, and only the dots need escaping.
    static var hostPattern: String {
        WebSite.known.flatMap(\.pageHosts).map { $0.replacingOccurrences(of: ".", with: #"\."#) }
            .joined(separator: "|")
    }

    static let source = """
        window.addEventListener("click", (event) => {
            if (!event.isTrusted || event.button !== 0 || event.metaKey || event.ctrlKey
                || event.shiftKey || event.altKey) {
                return;
            }
            const link = event.target instanceof Element ? event.target.closest('\(marker)') : null;
            if (!(link instanceof HTMLAnchorElement) || !(\(opensHere))(link.href)) {
                return;
            }
            event.preventDefault();
            const box = link.getBoundingClientRect();
            window.webkit.messageHandlers.\(handlerName).postMessage({
                href: link.href,
                rect: [box.left, box.top, box.width, box.height],
                viewportWidth: window.innerWidth,
            });
        }, true);
        """

    /// One click on a marked link, as the script posts it.
    public struct Request: Equatable, Sendable {
        /// The page the link names, and its site (`WebSite.page`).
        public let page: WebSite.Page
        /// The link's client rectangle, in CSS pixels from the viewport's top left.
        public let link: CGRect
        /// The viewport's width in CSS pixels, `innerWidth`, which gives the page's scale.
        public let viewportWidth: CGFloat

        /// Nil for a message of any other shape, or for a page on no known site.
        public init?(_ body: Any) {
            guard let body = body as? [String: Any], let href = body["href"] as? String,
                  let page = WebSite.page(href),
                  let numbers = body["rect"] as? [Any], numbers.count == 4,
                  let width = (body["viewportWidth"] as? NSNumber)?.doubleValue, width.isFinite, width > 0
            else { return nil }
            let values = numbers.compactMap { ($0 as? NSNumber)?.doubleValue }.filter(\.isFinite)
            guard values.count == 4, values[2] >= 0, values[3] >= 0 else { return nil }
            self.page = page
            link = CGRect(x: values[0], y: values[1], width: values[2], height: values[3])
            viewportWidth = width
        }
    }

    private let onRequest: (WKWebView, WKFrameInfo, Request) -> Void

    /// `onRequest` gets the web view, the frame that asked, and what it asked for. A
    /// message of another shape, or for a page on no known site, is dropped.
    public init(onRequest: @escaping (WKWebView, WKFrameInfo, Request) -> Void) {
        self.onRequest = onRequest
    }

    func install(in configuration: WKWebViewConfiguration) {
        let controller = configuration.userContentController
        controller.addUserScript(WKUserScript(
            source: Self.source, injectionTime: .atDocumentStart, forMainFrameOnly: true, in: Self.world))
        controller.add(self, contentWorld: Self.world, name: Self.handlerName)
    }

    public func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let webView = message.webView, let request = Request(message.body) else { return }
        onRequest(webView, message.frameInfo, request)
    }
}

extension WebViewRequests {
    /// Whether a window opens its web pane for a click in `frame`: only the main frame
    /// of a document of the server's own origin, as for the page's Print button
    /// (`PagePrintRequests.allows`), so a `/raw` HTML file, whose CSP sandbox gives it an
    /// opaque origin, cannot use a marked link of its own.
    public static func allows(_ frame: WKFrameInfo, under policy: NavigationPolicy) -> Bool {
        let origin = frame.securityOrigin
        return policy.isAppDocument(
            scheme: origin.protocol, host: origin.host, port: origin.port, isMainFrame: frame.isMainFrame)
    }
}
