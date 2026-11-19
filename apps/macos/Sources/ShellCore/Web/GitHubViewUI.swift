import WebKit

/// The popover's GitHub view as a `WKUIDelegate`: the file panel and the JavaScript
/// dialogs github.com asks for, and the windows it asks to open.
///
/// Without a delegate for each dialog, WebKit answers `alert()` with OK and `confirm()` and
/// `prompt()` with Cancel, so an action GitHub guards with `confirm()` is cancelled
/// silently, and without `runOpenPanelWith` an `<input type=file>` opens nothing, so
/// "click to add files" on a comment box does nothing. `present` shows each as the app
/// chooses, keeping the popover open behind it, and answers it; the window asks the
/// popover's own policy (`GitHubViewPolicy.decideNewWindow`).
public final class GitHubViewUI: NSObject, WKUIDelegate {
    /// What the page asked for.
    public enum Request: Equatable, Sendable {
        case alert(String)
        case confirm(String)
        case prompt(String, defaultText: String?)
        case openFiles(multiple: Bool, directories: Bool)
    }

    /// The user's answer: `dismissed` for an alert, `confirmed` for a confirm, the text or
    /// `nil` (Cancel) for a prompt, and the files or `nil` (Cancel) for a file panel. An
    /// answer of another kind counts as Cancel.
    public enum Answer: Equatable, Sendable {
        case dismissed
        case confirmed(Bool)
        case text(String?)
        case files([URL]?)
    }

    private let present: (Request, @escaping @MainActor (Answer) -> Void) -> Void
    private let openExternally: (URL) -> Void

    /// `present` shows a request and calls its answer once; `openExternally` hands a URL to
    /// the default browser.
    public init(
        present: @escaping (Request, @escaping @MainActor (Answer) -> Void) -> Void,
        openExternally: @escaping (URL) -> Void
    ) {
        self.present = present
        self.openExternally = openExternally
    }

    /// `target=_blank` to a GitHub page loads here, in place; anything else on the web opens
    /// in the default browser.
    public func webView(
        _ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
        for action: WKNavigationAction, windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        switch GitHubViewPolicy.decideNewWindow(action.request.url) {
        case .allow: webView.load(action.request)
        case .openExternally(let url): openExternally(url)
        case .download, .openInNewWindow, .cancel: break
        }
        return nil
    }

    public func webView(
        _ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
        initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping @MainActor ([URL]?) -> Void
    ) {
        present(.openFiles(multiple: parameters.allowsMultipleSelection, directories: parameters.allowsDirectories)) {
            guard case .files(let urls) = $0 else { return completionHandler(nil) }
            completionHandler(urls)
        }
    }

    public func webView(
        _ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
        initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping @MainActor () -> Void
    ) {
        present(.alert(message)) { _ in completionHandler() }
    }

    // The explicit selector keeps this reachable on every SDK, as for the folder window's
    // page (`BrowserWindowController`): earlier Xcode 26 SDKs declare the completion handler
    // `@Sendable` rather than main-actor, so Swift does not take this method as the
    // protocol's witness there, and without `@objc` WebKit would find no `confirm()`
    // handler and answer Cancel.
    @objc(webView:runJavaScriptConfirmPanelWithMessage:initiatedByFrame:completionHandler:)
    public func webView(
        _ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
        initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping @MainActor (Bool) -> Void
    ) {
        present(.confirm(message)) { completionHandler($0 == .confirmed(true)) }
    }

    public func webView(
        _ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?,
        initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping @MainActor (String?) -> Void
    ) {
        present(.prompt(prompt, defaultText: defaultText)) {
            guard case .text(let text) = $0 else { return completionHandler(nil) }
            completionHandler(text)
        }
    }
}
