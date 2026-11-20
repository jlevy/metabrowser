import Foundation

/// What a link sent into a repository's session does (`FolderSession.open(link:)`).
///
/// A repository's server is started on the repository itself, never on a link, so one
/// mirror serves every link into it: a link is opened in the ready server
/// (`SourceLink`), which starts a refresh and says where the window goes, and no link
/// starts the server again, as the owner decided on 2026-11-19. A link sent while the
/// server starts, such as during a first clone, or while a Retry or Restart Server waits
/// to replace it, waits for that server to be ready; the newest such link wins, since it
/// is the page the user asked for last. A link sent to a server that failed or stopped
/// starts it again, and waits for it. A session that has shut down opens nothing.
public nonisolated struct RepositoryLinks: Equatable, Sendable {
    /// What the session does with a link it was sent.
    public enum Step: Equatable, Sendable {
        /// Open the link in the ready server now.
        case open
        /// A start is under way: the link waits for it to be ready (`serverReady()`).
        case hold
        /// The server failed or stopped: start it again; the link waits for it.
        case start
        /// The session has shut down: nothing opens.
        case none
    }

    /// The link that waits for the server to be ready.
    public private(set) var waiting: URL?
    public private(set) var isShutDown = false

    /// - Parameter waiting: the link a new session was opened with, which its first
    ///   ready server opens; nil for the repository itself, whose entry page is the
    ///   repository's.
    public init(waiting: URL? = nil) {
        self.waiting = waiting
    }

    /// `link` was sent while the server is in `state`.
    ///
    /// - Parameter restarting: whether a restart was asked for and has not yet stopped
    ///   the server, as when it waits at the launch gate while the ready server goes on
    ///   serving (`ServerSupervisor.restart`). The link then waits for the new server.
    public mutating func receive(_ link: URL, state: ServerState, restarting: Bool = false) -> Step {
        guard !isShutDown else { return .none }
        switch state {
        case .ready where !restarting:
            waiting = nil
            return .open
        case .ready, .starting, .stopping:
            waiting = link
            return .hold
        case .failed, .stopped:
            waiting = link
            return .start
        }
    }

    /// The server is ready: the link to open in it, which no longer waits, or nil.
    public mutating func serverReady() -> URL? {
        defer { waiting = nil }
        return isShutDown ? nil : waiting
    }

    /// The session's last window closed: a waiting link opens nothing.
    public mutating func shutDown() {
        isShutDown = true
        waiting = nil
    }
}
