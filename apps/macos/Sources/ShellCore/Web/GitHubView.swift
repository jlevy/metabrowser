import CoreGraphics
import Foundation

/// View on GitHub, in a folder window: github.com's own page for the item the window shows,
/// in a native popover over the page (mb-4wqh).
///
/// Every page with a counterpart on github.com carries a View on GitHub button in its upper
/// right. Its main link, marked `data-view-on-github="open"`, names the item's page on
/// github.com, and a plain click on it opens the popover, anchored to the button, with a web
/// view of that page (`GitHubViewRequests`). The button's menu has Copy Link, which the page
/// does by itself, and Open in Browser, a link marked `data-view-on-github="external"` that
/// opens a new window, which the app hands to the default browser as it does any link to
/// another site (`NavigationPolicy.decideNewWindow`).
///
/// Only the marked link opens the popover. A github.com link handed to the app (`open -b`,
/// File > Open URL…, `metab --present`; `GitHubLink`) opens the repository in a folder
/// window instead, the inverse direction, and any other github.com link in a page opens in
/// the default browser (`NavigationPolicy`).
public nonisolated enum GitHubView {
    /// The page the button names, from its link's `href` as the page resolved it: an `https`
    /// page on github.com itself that `GitHubLink` accepts. Nil for anything else, which the
    /// window ignores.
    public static func page(_ href: String) -> URL? {
        guard let url = URL(string: href), GitHubLink.accepts(url),
              url.host(percentEncoded: true)?.lowercased() == "github.com"
        else { return nil }
        return url
    }

    /// What the popover's header says it shows: the page's host and path, without the
    /// scheme, query, or fragment, as `github.com/owner/repo/blob/main/README.md`. The path
    /// is decoded for reading unless decoding gives a control or bidirectional formatting
    /// character, which could break or reorder the line, and then it stays encoded. Empty
    /// before the popover has a page.
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

/// Which navigations stay in the popover's GitHub view.
///
/// A main-frame `https` page on GitHub's own domains stays: github.com, where GitHub signs
/// you in, githubusercontent.com, its raw files, images, and downloads, and
/// githubassets.com, its scripts and styles, each with its subdomains. GitHub Pages
/// (`github.io`) serves anyone's script and is not among them. A link clicked or a form
/// sent to anything else opens in the default browser, and the same URL reached any other
/// way, by script or by a redirect the page started itself, is cancelled, as in a folder's
/// window (`NavigationPolicy`). Command-click opens a GitHub link in the default browser
/// too, as a new tab would. Subframes are left to the page's own policy.
///
/// A download goes to the default browser too, which keeps the user's downloads where
/// their browser keeps them, rather than as a save panel over a popover.
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
        if shouldDownload { return byUser && isWeb(scheme) ? .openExternally(url) : .cancel }
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

    /// For a main-frame response, as `ResponsePolicy` sorts it: one the view can show
    /// shows, and a download from GitHub's own domains, such as Download ZIP, opens in the
    /// default browser. Only GitHub's own pages load here (`decide`), so only their scripts
    /// can start one.
    public static func decideResponse(_ url: URL?, _ response: ResponsePolicy) -> NavigationDecision {
        guard response == .download else { return .allow }
        guard let url, staysInView(url) else { return .cancel }
        return .openExternally(url)
    }

    private static func isWeb(_ scheme: String) -> Bool { scheme == "https" || scheme == "http" }
}

/// What the popover's GitHub view was opened for, which decides whether opening it again
/// loads a page.
///
/// A window keeps its popover's web view for `keptAfterClosing` after the popover closes,
/// so opening View on GitHub again for the same item within that time shows the popover at
/// once, as it was left, wherever the user went on github.com since, with its Back and
/// Forward history; opening it for another item loads that item's page in it.
public nonisolated struct GitHubPopoverState: Equatable, Sendable {
    /// How long a closed popover keeps its web view, and with it a WebContent process of its
    /// own, which `TabDiscardPolicy` does not count.
    ///
    /// Long enough to look from the page to github.com and back a few times without a
    /// reload, short enough that a window's GitHub page does not stay in memory while the
    /// user works on in Metabrowser. Measured on macOS 26.5.2 with
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

    /// The page the popover last loaded for the button: nil before its first use, and after
    /// its web view is let go.
    public private(set) var openedFor: URL?

    public init() {}

    /// The button was clicked for the item whose page is `page`. Returns the page to load,
    /// or nil to show the popover as it was left.
    public mutating func open(_ page: URL) -> URL? {
        guard page != openedFor else { return nil }
        openedFor = page
        return page
    }

    /// The popover's web view was let go: `keptAfterClosing` passed after it closed, the
    /// tab gave up its pages to save memory, or the window closes.
    public mutating func discard() { openedFor = nil }
}

/// Where the popover opens and how large it is.
public nonisolated enum GitHubPopoverLayout {
    /// The smallest the popover's content gets, screen permitting: GitHub lays a page out
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

    /// The button's rectangle in the web view, from its client rectangle in CSS pixels. The
    /// page's viewport spans the web view's width, so the web view's width over the
    /// viewport's (`innerWidth`) is the scale, page zoom included; `flipped` is the web
    /// view's `isFlipped`. The result is clipped to the web view, as a popover must point
    /// into its view; if none of the button is inside, the popover points at the web view's
    /// top right corner, where the button sits.
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
