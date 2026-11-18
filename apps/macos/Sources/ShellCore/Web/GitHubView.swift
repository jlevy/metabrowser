import Foundation

/// The GitHub view: github.com's own page for the item a folder window shows, in a second
/// web view that the window keeps beside its page (mb-lxgw).
///
/// Every page opens in the Metabrowser view. The view header's toggle
/// (`static/github-page.js`) ends in a link to the item's page on github.com, marked
/// `data-view-toggle="github"`. A plain click on that link shows the page in the window
/// (`GitHubViewRequests`), and choosing Metabrowser shows the window's own page again, as
/// it was left.
///
/// Only the marked link does this. A github.com link handed to the app (`open -b`, File >
/// Open URL…, `metab --present`; `GitHubLink`) opens the repository in the Metabrowser
/// view, the inverse direction, and any other github.com link in a page still opens in the
/// default browser (`NavigationPolicy`).
public nonisolated enum GitHubView {
    /// The page the toggle names, from its link's `href` as the page resolved it: an
    /// `https` page on github.com itself, as `pageUrl` in `github-page.js` writes every
    /// one, that `GitHubLink` accepts. Nil for anything else, which the window ignores.
    public static func togglePage(_ href: String) -> URL? {
        guard let url = URL(string: href), GitHubLink.accepts(url),
              url.host(percentEncoded: true)?.lowercased() == "github.com"
        else { return nil }
        return url
    }

    /// What the bar above the GitHub view says it shows: the page's host and path, without
    /// the scheme, query, or fragment, as `github.com/owner/repo/blob/main/README.md`. The
    /// path is decoded for reading unless decoding gives a control or bidirectional
    /// formatting character, which could break or reorder the line, and then it stays
    /// encoded. Empty before the view has a page.
    public static func location(_ url: URL?) -> String {
        guard let url, let host = url.host(percentEncoded: false), !host.isEmpty else { return "" }
        let encoded = url.path(percentEncoded: true)
        let decoded = url.path(percentEncoded: false)
        let path = decoded.unicodeScalars.contains(where: isUnsafeInLabel) ? encoded : decoded
        let trimmed = path.hasSuffix("/") ? String(path.dropLast()) : path
        return host.lowercased() + trimmed
    }

    private static let bidirectionalControls: Set<UInt32> = [
        0x061C, 0x200E, 0x200F, 0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069,
    ]

    private static func isUnsafeInLabel(_ scalar: Unicode.Scalar) -> Bool {
        CharacterSet.controlCharacters.contains(scalar) || bidirectionalControls.contains(scalar.value)
    }
}

/// Which navigations stay in a GitHub view.
///
/// A main-frame `https` page on GitHub's own domains stays: github.com, where GitHub signs
/// you in, githubusercontent.com, its raw files, images, and downloads, and
/// githubassets.com, its scripts and styles, each with its subdomains. GitHub Pages
/// (`github.io`) serves anyone's script and is not among them. A link clicked or a form
/// sent to anything else opens in the default browser, and the same URL reached any other
/// way, by script or by a redirect the page started itself, is cancelled, as in a folder's
/// window (`NavigationPolicy`). Command-click opens a GitHub link in the default browser
/// too, as a new tab would. Subframes are left to the page's own policy.
public nonisolated enum GitHubViewPolicy {
    public static let domains = ["github.com", "githubusercontent.com", "githubassets.com"]

    /// Whether a page at `url` shows in the GitHub view: `https`, no port but 443, and a
    /// host that is one of `domains` or below one.
    public static func staysInView(_ url: URL) -> Bool {
        guard url.scheme?.lowercased() == "https", url.user == nil, url.password == nil,
              url.port == nil || url.port == 443,
              let host = url.host(percentEncoded: false)?.lowercased()
        else { return false }
        return domains.contains { host == $0 || host.hasSuffix("." + $0) }
    }

    /// - Parameters:
    ///   - isMainFrame: false for a subframe; a new-window request counts as main frame.
    ///   - byUser: the user clicked a link or sent a form (`WKNavigationType`
    ///     `linkActivated`, `formSubmitted`, or `formResubmitted`).
    ///   - shouldDownload: the link carried a `download` attribute.
    ///   - wantsNewWindow: a Command-click on a link.
    public static func decide(
        _ url: URL?, isMainFrame: Bool, byUser: Bool, shouldDownload: Bool = false, wantsNewWindow: Bool = false
    ) -> NavigationDecision {
        guard let url, let scheme = url.scheme?.lowercased() else { return .cancel }
        if shouldDownload { return .download }
        if !isMainFrame { return .allow }
        if staysInView(url) { return wantsNewWindow && byUser ? .openExternally(url) : .allow }
        if NavigationPolicy.inWindowSchemes.contains(scheme) { return .allow }
        if NavigationPolicy.externalSchemes.contains(scheme), byUser { return .openExternally(url) }
        return .cancel
    }

    /// For `target=_blank` and `window.open`, which WebKit asks about only on a user gesture
    /// (`WebConfiguration.restrict`): `.allow` loads a GitHub page in this view, in place,
    /// rather than in a window of its own, and anything else on the web opens in the default
    /// browser.
    public static func decideNewWindow(_ url: URL?) -> NavigationDecision {
        guard let url, let scheme = url.scheme?.lowercased() else { return .cancel }
        if staysInView(url) { return .allow }
        if NavigationPolicy.externalSchemes.contains(scheme) { return .openExternally(url) }
        return .cancel
    }
}

/// Which of a folder window's two views it shows, and what its GitHub view was opened for.
///
/// The window keeps both web views while it has a GitHub view, so a switch either way is
/// instant: the Metabrowser view keeps its page, scroll, and state, and the GitHub view
/// keeps the page it is on and its Back and Forward history. Choosing GitHub for the item
/// the GitHub view was opened for shows it as it was left, wherever the user went on
/// github.com since; choosing it for another item loads that item's page in it.
public nonisolated struct GitHubViewState: Equatable, Sendable {
    /// The GitHub view is on screen in place of the window's page.
    public private(set) var showsGitHub = false
    /// The toggle's page the GitHub view last loaded: nil before the toggle is first
    /// chosen, and after the tab gives up its pages.
    public private(set) var openedFor: URL?

    public init() {}

    /// The window has a GitHub view, shown or kept beside its page.
    public var hasGitHubView: Bool { openedFor != nil }

    /// The toggle's GitHub side was chosen, for the item whose page is `page`. Returns the
    /// page to load in the GitHub view, or nil to show it as it was left.
    public mutating func showGitHub(for page: URL) -> URL? {
        showsGitHub = true
        guard page != openedFor else { return nil }
        openedFor = page
        return page
    }

    /// The toggle's Metabrowser side was chosen: the window's own page shows again.
    public mutating func showMetabrowser() { showsGitHub = false }

    /// The tab gave up its pages to save memory, or the window closes: the GitHub view goes
    /// with them, and the window shows its own page when it is shown again.
    public mutating func discard() {
        showsGitHub = false
        openedFor = nil
    }

    /// View > Show GitHub View, or Show Metabrowser View while the GitHub view shows: the
    /// item's title says which view it switches to.
    public var toggleTitle: String { showsGitHub ? "Show Metabrowser View" : "Show GitHub View" }
}
