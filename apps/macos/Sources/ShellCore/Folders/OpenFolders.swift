/// The folders and repositories open in the app, by session key (`SessionRoot.key`: a
/// folder's canonical path, or a repository's URL): the order they opened in, and when
/// each was last shown.
///
/// A folder opens when its session is made, before it has a page, and closes when its
/// last page does. It is **shown** while a window shows one of its pages, and **in the
/// background** while its one page has no window, because a window switched away from
/// it. The app knows which windows show which pages; this model keeps the order and
/// recency that the chooser, the switcher, and File > Close Folder read, and decides what
/// a switch (`FolderSwitch`) and a close (`closing`) do.
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

    /// What File > Close Folder does with each window showing the folder `key`.
    ///
    /// A sheet open on any of them holds up the whole close (`FolderSwitch.refused`), so a
    /// folder never closes in some of its windows and stays open in others. Otherwise each
    /// window in turn shows the next folder in the background, the one shown most recently
    /// first, and closes once none is left: the windows on screen first, in the order
    /// given, then the minimized ones.
    ///
    /// - Parameters:
    ///   - windows: the windows showing `key`, front to back.
    ///   - background: the open folders in the background.
    public func closing<ID>(
        _ key: String, windows: [SwitchingWindow<ID>], background: Set<String>
    ) -> CloseFolderPlan<ID> {
        let blocked = windows.filter(\.hasSheet).map(\.id)
        guard blocked.isEmpty else { return .refused(blocked) }
        var replacements = byRecency.filter { $0 != key && background.contains($0) }[...]
        let ordered = windows.filter(\.isOnScreen) + windows.filter { !$0.isOnScreen }
        return .steps(ordered.map { CloseFolderStep(window: $0.id, showing: replacements.popFirst()) })
    }
}

/// A window as a switch or File > Close Folder sees it.
public nonisolated struct SwitchingWindow<ID: Hashable & Sendable>: Equatable, Sendable {
    public var id: ID
    /// On screen: not minimized. A minimized window counts its folder as shown only once it
    /// is brought back and becomes key (`windowDidBecomeKey`).
    public var isOnScreen: Bool
    /// A sheet is open on it: an `alert`, `confirm`, or `prompt`, a file input's open
    /// panel, or the print panel, which the page it shows opened, or one of the app's own,
    /// such as a download's save panel.
    public var hasSheet: Bool

    public init(id: ID, isOnScreen: Bool, hasSheet: Bool) {
        self.id = id
        self.isOnScreen = isOnScreen
        self.hasSheet = hasSheet
    }
}

/// What a window asked to show another folder does. Every switch, File > Close Folder's
/// included, goes through `FolderWindows.switchWindow`, which asks this.
public nonisolated enum FolderSwitch: Equatable, Sendable {
    /// The window shows that folder already, so nothing changes.
    case alreadyShown
    /// A sheet is open on the window. The sheet is modal to the window and answers for the
    /// page the window shows, so the window keeps that page until the sheet ends.
    case refused
    /// The window shows the folder's page in the background if it has one, else a new
    /// page of it, and the page it leaves becomes `left`. The folder counts as shown only
    /// if the window is on screen: a minimized window does not revive a discarded page,
    /// move its folder up in recency, or start a restored folder as the user's choice
    /// until it is brought back and becomes key.
    case show(left: SwitchedAwayPage, countsAsShown: Bool)

    /// - Parameters:
    ///   - showsFolder: whether the window shows that folder already.
    ///   - leftFolderPages: how many pages the folder the window shows now has, the one
    ///     the window shows included.
    public static func decide<ID>(_ window: SwitchingWindow<ID>, showsFolder: Bool, leftFolderPages: Int) -> FolderSwitch {
        if showsFolder { return .alreadyShown }
        if window.hasSheet { return .refused }
        return .show(left: .fate(otherPages: max(0, leftFolderPages - 1)), countsAsShown: window.isOnScreen)
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

/// What File > Close Folder does (`OpenFolders.closing`).
public nonisolated enum CloseFolderPlan<ID: Hashable & Sendable>: Equatable, Sendable {
    /// A sheet is open on these windows, so nothing switches or closes.
    case refused([ID])
    /// Each window in turn shows a folder in the background or closes; then the folder's
    /// pages close, which stops its server.
    case steps([CloseFolderStep<ID>])
}

public nonisolated struct CloseFolderStep<ID: Hashable & Sendable>: Equatable, Sendable {
    public var window: ID
    /// The folder in the background that the window shows instead, or nil: the window
    /// closes.
    public var showing: String?

    public init(window: ID, showing: String?) {
        self.window = window
        self.showing = showing
    }
}

/// What becomes of each page of a folder whose pages move to another folder's session,
/// because the folder's saved path now leads to that one (`RestoreRun`'s `movePages`).
///
/// Pages move, not windows: a page no window shows moves too, so the folder of the saved
/// path is left with no page and closes, and the target keeps at most one page in the
/// background, and only while no window shows it.
public nonisolated enum MovedPage: Equatable, Sendable {
    /// A window shows it: a page of the target, at the same address, takes its place in
    /// that window, and it closes.
    case replaceInWindow
    /// No window shows it, and the target will have no other page: a page of the target
    /// at the same address takes its place in the background, and it closes.
    case moveToBackground
    /// No window shows it, and the target has a page already or is shown: it closes.
    case close

    /// What moving a folder's pages to a target does.
    public struct Plan: Equatable, Sendable {
        /// Each moved page's fate, in the order given.
        public var pages: [MovedPage]
        /// Whether the target's pages that no window shows close, because a window shows
        /// the target once the pages have moved.
        public var closesTargetBackgroundPages: Bool
    }

    /// - Parameters:
    ///   - pages: whether a window shows each page that moves.
    ///   - target: whether a window shows each page the target has now.
    public static func plan(_ pages: [Bool], into target: [Bool]) -> Plan {
        let targetShown = target.contains(true) || pages.contains(true)
        var targetHasBackgroundPage = !targetShown && !target.isEmpty
        let fates = pages.map { inWindow -> MovedPage in
            if inWindow { return .replaceInWindow }
            if targetShown || targetHasBackgroundPage { return .close }
            targetHasBackgroundPage = true
            return .moveToBackground
        }
        return Plan(pages: fates, closesTargetBackgroundPages: targetShown && target.contains(false))
    }
}
