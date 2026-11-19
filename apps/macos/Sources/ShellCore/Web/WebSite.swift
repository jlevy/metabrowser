import CoreGraphics
import Foundation

/// A site the app shows in a web pane of its own (`WebPane`), apart from the folders'
/// pages: which of its pages a page's marked link may open there, and which navigations
/// stay in the pane once it shows one (`WebViewPolicy`) (mb-730z).
///
/// A page marks a link `data-web-view="open"` (`WebViewRequests`), and a plain click on it
/// opens the pane, anchored to the link, on the link's page, when the page is one of a
/// known site's (`page`); any other click, and any link to a site the app does not know,
/// opens in the default browser. The page names no site: the link's host chooses it. Every
/// site's pane keeps what it stores in the one store all panes share (`WebDataStore`), as
/// a browser profile does.
///
/// View on GitHub is the first use (mb-4wqh): every page with a counterpart on github.com
/// carries a View on GitHub button whose main link is marked. A github.com link handed to
/// the app (`open -b`, File > Open URL…, `metab --present`; `GitHubLink`) opens the
/// repository in a folder window instead, the inverse direction.
public nonisolated struct WebSite: Equatable, Sendable {
    /// What the app calls the site, as in a menu.
    public let name: String
    /// The registrable domains whose `https` pages stay in the pane, each with its
    /// subdomains (`WebViewPolicy`).
    public let domains: [String]
    /// The hosts a marked link may open the pane on, exactly: the site's own pages, not its
    /// raw files or assets.
    public let pageHosts: [String]

    public init(name: String, domains: [String], pageHosts: [String]) {
        self.name = name
        self.domains = domains
        self.pageHosts = pageHosts
    }

    /// github.com, where GitHub signs you in, githubusercontent.com, its raw files, images,
    /// and downloads, and githubassets.com, its scripts and styles. GitHub Pages
    /// (`github.io`) serves anyone's script and is not among them. A marked link opens only
    /// github.com itself.
    public static let gitHub = WebSite(
        name: "GitHub", domains: ["github.com", "githubusercontent.com", "githubassets.com"],
        pageHosts: ["github.com"])

    /// Every site a marked link may open in a pane.
    public static let known: [WebSite] = [.gitHub]

    /// The longest `href` a marked link may open, in UTF-8 bytes: `GitHubLink.maximumLength`,
    /// the bound on a link handed to the app, which already holds any page GitHub names.
    public static let maximumPageLength = GitHubLink.maximumLength

    /// A page a marked link opens, and the site it is on.
    public struct Page: Equatable, Sendable {
        public let site: WebSite
        public let url: URL
    }

    /// The page a marked link names, from its `href` as the page resolved it: an `https`
    /// page, with no user, password, or port but 443, at most `maximumPageLength` long, on
    /// one of a known site's `pageHosts`. Nil for anything else, which the window ignores.
    public static func page(_ href: String) -> Page? {
        guard href.utf8.count <= maximumPageLength, let url = URL(string: href),
              url.scheme?.lowercased() == "https", url.user == nil, url.password == nil,
              url.port == nil || url.port == 443,
              let host = url.host(percentEncoded: true)?.lowercased(),
              let site = known.first(where: { $0.pageHosts.contains(host) })
        else { return nil }
        return Page(site: site, url: url)
    }

    /// Whether a page at `url` shows in this site's pane: `https`, no port but 443, and a
    /// host that is one of `domains` or below one.
    public func staysInView(_ url: URL) -> Bool {
        guard url.scheme?.lowercased() == "https", url.user == nil, url.password == nil,
              url.port == nil || url.port == 443,
              let host = url.host(percentEncoded: false)?.lowercased()
        else { return false }
        return domains.contains { host == $0 || host.hasSuffix("." + $0) }
    }
}

