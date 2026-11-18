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
                mark: RootMark(item.target.mode), isChecked: false, target: .recent(item.url))
        }
    }
}
