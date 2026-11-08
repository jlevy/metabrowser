import Foundation

public nonisolated enum NavigationDecision: Equatable, Sendable {
    case allow
    case download
    /// Hand the URL to the default browser (or mail client) and cancel here.
    case openExternally(URL)
    /// Open the URL in another window of the same folder and cancel here.
    case openInNewWindow(URL)
    case cancel
}

/// Which navigations stay in a folder's window.
///
/// The server's origin (scheme, host, and port) stays. A click on a link to any other
/// `http`, `https`, or `mailto` URL goes to the default browser; the same URL reached
/// any other way (script, redirect, form, Back or Forward) is cancelled, so a page
/// cannot open the browser by itself, and Back to a page of a server that has since
/// restarted on another port does nothing rather than leaving the app. Everything else,
/// including a `file://` navigation from a stray drop, is cancelled. Subframes are left
/// to the page's own policy. `127.0.0.1` and `localhost` are different origins, and
/// every URL the window loads comes from the server's announcement, so only the
/// announced one matches.
public nonisolated struct NavigationPolicy: Equatable, Sendable {
    public var origin: URL?

    public init(origin: URL? = nil) {
        self.origin = origin
    }

    static let inWindowSchemes: Set<String> = ["about", "blob", "data"]
    static let externalSchemes: Set<String> = ["http", "https", "mailto"]

    public func isAppOrigin(_ url: URL) -> Bool {
        guard let origin, let scheme = url.scheme?.lowercased(), scheme == origin.scheme?.lowercased()
        else { return false }
        return url.host(percentEncoded: false)?.lowercased() == origin.host(percentEncoded: false)?.lowercased()
            && Self.effectivePort(url) == Self.effectivePort(origin)
    }

    /// - Parameters:
    ///   - isMainFrame: false for a subframe; a new-window request (no target frame)
    ///     counts as main frame.
    ///   - isLinkClick: the user activated a link (`WKNavigationType.linkActivated`).
    ///   - shouldDownload: the link carried a `download` attribute.
    ///   - wantsNewWindow: a Command-click on a link.
    public func decide(
        _ url: URL?, isMainFrame: Bool, isLinkClick: Bool, shouldDownload: Bool = false,
        wantsNewWindow: Bool = false
    ) -> NavigationDecision {
        guard let url, let scheme = url.scheme?.lowercased() else { return .cancel }
        if shouldDownload { return .download }
        if !isMainFrame { return .allow }
        if isAppOrigin(url) { return wantsNewWindow && isLinkClick ? .openInNewWindow(url) : .allow }
        if Self.inWindowSchemes.contains(scheme) { return .allow }
        if Self.externalSchemes.contains(scheme), isLinkClick { return .openExternally(url) }
        return .cancel
    }

    /// For `target=_blank` and `window.open`: a window of this folder, or the default
    /// browser, or nothing. WebKit asks only on a user gesture, because it blocks
    /// `window.open` without one (`javaScriptCanOpenWindowsAutomatically` is off).
    public func decideNewWindow(_ url: URL?) -> NavigationDecision {
        guard let url, let scheme = url.scheme?.lowercased() else { return .cancel }
        if isAppOrigin(url) { return .openInNewWindow(url) }
        if Self.externalSchemes.contains(scheme) { return .openExternally(url) }
        return .cancel
    }

    /// `url` with its scheme, host, and port replaced by `origin`'s: where a window that
    /// was showing a page goes after its server restarts on another port.
    public static func rebase(_ url: URL, onto origin: URL) -> URL? {
        guard var parts = URLComponents(url: url, resolvingAgainstBaseURL: false),
              let target = URLComponents(url: origin, resolvingAgainstBaseURL: false)
        else { return nil }
        parts.scheme = target.scheme
        parts.percentEncodedHost = target.percentEncodedHost
        parts.port = target.port
        return parts.url
    }

    static func effectivePort(_ url: URL) -> Int? {
        if let port = url.port { return port }
        switch url.scheme?.lowercased() {
        case "http": return 80
        case "https": return 443
        default: return nil
        }
    }
}
