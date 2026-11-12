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
    /// A web view is one WebContent process of 155 to 210 MB with real pages (the
    /// server-topology brief), and of 111 to 143 MB on Metabrowser pages measured with
    /// `scripts/measure-web-views.swift` on macOS 26.5.2, which also found that the
    /// process ends within a second of its view's release and that a fresh view reloads
    /// the page from a warm server in a few hundred milliseconds (README, "Files, Tabs,
    /// Recents, and the Last Session"). Three background tabs then hold at most about
    /// 0.6 GB beyond the windows on screen. It is a conservative default, not a measured
    /// optimum.
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
