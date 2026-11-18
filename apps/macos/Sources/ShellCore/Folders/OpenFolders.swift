/// The folders and repositories open in the app, by session key (`SessionRoot.key`, a
/// folder's canonical path): the order they opened in, and when each was last shown.
///
/// A folder is open while its session has a page. It is **shown** while a window shows
/// one of its pages, and **in the background** while its one page has no window, because
/// a window switched away from it. The app knows which windows show which pages; this
/// model keeps the order and recency that the chooser, the switcher, and File > Close
/// Folder read, and decides what a switch does with the page left behind.
public nonisolated struct OpenFolders: Equatable, Sendable {
    /// Every open folder, in the order it opened, so the chooser's rows stay put.
    public private(set) var inOrderOpened: [String] = []
    /// When each folder was last shown, on `clock`.
    private var lastShown: [String: UInt64] = [:]
    private var clock: UInt64 = 0

    public init() {}

    public func contains(_ root: String) -> Bool { inOrderOpened.contains(root) }

    /// `root` opened. Opening an open folder changes nothing.
    public mutating func open(_ root: String) {
        if !contains(root) { inOrderOpened.append(root) }
    }

    /// A window showed `root`, or became key showing it. A folder not yet open opens.
    public mutating func show(_ root: String) {
        open(root)
        clock += 1
        lastShown[root] = clock
    }

    /// `root` closed: its last page did.
    public mutating func close(_ root: String) {
        inOrderOpened.removeAll { $0 == root }
        lastShown[root] = nil
    }

    /// Every open folder, the one shown most recently first; folders never shown follow,
    /// in the order they opened.
    public var byRecency: [String] {
        let shown = inOrderOpened.filter { lastShown[$0] != nil }.sorted { lastShown[$0]! > lastShown[$1]! }
        return shown + inOrderOpened.filter { lastShown[$0] == nil }
    }

    /// The folder a window shows in place of `closing` when File > Close Folder closes it:
    /// the background folder shown most recently, other than `closing`. Nil when there is
    /// none, and the window closes.
    public func replacement(closing: String, background: Set<String>) -> String? {
        byRecency.first { $0 != closing && background.contains($0) }
    }
}

/// What becomes of the page a window stops showing when it switches to another folder.
public nonisolated enum SwitchedAwayPage: Equatable, Sendable {
    /// The folder stays open in the background, its page kept for an instant switch back.
    case keepInBackground
    /// The page closes: its folder is shown in another window, or already has a page in
    /// the background, so keeping this one would only cost a web view. A folder thus has at
    /// most one background page, and only while no window shows it.
    case close

    /// - Parameter otherPages: how many other pages the folder has, shown or not.
    public static func fate(otherPages: Int) -> SwitchedAwayPage {
        otherPages == 0 ? .keepInBackground : .close
    }
}
