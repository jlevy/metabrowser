import WebKit

/// The page's own Print button, which calls `window.print()`.
///
/// WebKit on macOS hands a page's `window.print()` only to private `WKUIDelegate`
/// methods, and there is no public one, so in the app the button did nothing (mb-j3eu)
/// while File > Print worked. A user script, installed by `WebConfiguration.make`,
/// replaces `window.print` in each page's main frame with a message to this handler, and
/// the window then prints exactly as File > Print does. The page still calls only the
/// web's own `window.print()`; nothing in it knows about the app. Frames inside the page
/// keep WebKit's own `print()`, which reaches nothing.
public final class PagePrintRequests: NSObject, WKScriptMessageHandler {
    public static let handlerName = "metabrowserPrint"
    static let source = """
        window.print = function print() {
            window.webkit.messageHandlers.\(handlerName).postMessage(null);
        };
        """

    private let onRequest: (WKWebView, WKFrameInfo) -> Void

    /// `onRequest` gets the web view and the frame that asked.
    public init(onRequest: @escaping (WKWebView, WKFrameInfo) -> Void) {
        self.onRequest = onRequest
    }

    func install(in configuration: WKWebViewConfiguration) {
        let controller = configuration.userContentController
        controller.addUserScript(WKUserScript(source: Self.source, injectionTime: .atDocumentStart, forMainFrameOnly: true))
        controller.add(self, name: Self.handlerName)
    }

    public func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let webView = message.webView else { return }
        onRequest(webView, message.frameInfo)
    }
}

extension PagePrintRequests {
    /// Whether a window prints when `frame` asks, the check every window applies. It goes
    /// by the document's security origin, not its URL: a `/raw` response has the server's
    /// URL, but its CSP sandbox gives it an opaque origin and no `allow-modals`, and a
    /// frame can call the handler directly, without the `window.print` replacement.
    public static func allows(_ frame: WKFrameInfo, under policy: NavigationPolicy, sheetOpen: Bool) -> Bool {
        let origin = frame.securityOrigin
        return policy.allowsPagePrint(
            scheme: origin.protocol, host: origin.host, port: origin.port, isMainFrame: frame.isMainFrame,
            sheetOpen: sheetOpen)
    }
}

extension NavigationPolicy {
    /// Whether a document whose security origin is `scheme`, `host`, and `port` (0 for the
    /// scheme's default, as WebKit reports it) may print: only the main frame of the
    /// server's own origin, never an opaque one, which has no scheme or host, and not
    /// while a sheet, such as an earlier print panel, is open.
    public func allowsPagePrint(scheme: String, host: String, port: Int, isMainFrame: Bool, sheetOpen: Bool) -> Bool {
        guard isMainFrame, !sheetOpen, !scheme.isEmpty, !host.isEmpty, origin != nil else { return false }
        var parts = URLComponents()
        parts.scheme = scheme
        parts.host = host
        if port != 0 { parts.port = port }
        guard let document = parts.url else { return false }
        return isAppOrigin(document)
    }
}
