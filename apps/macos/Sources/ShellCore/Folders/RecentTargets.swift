import Foundation

/// One entry of `metab --recent --json`: a root, the mode it was opened in, and whether a
/// folder was a Git checkout.
///
/// `metab` keeps the list (`src/metabrowser/recent_targets.py`): every server records
/// its root as it starts, whoever started it, so the app, a `metab` run in Terminal, and
/// a restored session all end up in the one list. The app only reads it and draws it,
/// which is what lets a second shell show the same list.
public nonisolated struct RecentTarget: Codable, Equatable, Sendable {
    /// How a root was opened, fixed while it is open: `kind` in `GET /api/identity`. No
    /// entry records a view, what a server shows at a moment, so a recent folder reopens
    /// on its working tree.
    public enum Mode: String, Codable, Equatable, Sendable {
        /// A folder on this Mac, a plain folder or a repository's working tree, which
        /// records write as one mode.
        case folder
        /// A repository opened by its address and read from `metab`'s own cached copy.
        case mirror
    }

    public var mode: Mode
    /// A folder's canonical path, or a repository's address,
    /// `https://github.com/<owner>/<repo>`.
    public var root: String
    /// When it was last opened, `2026-11-18T03:14:15Z`.
    public var openedAt: String
    /// Whether a folder was a Git checkout when it was last opened: it held a `.git` entry,
    /// which is the `git` kind `GET /api/identity` gives it. `metab --recent --json` lists it
    /// for every target, so the list is read with it. The app draws the Git
    /// checkout's mark for it (`RootMark`) without looking at the folder, which could raise
    /// a privacy prompt, so a folder that became a checkout since reads as a plain one until
    /// it is opened again. Always false for a mirror.
    public var git: Bool

    public init(mode: Mode, root: String, openedAt: String, git: Bool = false) {
        self.mode = mode
        self.root = root
        self.openedAt = openedAt
        self.git = git
    }

    enum CodingKeys: String, CodingKey {
        case mode
        case root
        case openedAt = "opened_at"
        case git
    }

    /// What the app is asked to open for this entry, as a folder dropped on it or a link
    /// sent to it would be: a file URL, or the repository's own address. Nil for a root
    /// the app has no way to open, such as a mirror of a `file://` source, which only
    /// `metab` in Terminal serves.
    public var url: URL? {
        switch mode {
        case .folder:
            return root.hasPrefix("/") ? URL(filePath: root, directoryHint: .isDirectory) : nil
        case .mirror:
            guard let url = URL(string: root), url.scheme == "https", url.host() == RecentTargets.repositoryHost,
                  url.query == nil, url.fragment == nil, url.user == nil
            else { return nil }
            return url
        }
    }

    /// What it is called before any server answers, as `FolderIdentity` names a window
    /// then: a folder by its name and its path with `~` (`FolderIdentity.localFolder`), and
    /// a repository by its name and its address without the scheme, as `metab` abbreviates
    /// an origin (`FolderIdentity.repository`). A root that is no URL at all, which no row
    /// shows (`url`), is named by itself.
    public func identity(home: String = FileChecks.canonicalPath(NSHomeDirectory())) -> FolderIdentity {
        switch mode {
        case .folder:
            return .localFolder(URL(filePath: root, directoryHint: .isDirectory), git: git, home: home)
        case .mirror:
            guard let url = URL(string: root) else {
                return FolderIdentity(
                    shortName: root, fullName: root, kind: .mirror, kindLabel: FolderKind.mirror.label,
                    title: FolderIdentity.title(for: root))
            }
            return .repository(url)
        }
    }
}

