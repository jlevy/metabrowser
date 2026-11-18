import Foundation

/// What a repository's server is started with, and what a link sent into the repository
/// does to it (`FolderSession.open(link:)`).
///
/// A link into a repository with a window starts its server again on the link, so the
/// window shows the revision the link names. A start under way, such as a first clone,
/// runs to its end first, and the newest link sent meanwhile waits for it. A link equal
/// to the one that start runs on is already being opened, so it joins that start, and a
/// link that waited for a start on that same link is dropped when the start ends: a
/// second click during a first clone neither clones nor restarts again (review C3 on
/// #539). Joining still brings the window to the link's page, whoever began the start:
/// Retry, Restart Server, and an upgrade's restart run on the target too, and the window
/// they leave would otherwise reload the page it showed (review D2). A session that has
/// shut down starts nothing.
public nonisolated struct RepositoryLinks: Equatable, Sendable {
    /// What the session does with a link it was sent.
    public enum Step: Equatable, Sendable {
        /// Start the server again now, on `target`, which is now the link.
        case restart
        /// A start is under way: the link waits for it to end (`startEnded()`).
        case hold
        /// The start under way, or the restart waiting for its turn, runs on this link
        /// already, whoever began it: the window loads that start's entry page, which is
        /// the link's, rather than the page it showed.
        case join
        /// The session has shut down: nothing starts.
        case none
    }

    /// What the server is started with: the root, or the newest link a start took.
    public private(set) var target: URL
    /// The link that waits for the start under way to end.
    public private(set) var pending: URL?
    public private(set) var isShutDown = false

    public init(target: URL) {
        self.target = target
    }

    /// `link` was sent while the server is in `state`.
    ///
    /// - Parameter restarting: whether a restart was asked for and has not yet stopped
    ///   the server, as when it waits at the launch gate while the ready server goes on
    ///   serving (`ServerSupervisor.restart`). The server then counts as starting on
    ///   `target`, and another link replaces that restart.
    public mutating func receive(_ link: URL, state: ServerState, restarting: Bool = false) -> Step {
        guard !isShutDown else { return .none }
        let same = link.absoluteString == target.absoluteString
        switch state {
        case .starting, .stopping:
            // The newest link wins: one equal to the target cancels a link held before it.
            pending = same ? nil : link
            return same ? .join : .hold
        case .ready where restarting && same:
            return .join
        case .ready, .failed, .stopped:
            target = link
            pending = nil
            return .restart
        }
    }

    /// The start under way ended, ready, failed, or stopped: the link to start again on,
    /// which is now `target`, or nil when none waits or the one that waits is the link the
    /// start ran on.
    public mutating func startEnded() -> URL? {
        defer { pending = nil }
        guard !isShutDown, let link = pending, link.absoluteString != target.absoluteString else { return nil }
        target = link
        return link
    }

    /// The session's last window closed: a held link starts nothing.
    public mutating func shutDown() {
        isShutDown = true
        pending = nil
    }
}
