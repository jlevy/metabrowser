import Foundation

/// What one session serves, and so what finds it: a folder on this Mac, or a repository
/// on GitHub, which `metab` clones into its cache or finds there.
///
/// A repository is keyed by its canonical URL, `https://github.com/<owner>/<repo>`, as
/// `metab URL --present --dry-run --json` reports it (`PresentPlan`), never by its pin: a
/// page can switch the pin while the server runs (View on branch), so a key that held the
/// pin would stop naming the session. Every link into one repository opens in its one
/// session, then, and navigates that session's window to the page it names.
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

    /// Its session's key among the open servers (`ServerFleet`): a folder's path, as the
    /// app has always keyed one, or a repository's URL, which starts with its scheme and
    /// so is never a path.
    public var key: String {
        switch self {
        case .folder(let url): url.path(percentEncoded: false)
        case .repository(let url): url.absoluteString
        }
    }

    /// What its windows call it until its server answers `/api/identity`.
    public func identity(home: String = FileChecks.canonicalPath(NSHomeDirectory())) -> FolderIdentity {
        switch self {
        case .folder(let url): .localFolder(url, home: home)
        case .repository(let url): .repository(url)
        }
    }

    /// Where its server's port walk starts: a repository's apart from every folder's, so
    /// the two kinds start behind launch gates of their own.
    public var basePort: Int {
        isLocal ? CLIServeLaunch.defaultBasePort : CLIServeLaunch.repositoryBasePort
    }
}