/// The app's side of `metab`'s recent targets: the commands it runs, how it reads the
/// answer, and which entries File > Open Recent shows.
public nonisolated enum RecentTargets {
    /// The host of a repository root: the one host `metab`'s GitHub grammar writes.
    public static let repositoryHost = "github.com"
    /// The `Info.plist` key, a boolean, of a build that opens a link sent to it. `metab
    /// TARGET --present` reads the same key before it sends one.
    public static let opensURLsKey = "MetabrowserOpensURLs"
    /// The variable that, set to `0`, keeps a `metab` from recording anything
    /// (`RECORD_ENV` in `recent_targets.py`). The app sets it for every server that is not
    /// the first start of something the user just opened (`FolderServer`), and passes its
    /// own on, so a development run started with it records nothing at all
    /// (`ChildEnvironment.passedThrough`).
    public static let recordVariable = "METABROWSER_RECORD_RECENT"
    /// How long one of these commands may take. Each reads or rewrites one small file
    /// and starts no server; `metab --version`, which does less, gets the same
    /// (`RuntimeDiscovery.versionTimeout`).
    public static let timeout: Duration = .seconds(20)
    /// The largest answer decoded: above the largest list `metab` keeps, whose file
    /// `MAX_STORE_BYTES` in `recent_targets.py` bounds.
    public static let outputLimit = 1 << 20
    /// How soon after one answer the next is asked for. A menu asks whenever it opens,
    /// and AppKit can ask a menu to update several times for one click.
    public static let refreshInterval: Duration = .seconds(2)

    /// The mode that lists the targets. Setup refuses a `metab` without it
    /// (`RuntimeDiscovery.validate`), so every `metab` the app runs has the four modes.
    public static let listFlag = "--recent"
    public static let listArguments = [listFlag, "--json"]
    public static let clearArguments = ["--recent-clear"]

    /// Records `target` as opened, for an open that starts no server. A folder's path is
    /// absolute and a repository's address starts with its scheme, so neither can read as
    /// an option.
    public static func addArguments(_ target: String) -> [String] { [target, "--recent-add"] }

    /// What `metab` is given for `root`: a folder's path, or a repository's address whole.
    /// A URL's path alone, `/owner/repo`, would name a folder.
    public static func target(_ root: URL) -> String {
        root.isFileURL ? root.path(percentEncoded: false) : root.absoluteString
    }

    public static func forgetArguments(_ root: String) -> [String] { [root, "--recent-forget"] }

    /// `metab` with `arguments`, in the environment the app gives every `metab` it runs.
    public static func spec(_ arguments: [String], with setup: RuntimeSetup, inherited: [String: String]) -> LaunchSpec {
        LaunchSpec(
            executable: setup.runtime.executable, arguments: arguments,
            environment: ChildEnvironment.build(inherited: inherited, toolDirectories: setup.tools.directories))
    }

    /// What `metab --recent --json` answered.
    public struct Listing: Decodable, Equatable, Sendable {
        public var targets: [RecentTarget]
        /// Why a damaged file, or one a newer `metab` wrote, lists as empty.
        public var problem: String?

        public init(targets: [RecentTarget], problem: String? = nil) {
            self.targets = targets
            self.problem = problem
        }
    }

    public enum Answer: Equatable, Sendable {
        case listing(Listing)
        /// The command failed or printed something else; the text says what.
        case unreadable(String)
    }

    /// Reads the answer. Standard output and standard error share the pipe, so the
    /// object is what lies between the first line that is `{` and the last that is `}`,
    /// and a warning printed before or after it is skipped.
    public static func answer(_ result: CommandResult) -> Answer {
        if let launchError = result.launchError { return .unreadable("could not run: \(launchError)") }
        if result.timedOut { return .unreadable("did not answer within \(timeout.components.seconds) seconds") }
        guard result.succeeded else {
            return .unreadable(result.output.last ?? "exited with a failure")
        }
        guard let first = result.output.firstIndex(of: "{"), let last = result.output.lastIndex(of: "}"), first < last
        else { return .unreadable("printed no JSON object") }
        let text = result.output[first...last].joined(separator: "\n")
        guard text.utf8.count <= outputLimit else { return .unreadable("printed more than \(outputLimit) bytes") }
        do {
            return .listing(try JSONDecoder().decode(Listing.self, from: Data(text.utf8)))
        } catch {
            return .unreadable("printed JSON that is not a list of targets")
        }
    }

    /// One row of File > Open Recent.
    public struct Item: Equatable, Sendable {
        public var target: RecentTarget
        /// What opening it asks the app for (`RecentTarget.url`).
        public var url: URL
        public var title: String
        public var toolTip: String
    }

    /// The rows for `targets`, in their order, which is `metab`'s: most recent first.
    ///
    /// Only what this build can open is shown: every folder, and a repository when the
    /// build opens links (`opensURLs`, from `opensURLsKey`). A row is titled by its short
    /// name, or by its full name where another row shares the short name, the rule a
    /// window's title follows (`WindowTitle.windowTitles`). Nothing here touches a listed
    /// folder: a look can raise a privacy prompt for a folder nobody asked to see.
    public static func items(
        _ targets: [RecentTarget], opensURLs: Bool, home: String = FileChecks.canonicalPath(NSHomeDirectory())
    ) -> [Item] {
        let shown = targets.compactMap { target -> (RecentTarget, URL)? in
            guard let url = target.url, target.mode == .folder || opensURLs else { return nil }
            return (target, url)
        }
        let names = shown.map { WindowTitle($0.0.identity(home: home)) }
        return zip(shown, zip(names, WindowTitle.windowTitles(names))).map { entry, naming in
            Item(target: entry.0, url: entry.1, title: naming.1, toolTip: naming.0.subtitle)
        }
    }

    /// One line of a menu drawn from the list.
    public enum Row: Equatable, Sendable {
        /// The item at this index.
        case target(Int)
        /// "No Recent Items".
        case empty
        case separator
        /// "Clear Menu".
        case clear
    }

    /// The two menus the list is drawn in.
    public enum Menu: Equatable, Sendable {
        /// File > Open Recent.
        case openRecent
        /// The Dock icon's menu, where the Dock puts its own items after these.
        case dock
    }

    /// The lines of `menu` for `count` items. Both menus hold every item, in the list's
    /// order, so the Dock and File > Open Recent never disagree. Open Recent says when
    /// there are none and ends with Clear Menu; the Dock's holds the items alone, and
    /// nothing when there are none.
    public static func rows(for menu: Menu, count: Int) -> [Row] {
        let targets = (0..<count).map(Row.target)
        switch menu {
        case .dock: return targets
        case .openRecent: return (targets.isEmpty ? [.empty] : targets) + [.separator, .clear]
        }
    }

    /// Whether the build described by `infoDictionary` opens a link sent to it.
    public static func opensURLs(infoDictionary: [String: Any]) -> Bool {
        infoDictionary[opensURLsKey] as? Bool == true
    }
}
