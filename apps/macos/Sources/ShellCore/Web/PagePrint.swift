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

extension NavigationPolicy {
    /// Whether a window prints when its page asks: only the main frame of the server's own
    /// page, and not while a sheet, such as an earlier print panel, is open, so a page
    /// cannot stack print panels.
    public func allowsPagePrint(from url: URL?, isMainFrame: Bool, sheetOpen: Bool) -> Bool {
        guard isMainFrame, !sheetOpen, let url else { return false }
        return isAppOrigin(url)
    }
}
