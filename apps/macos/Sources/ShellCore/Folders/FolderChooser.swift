import Foundation

/// The rows of the title's folder chooser and of the Switch Folder panel, and what
/// choosing each does. Both read this one model, so they never disagree.
///
/// The chooser lists the open folders in the order they opened (`OpenFolders`), so a row
/// stays where the hand expects it, then `metab`'s recent targets that are not open, in
/// `metab`'s order (`RecentTargets.items`). The panel lists the same rows, the open
/// folders most recently shown first, with the window's own folder last, so its first
/// row goes back to the folder shown before this one.
public nonisolated enum FolderChooser {
    /// Where an open folder is shown, as the window asking sees it.
    public enum Shown: Equatable, Sendable {
        /// This window shows it.
        case here
        /// Another window shows it, and this one does not.
        case inAnotherWindow
        /// No window shows it: it is open in the background.
        case background
    }

    /// One open folder, as the app reads it from its sessions and windows.
    public struct OpenFolder: Equatable, Sendable {
        /// Its key among the open folders (`OpenFolders`).
        public var key: String
        /// Its `window.title`: the short name, or the full name where another open
        /// folder shares the short name (`WindowTitle.windowTitles`).
        public var title: String
        /// Where it is, as the status view says: `~/wrk/fdu` or `github.com/owner/repo`.
        public var location: String
        public var mark: RootMark
        public var shown: Shown

        public init(key: String, title: String, location: String, mark: RootMark, shown: Shown) {
            self.key = key
            self.title = title
            self.location = location
            self.mark = mark
            self.shown = shown
        }
    }

    public enum Section: Equatable, Sendable {
        case open
        case recent
    }

    /// What a row stands for.
    public enum Target: Equatable, Sendable {
        /// An open folder, by its key.
        case open(String, Shown)
        /// A recent target that is not open, by what opening it asks the app for.
        case recent(URL)
    }

    public struct Row: Equatable, Sendable {
        public var section: Section
        public var title: String
        /// The row's second line: its location, or "In another window".
        public var subtitle: String
        /// Where it is, which the panel's search matches as well as the title.
        public var location: String
        public var mark: RootMark
        /// The window's own folder.
        public var isChecked: Bool
        public var target: Target
    }

    /// What choosing a row does.
    public enum Action: Equatable, Sendable {
        /// The row is this window's folder.
        case nothing
        /// This window shows the open folder with this key, which was in the background.
        case showHere(String)
        /// The window showing the open folder with this key comes forward, as opening an
        /// open folder does.
        case bringForward(String)
        /// The recent target opens, and this window shows it.
        case openHere(URL)
        /// The open folder with this key is shown in a new window, placed as a new folder
        /// is: its background page if it has one, else a page of its own.
        case newWindow(String)
        /// The recent target opens in a new window, as File > Open Recent opens it.
        case openInNewWindow(URL)
    }

    /// The subtitle of a folder another window shows.
    public static let inAnotherWindow = "In another window"

    /// What a chooser row shows of `subtitle`, on one line: all of it when `fits` says it
    /// fits, else the longest middle truncation of it that does (`middleTruncated`), as the
    /// Switch Folder panel's label cuts the same subtitle. AppKit wraps a menu item's
    /// subtitle that is too wide, which would put the row's mark between lines again.
    ///
    /// `fits` is asked about the whole subtitle, then about truncations in a binary search
    /// over how many characters to keep, so about `log2` of the length times. What comes
    /// back is a string `fits` answered true for, or, should none, the ellipsis alone.
    public static func oneLine(_ subtitle: String, fits: (String) -> Bool) -> String {
        guard !subtitle.isEmpty, !fits(subtitle) else { return subtitle }
        // `kept` characters fit, the ellipsis alone at first; `tooMany` do not.
        var kept = 0
        var tooMany = subtitle.count
        while tooMany - kept > 1 {
            let tried = (kept + tooMany) / 2
            if fits(middleTruncated(subtitle, keeping: tried)) { kept = tried } else { tooMany = tried }
        }
        return middleTruncated(subtitle, keeping: kept)
    }

    /// `text` with its middle replaced by an ellipsis, keeping `kept` of its characters:
    /// the first half of them, rounded up, and the last half. `text` itself when it has no
    /// more than `kept`.
    public static func middleTruncated(_ text: String, keeping kept: Int) -> String {
        guard kept < text.count else { return text }
        return String(text.prefix((kept + 1) / 2)) + "…" + String(text.suffix(kept / 2))
    }

    /// The chooser's rows: `open` in the order the folders opened, then `recent` less
    /// those that are open, in their order.
    public static func menuRows(
        open: [OpenFolder], recent: [RecentTargets.Item], home: String = FileChecks.canonicalPath(NSHomeDirectory())
    ) -> [Row] {
        open.map(row) + recentRows(recent, excluding: Set(open.map(\.key)), home: home)
    }

    /// The panel's rows: `open` most recently shown first, as `byRecency` orders their
    /// keys, with this window's folder last, after the recent targets.
    public static func panelRows(
        open: [OpenFolder], byRecency: [String], recent: [RecentTargets.Item],
        home: String = FileChecks.canonicalPath(NSHomeDirectory())
    ) -> [Row] {
        let rank = Dictionary(byRecency.enumerated().map { ($1, $0) }, uniquingKeysWith: min)
        let ordered = open.enumerated().sorted { lhs, rhs in
            let left = rank[lhs.element.key] ?? byRecency.count + lhs.offset
            let right = rank[rhs.element.key] ?? byRecency.count + rhs.offset
            return left < right
        }.map(\.element)
        let here = ordered.filter { $0.shown == .here }
        let others = ordered.filter { $0.shown != .here }
        return others.map(row) + recentRows(recent, excluding: Set(open.map(\.key)), home: home) + here.map(row)
    }

    /// What choosing `target` does, in a new window when `newWindow`: the chooser's
    /// Option alternates, and the panel's Option-Return.
    public static func action(for target: Target, newWindow: Bool) -> Action {
        switch (target, newWindow) {
        case (.open(let key, _), true): .newWindow(key)
        case (.open(_, .here), false): .nothing
        case (.open(let key, .background), false): .showHere(key)
        case (.open(let key, .inAnotherWindow), false): .bringForward(key)
        case (.recent(let url), false): .openHere(url)
        case (.recent(let url), true): .openInNewWindow(url)
        }
    }

    /// The rows of `rows` that `query` matches: those whose title or location holds every
    /// word of it, ignoring case and diacritics, in the order given. An empty query
    /// matches every row.
    public static func matching(_ rows: [Row], query: String) -> [Row] {
        let words = query.split(whereSeparator: \.isWhitespace).map(String.init)
        guard !words.isEmpty else { return rows }
        return rows.filter { row in
            words.allSatisfy { word in
                [row.title, row.location].contains {
                    $0.range(of: word, options: [.caseInsensitive, .diacriticInsensitive]) != nil
                }
            }
        }
    }

    /// The key `target` would have as an open folder, so a recent target that is open is
    /// left out: a folder's canonical path without a trailing slash, as a session names
    /// it, or a repository's address, its session's key.
    public static func key(of target: RecentTarget) -> String {
        var root = target.root
        if target.mode == .folder { while root.count > 1, root.hasSuffix("/") { root.removeLast() } }
        return root
    }

    private static func row(_ folder: OpenFolder) -> Row {
        Row(
            section: .open, title: folder.title,
            subtitle: folder.shown == .inAnotherWindow ? inAnotherWindow : folder.location,
            location: folder.location, mark: folder.mark, isChecked: folder.shown == .here,
            target: .open(folder.key, folder.shown))
    }

    private static func recentRows(_ recent: [RecentTargets.Item], excluding open: Set<String>, home: String) -> [Row] {
        recent.filter { !open.contains(key(of: $0.target)) }.map { item in
            let location = item.target.identity(home: home).fullName
            return Row(
                section: .recent, title: item.title, subtitle: location, location: location,
                mark: RootMark(item.target), isChecked: false, target: .recent(item.url))
        }
    }
}

