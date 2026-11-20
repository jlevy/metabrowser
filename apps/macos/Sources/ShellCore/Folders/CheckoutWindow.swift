import Foundation

/// Which open checkout's window a link's new mirror window joins as a tab.
///
/// A GitHub link always opens its repository's mirror, and a mirror with a window already
/// shows the link there (The File Menu in `docs/project/architecture/arch-open-modes.md`).
/// When no window shows the mirror yet, but one shows a checkout of the same GitHub
/// repository, the mirror's new window joins that window as a tab instead of opening on
/// its own, so a pull request link for a repository the reader has open lands where they
/// are working. The checkout's server keeps serving the checkout: the tab is the mirror's.
///
/// A checkout's repository is the one its `origin` names, as its server reports it
/// (`FolderIdentity.repository`), never its folder's name. A folder below a checkout's
/// root belongs to the checkout's repository too, as `metab` reports it.
public nonisolated enum CheckoutWindow {
    /// An open session, as a link's placement reads it.
    public struct Candidate: Equatable, Sendable {
        /// Its session key (`SessionRoot.key`).
        public var key: String
        public var root: SessionRoot
        /// The GitHub repository its server says it belongs to; nil until the server
        /// answers, and for a folder in no repository on github.com.
        public var repository: URL?
        /// Whether a window on screen shows one of its pages; a folder in the background,
        /// or only in a minimized window, has no window a tab could join.
        public var isShown: Bool

        public init(key: String, root: SessionRoot, repository: URL?, isShown: Bool) {
            self.key = key
            self.root = root
            self.repository = repository
            self.isShown = isShown
        }
    }

    /// The key of the checkout whose window a new mirror window of `repository` joins,
    /// or nil, when the mirror's window is placed as any new folder's is
    /// (`FolderPlacement`).
    ///
    /// `open` is ordered by when each was last shown, most recent first
    /// (`OpenFolders.byRecency`). Several open checkouts can belong to one repository, a
    /// clone and its worktrees, or a checkout and a folder inside it: the one shown most
    /// recently wins, since it is the one the reader was last working in. Only a local
    /// folder qualifies: a mirror of the repository would have been given the link itself.
    public static func host(for repository: URL, among open: [Candidate]) -> String? {
        open.first { candidate in
            guard candidate.root.isLocal, candidate.isShown, let theirs = candidate.repository else { return false }
            return same(theirs, repository)
        }?.key
    }

    /// Whether two canonical repository URLs name one repository. GitHub ignores letter
    /// case in owner and repository names; `metab` writes both sides in lowercase, and
    /// this still holds if one side did not.
    static func same(_ one: URL, _ other: URL) -> Bool {
        one.absoluteString.lowercased() == other.absoluteString.lowercased()
    }
}