/// What a web pane's header says it shows.
public nonisolated enum WebLocation {
    /// The page's host and path, without the scheme, query, or fragment, as
    /// `github.com/owner/repo/blob/main/README.md`. The path is decoded for reading unless
    /// decoding gives a control or bidirectional formatting character, which could break or
    /// reorder the line, and then it stays encoded. Empty before the pane has a page.
    public static func text(_ url: URL?) -> String {
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

/// Which navigations stay in a web pane, for the site it shows.
///
/// A main-frame `https` page on one of the site's domains stays (`WebSite.staysInView`).
/// A link clicked or a form
/// sent to anything else opens in the default browser, and the same URL reached any other
/// way, by script or by a redirect the page started itself, is cancelled, as in a folder's
/// window (`NavigationPolicy`). Command-click opens a link to the site in the default browser
/// too, as a new tab would. Subframes are left to the page's own policy.
///
/// A download goes to the default browser too, which keeps the user's downloads where
/// their browser keeps them, rather than as a save panel over a pane.
public nonisolated struct WebViewPolicy: Equatable, Sendable {
    public let site: WebSite

    public init(site: WebSite) { self.site = site }

    /// Whether a page at `url` shows in the pane (`WebSite.staysInView`).
    public func staysInView(_ url: URL) -> Bool { site.staysInView(url) }

    /// - Parameters:
    ///   - isMainFrame: false for a subframe; a new-window request counts as main frame.
    ///   - byUser: the user clicked a link or sent a form (`WKNavigationType`
    ///     `linkActivated`, `formSubmitted`, or `formResubmitted`).
    ///   - shouldDownload: the link carried a `download` attribute.
    ///   - wantsNewWindow: a Command-click on a link.
    public func decide(
        _ url: URL?, isMainFrame: Bool, byUser: Bool, shouldDownload: Bool = false, wantsNewWindow: Bool = false
    ) -> NavigationDecision {
        guard let url, let scheme = url.scheme?.lowercased() else { return .cancel }
        if shouldDownload { return byUser && Self.isWeb(scheme) ? .openExternally(url) : .cancel }
        if !isMainFrame { return .allow }
        if staysInView(url) { return wantsNewWindow && byUser ? .openExternally(url) : .allow }
        if NavigationPolicy.inWindowSchemes.contains(scheme) { return .allow }
        if NavigationPolicy.externalSchemes.contains(scheme), byUser { return .openExternally(url) }
        return .cancel
    }

    /// For `target=_blank` and `window.open`, which WebKit asks about only on a user gesture
    /// (`WebConfiguration.restrict`): `.allow` loads a page of the site in this pane, in place,
    /// rather than in a window of its own, and anything else on the web opens in the default
    /// browser.
    public func decideNewWindow(_ url: URL?) -> NavigationDecision {
        guard let url, let scheme = url.scheme?.lowercased() else { return .cancel }
        if staysInView(url) { return .allow }
        if NavigationPolicy.externalSchemes.contains(scheme) { return .openExternally(url) }
        return .cancel
    }

    /// For a main-frame response, as `ResponsePolicy` sorts it: one the view can show
    /// shows, and a download from the site's own domains, such as GitHub's Download ZIP,
    /// opens in the default browser. Only the site's own pages load here (`decide`), so only
    /// their scripts can start one.
    public func decideResponse(_ url: URL?, _ response: ResponsePolicy) -> NavigationDecision {
        guard response == .download else { return .allow }
        guard let url, staysInView(url) else { return .cancel }
        return .openExternally(url)
    }

    private static func isWeb(_ scheme: String) -> Bool { scheme == "https" || scheme == "http" }
}

/// What a web pane was opened for, which decides whether opening it again loads a page.
///
/// Each folder page has a pane of its own, in a popover (`FolderPage`, `WebPopover`), which
/// keeps its web view for `keptAfterClosing` after the popover closes, so opening the same
/// link again within that time shows the pane at once, as it was left, wherever the user
/// went on the site since, with its Back and Forward history; opening it for another page
/// loads that page in it, and so does opening it for a page that never loaded. While the
/// page holds text the user has not sent (`unsentTextProbe`), the web view stays.
public nonisolated struct WebPaneState: Equatable, Sendable {
    /// How long a closed popover's pane keeps its web view, and with it a WebContent process of its
    /// own, which `TabDiscardPolicy` does not count. A web view holding text the user has not
    /// sent (`unsentTextProbe`) stays for another `keptAfterClosing`, as often as it still
    /// does, so time alone does not bound these processes: there is at most one per live
    /// folder page, since a page the policy discards, or that closes, lets its pane's web view
    /// go at once.
    ///
    /// Long enough to look from the page to the site and back a few times without a reload,
    /// short enough that a page's pane does not stay in memory while the user
    /// works on in Metabrowser. Measured on macOS 26.5.2 with
    /// `scripts/measure-web-views.swift` on a github.com file page (a README), signed out,
    /// 3 views:
    ///
    /// - Each view is one WebContent process of 189 to 193 MB, 8 s after loading: more than
    ///   a folder's page (`TabDiscardPolicy.defaultLiveBackgroundTabs`).
    /// - A fresh view loading the page again, to `didFinish`: 376 to 896 ms in 5 loads; the
    ///   first load of the run took 2.7 s. That is the cost of reopening after this time.
    /// - A released view's process was still there, at the same size, 10 s after release,
    ///   where a folder page's ends within 1 s: WebKit, not the app, decides when it ends.
    ///   Letting the view go bounds what the app holds, not when the memory returns.
    public static let keptAfterClosing = Duration.seconds(60)

    /// The page the pane last loaded for a marked link: nil before its first use, and after
    /// its web view is let go.
    public private(set) var openedFor: URL?

    public init() {}

    /// A marked link to `page` was clicked; `hasPage` says whether the
    /// web view has a committed page. Returns the page to load, or nil to show the pane as
    /// it was left. A page that never loaded, such as one asked for offline, loads again.
    public mutating func open(_ page: URL, hasPage: Bool) -> URL? {
        guard page != openedFor || !hasPage else { return nil }
        openedFor = page
        return page
    }

    /// For Reload Page, and after Clear Website Data…: the page to load in place of a reload,
    /// which does nothing in a web view without a committed page (`PageReload`), or nil to
    /// reload the page shown.
    public func pageToLoad(hasPage: Bool) -> URL? { hasPage ? nil : openedFor }

    /// The pane's web view was let go: `keptAfterClosing` passed after its popover closed,
    /// its folder page gave up its web view to save memory, or the page closes.
    public mutating func discard() { openedFor = nil }

    /// Evaluated in the app's content world before a closed pane's web view is let go:
    /// whether a text area, or a text, URL, or email field, holds text other than what the
    /// page put there, such as a comment the user has not sent. While one does, the web
    /// view stays for another `keptAfterClosing`, so closing the popover to look at the page
    /// behind it does not lose the comment. A password field never counts.
    public static let unsentTextProbe = """
        (() => {
            const typed = (field) => field.value !== field.defaultValue;
            if (Array.from(document.querySelectorAll("textarea")).some(typed)) return true;
            return Array.from(document.querySelectorAll("input")).some((field) =>
                ["text", "url", "email"].includes(field.type) && typed(field));
        })()
        """
}

/// Where a web pane's popover opens and how large it is.
public nonisolated enum WebPopoverLayout {
    /// The smallest the popover's content gets, screen permitting. Set for GitHub, the first
    /// site, and wide enough for most: GitHub lays a page out
    /// in one narrow column below 768 CSS pixels, its `md` breakpoint, so the width keeps
    /// the repository layout with room to spare, and the height shows a file's first
    /// screen below GitHub's own header.
    public static let minimumSize = CGSize(width: 800, height: 520)
    /// "Most of the window": the share of the window's content area the popover takes when
    /// that is larger than `minimumSize`.
    public static let windowShare = CGSize(width: 0.9, height: 0.85)
    /// Kept clear at the screen's edges for the popover's border and arrow.
    public static let screenMargin: CGFloat = 48

    /// The popover's content size for a window whose content area is `window`, on a screen
    /// whose visible area is `screen`. NSPopover has no resize handle, so this is the size
    /// every time it opens, following the window's.
    public static func contentSize(window: CGSize, screen: CGSize?) -> CGSize {
        var width = max(minimumSize.width, (window.width * windowShare.width).rounded())
        var height = max(minimumSize.height, (window.height * windowShare.height).rounded())
        if let screen {
            width = min(width, max(0, screen.width - screenMargin))
            height = min(height, max(0, screen.height - screenMargin))
        }
        return CGSize(width: width, height: height)
    }

    /// The marked link's rectangle in the web view, from its client rectangle in CSS pixels. The
    /// page's viewport spans the web view's width, so the web view's width over the
    /// viewport's (`innerWidth`) is the scale, page zoom included; `flipped` is the web
    /// view's `isFlipped`. The result is clipped to the web view, as a popover must point
    /// into its view; if none of the link is inside, the popover points at the web view's
    /// top right corner, where the pages put their View on GitHub button.
    public static func anchor(_ link: CGRect, viewportWidth: CGFloat, in bounds: CGRect, flipped: Bool) -> CGRect {
        let scale = viewportWidth > 0 ? bounds.width / viewportWidth : 1
        let top = link.minY * scale
        let height = link.height * scale
        let rect = CGRect(
            x: bounds.minX + link.minX * scale, y: flipped ? bounds.minY + top : bounds.maxY - top - height,
            width: link.width * scale, height: height)
        let clipped = rect.intersection(bounds)
        if !clipped.isNull, clipped.width > 0, clipped.height > 0 { return clipped }
        return CGRect(x: bounds.maxX - 1, y: flipped ? bounds.minY : bounds.maxY - 1, width: 1, height: 1)
    }
}