/// The Switch Folder panel's state: its rows (`FolderChooser.panelRows`), the search, the
/// rows it matches, and the selected one, which Return chooses and Command-Delete closes;
/// what each key pressed in its search field does (`command(for:text:)`); and where the
/// panel opens (`frame(size:over:visible:)`). `SwitchFolderWindowController` shows it,
/// passes on the user's keys, and carries out each command.
public nonisolated struct FolderSwitcher: Equatable, Sendable {
    /// What a key pressed in the panel's search field does.
    public enum Command: Equatable, Sendable {
        /// Up or Down: the selection moves by this many rows.
        case move(Int)
        /// Return, or Option-Return for a new window: the selected row is chosen.
        case choose(newWindow: Bool)
        /// Escape: the panel closes.
        case dismiss
        /// Command-Delete with nothing typed: the open folder with this key closes.
        case close(String)
        /// Tab and Shift-Tab: nothing, so the field keeps the focus and the panel its keys.
        case ignore
        /// Any other key: the field edits its text as any text field does.
        case edit
    }

    /// A key the search field passes on, as AppKit reports it.
    public struct Key: Equatable, Sendable {
        /// The command the key's binding sends, as `NSStringFromSelector` names it:
        /// `moveUp:` for Up, `deleteToBeginningOfLine:` for Command-Delete.
        public var command: String
        /// Return or Enter was pressed, rather than another key bound to the same command,
        /// as Control-O is bound to Option-Return's `insertNewlineIgnoringFieldEditor:`.
        public var isReturn: Bool
        /// Option was held.
        public var option: Bool

        public init(command: String, isReturn: Bool = false, option: Bool = false) {
            self.command = command
            self.isReturn = isReturn
            self.option = option
        }
    }

    /// How far below a window's top edge the panel's top opens, so the window's title,
    /// which names the folder the panel switches, stays in view above it.
    public static let dropBelowWindowTop: CGFloat = 80

    /// Every row, in the panel's order.
    public private(set) var rows: [FolderChooser.Row]
    public private(set) var query = ""
    /// The rows the search matches, in the panel's order.
    public private(set) var shown: [FolderChooser.Row]
    /// The selected row's index in `shown`; nil while nothing matches.
    public private(set) var selected: Int?

    /// The panel opens on its first row: the folder shown before this window's.
    public init(rows: [FolderChooser.Row]) {
        self.rows = rows
        shown = rows
        selected = rows.isEmpty ? nil : 0
    }

    /// The search changed: the first match is selected, as Open Quickly selects it.
    public mutating func search(_ query: String) {
        self.query = query
        shown = FolderChooser.matching(rows, query: query)
        selected = shown.isEmpty ? nil : 0
    }

    /// Up or Down: the selection moves by `delta`, and stops at either end.
    public mutating func move(by delta: Int) {
        guard let current = selected else { return }
        selected = min(max(current + delta, 0), shown.count - 1)
    }

    /// A click on a row.
    public mutating func select(_ index: Int) {
        if shown.indices.contains(index) { selected = index }
    }

    /// What Return chooses, or Option-Return with `newWindow`; nil with nothing selected.
    public func choice(newWindow: Bool) -> FolderChooser.Action? {
        guard let selected else { return nil }
        return FolderChooser.action(for: shown[selected].target, newWindow: newWindow)
    }

    /// The open folder Command-Delete closes once the field is empty: the selected row's,
    /// if it is open.
    public var closable: String? {
        guard let selected, case .open(let key, _) = shown[selected].target else { return nil }
        return key
    }

    /// What `key` does in the search field, which holds `text`.
    ///
    /// Command-Delete is the field's own delete-to-start-of-line while anything is typed,
    /// so it clears a search as it would in any field; only with the field empty does it
    /// close the selected open folder, which the unfiltered list shows selected. Control-O
    /// sends Option-Return's command, and edits the field as it would anywhere.
    public func command(for key: Key, text: String) -> Command {
        switch key.command {
        case "moveUp:": .move(-1)
        case "moveDown:": .move(1)
        case "insertNewline:": .choose(newWindow: key.option)
        case "insertNewlineIgnoringFieldEditor:": key.isReturn ? .choose(newWindow: true) : .edit
        case "cancelOperation:": .dismiss
        case "insertTab:", "insertBacktab:": .ignore
        case "deleteToBeginningOfLine:": text.isEmpty ? closable.map(Command.close) ?? .edit : .edit
        default: .edit
        }
    }

    /// The rows changed under the panel, as when Command-Delete closed a folder: the
    /// search stays, and so does the selection's place in the list, kept in range.
    public mutating func reload(_ rows: [FolderChooser.Row]) {
        let place = selected ?? 0
        self.rows = rows
        shown = FolderChooser.matching(rows, query: query)
        selected = shown.isEmpty ? nil : min(place, shown.count - 1)
    }

    /// The panel's frame, `size` large, over a window whose frame is `window`: centered
    /// across it, `dropBelowWindowTop` below its top edge, and moved onto `visible`, its
    /// screen's visible frame, where it would run past an edge, as for a short window near
    /// the bottom of the screen or one dragged partly off it. On a screen too small for
    /// the panel, its top left corner stays on screen, so its field can be reached.
    ///
    /// Frames are in AppKit's screen coordinates, whose y axis points up.
    public static func frame(size: CGSize, over window: CGRect, visible: CGRect?) -> CGRect {
        var x = (window.midX - size.width / 2).rounded()
        var y = (window.maxY - dropBelowWindowTop - size.height).rounded()
        if let visible {
            x = max(min(x, visible.maxX - size.width), visible.minX)
            y = min(max(y, visible.minY), visible.maxY - size.height)
        }
        return CGRect(origin: CGPoint(x: x, y: y), size: size)
    }
}
