/// One folder tab, as the discard policy sees it.
public nonisolated struct TabActivity<ID: Hashable & Sendable>: Equatable, Sendable {
    public var id: ID
    /// A tab its window is not showing. A window's shown tab, or a window without other
    /// tabs, is on screen, and is never discarded.
    public var isBackground: Bool
    /// Whether it still has its web view's page.
    public var isLive: Bool
    /// When the tab was last shown, on any increasing counter.
    public var lastShown: UInt64

    public init(id: ID, isBackground: Bool, isLive: Bool, lastShown: UInt64) {
        self.id = id
        self.isBackground = isBackground
        self.isLive = isLive
        self.lastShown = lastShown
    }
}

/// Which background tabs give up their web views.
///
/// A folder tab's web view is its own WebContent process, and that process is most of
/// what a tab costs (see `defaultLiveBackgroundTabs`). A discarded tab keeps its window
/// and its server, and reloads its page from that running server when it is shown
/// again. The windows on screen keep their pages, and so do the background tabs shown
/// most recently, up to the limit.
public nonisolated struct TabDiscardPolicy: Equatable, Sendable {
    /// Background tabs that keep their pages.
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
    /// Three background tabs then hold at most about 0.6 GB beyond the windows on screen,
    /// at the brief's upper figure. It is a conservative default, not a measured optimum:
    /// showing a discarded tab costs a reload of a few hundred milliseconds, and how often
    /// people return to a tab past the third is unmeasured.
    public static let defaultLiveBackgroundTabs = 3

    public var liveBackgroundTabs: Int

    public init(liveBackgroundTabs: Int = TabDiscardPolicy.defaultLiveBackgroundTabs) {
        self.liveBackgroundTabs = max(0, liveBackgroundTabs)
    }

    /// The tabs to discard now, least recently shown first.
    public func discards<ID>(_ tabs: [TabActivity<ID>]) -> [ID] {
        let live = tabs.filter { $0.isBackground && $0.isLive }.sorted { $0.lastShown > $1.lastShown }
        return live.dropFirst(liveBackgroundTabs).reversed().map(\.id)
    }
}
