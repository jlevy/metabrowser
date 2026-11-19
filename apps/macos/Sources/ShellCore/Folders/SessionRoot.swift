import Foundation

/// What one session serves, and so what finds it: a folder on this Mac, or a repository
/// on GitHub, which `metab` clones into its cache or finds there.
///
/// A repository is keyed by its canonical URL, `https://github.com/<owner>/<repo>`, as
/// `metab URL --present --dry-run --format json` reports it (`PresentPlan`), never by its
/// pin: a page can switch the pin while the server runs (View on branch), so a key that
/// held the pin would stop naming the session. Every link into one repository opens in
/// its one session, then, which starts its server again on a link that its window does
/// not show (`FolderSession.open(link:)`).
public nonisolated enum SessionRoot: Hashable, Sendable {
    /// A canonical folder, as `OpenTarget` resolves one.
    case folder(URL)
    /// A repository's canonical URL (`PresentPlan.repositoryURL`).
    case repository(URL)

    public var url: URL {
        switch self {
        case .folder(let url), .repository(let url): url
        }
    }

    public var isLocal: Bool {
        if case .folder = self { return true }
        return false
    }

    /// Its session's one key, wherever the app looks an open folder up: among the open
    /// servers (`ServerFleet`), the open folders (`OpenFolders`), and the restore. A
    /// folder's is its path without a trailing slash, as `OpenTarget` and the saved session
    /// spell a root; a repository's is its URL, which starts with its scheme and so is
    /// never a path.
    public var key: String {
        switch self {
        case .folder(let url):
            var path = url.path(percentEncoded: false)
            while path.count > 1, path.hasSuffix("/") { path.removeLast() }
            return path
        case .repository(let url):
            return url.absoluteString
        }
    }

    /// What its windows call it until its server answers `/api/identity`.
    public func identity(home: String = FileChecks.canonicalPath(NSHomeDirectory())) -> FolderIdentity {
        switch self {
        case .folder(let url): .localFolder(url, home: home)
        case .repository(let url): .repository(url)
        }
    }

    /// Which servers it starts among: its port walk, and the launch gate it waits at.
    public var lane: LaunchLane { isLocal ? .folders : .repositories }
}

/// A kind of server that starts behind a `LaunchGate` of its own, because its port walk
/// covers ports no other lane's reaches. One value names both, so a session's gate and the
/// port its walk starts from cannot disagree: the app holds one gate per lane.
public nonisolated enum LaunchLane: CaseIterable, Hashable, Sendable {
    case folders
    /// Repositories, whose start can clone for minutes before it walks.
    case repositories

    /// Where its servers' port walk starts.
    public var basePort: Int {
        switch self {
        case .folders: CLIServeLaunch.defaultBasePort
        case .repositories: CLIServeLaunch.repositoryBasePort
        }
    }

    /// Every port its walk can reach.
    public var ports: Range<Int> { basePort..<(basePort + CLIServeLaunch.portSearchCount) }
}
