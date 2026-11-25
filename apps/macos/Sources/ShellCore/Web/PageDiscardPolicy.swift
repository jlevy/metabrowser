/// One folder page, as the discard policy sees it: a page a window shows, or a folder's
/// page in the background, which no window shows (`OpenFolders`).
public nonisolated struct PageActivity<ID: Hashable & Sendable>: Equatable, Sendable {
    public var id: ID
    /// A page no window is showing: a folder's page in the background. A page a window
    /// shows, minimized or not, is never discarded.
    public var isBackground: Bool
    /// Whether it still has its web view's page.
    public var isLive: Bool
    /// When the page was last shown, on any increasing counter.
    public var lastShown: UInt64

    public init(id: ID, isBackground: Bool, isLive: Bool, lastShown: UInt64) {
        self.id = id
        self.isBackground = isBackground
        self.isLive = isLive
        self.lastShown = lastShown
    }
}

/// Which background pages give up their web views: the pages of folders in the
/// background, which a window switched away from (`SwitchedAwayPage.keepInBackground`).
///
/// A folder page's web view is its own WebContent process, and that process is most of
/// what a background folder costs (see `defaultLiveBackgroundPages`). A page's web pane, as
/// View on GitHub opens, adds a process of its own while it is open, for
/// `WebPaneState.keptAfterClosing` after it closes, and for as long as it holds text the
/// user has not sent. The policy does not count it; there is at most one per live page,
/// since a page the policy discards lets its pane's go with its own. A discarded page
/// keeps its folder's server, and reloads its page from that running server when a window
/// shows it again. The windows keep their pages, and so do the background pages shown
/// most recently, up to the limit.
public nonisolated struct PageDiscardPolicy: Equatable, Sendable {
    /// Background pages that keep their web views.
    ///
    /// Measured on macOS 26.5.2 with `scripts/measure-web-views.swift` against this
    /// repository's own server:
    ///
    /// - Each web view that loaded a page is one WebContent process; a view that never
    ///   loaded has none, and a released view's process is gone within 1 s.
    /// - One view's footprint, 8 s after loading: 120 to 143 MB on the folder page (4
    ///   views), 111 to 112 MB on a Markdown page (3 views). The server-topology brief
    ///   measured 155 to 210 MB with real pages.
    /// - A fresh view loading the page from the warm server, to `didFinish`: 155 to 489 ms
    ///   in 9 of 10 loads, and one of 3.7 s. In a run started 5 s after the server, while
    ///   it was likely still walking the tree, two of five took 3.6 and 17.9 s.
    ///
    /// Three background pages then hold at most about 0.6 GB beyond the windows, at the
    /// brief's upper figure, and as much again while each keeps a web pane's web view
    /// (`WebPaneState.keptAfterClosing` has that measurement). It is a conservative default,
    /// not a measured optimum: showing a discarded page costs a reload of a few hundred
    /// milliseconds, and how often people return to a folder past the third is unmeasured.
    public static let defaultLiveBackgroundPages = 3

    public var liveBackgroundPages: Int

    public init(liveBackgroundPages: Int = PageDiscardPolicy.defaultLiveBackgroundPages) {
        self.liveBackgroundPages = max(0, liveBackgroundPages)
    }

    /// The pages to discard now, least recently shown first.
    public func discards<ID>(_ pages: [PageActivity<ID>]) -> [ID] {
        let live = pages.filter { $0.isBackground && $0.isLive }.sorted { $0.lastShown > $1.lastShown }
        return live.dropFirst(liveBackgroundPages).reversed().map(\.id)
    }
}
