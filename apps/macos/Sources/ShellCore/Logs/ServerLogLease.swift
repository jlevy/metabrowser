import Darwin
import Foundation

/// One folder session's claim on a folder's server log, held for as long as it serves the
/// folder, which outlasts its windows while its server stops.
///
/// Two copies of the app with one bundle identifier, such as development builds run from
/// two checkouts, share a logs folder and can serve the same folder at once. Both writing
/// one log would mix their servers' output, and each error view, which reads its server's
/// part of the log, would show the other's lines. So the first copy claims the folder's
/// log, `<folder>-<hash>.log`, and a copy that finds it claimed writes
/// `<folder>-<hash>.app-<pid>.log` beside it instead.
///
/// One copy can also hold several claims on a folder at once: a session whose last window
/// closed keeps its claim until its server has stopped (`ServerFleet.retire`), and the
/// folder can be opened again before then. The new session takes the first name free,
/// `<folder>-<hash>.app-<pid>-2.log` once the copy's own is held, and so on, so no two
/// servers write one log however their lifetimes overlap.
///
/// The claim is an exclusive `flock` on a hidden lock file beside the log, so rotating the
/// log does not move it. A lock belongs to its open file, so two claims of one process
/// exclude each other too. The kernel releases it when this lease goes away, and when the
/// process ends however it ends, so a crashed copy holds no claim.
public nonisolated final class ServerLogLease: Sendable {
    /// How many logs named for one process a claim tries. Each one held but the newest is
    /// a session of the folder still stopping, and a stop takes at most
    /// `SupervisorPolicy.shutdownGrace`, `killWait`, and `outputSettle`, under 8 seconds by
    /// default. Closing and opening one folder 16 times within one stop is not a case to
    /// serve, and the bound keeps a claim from searching on.
    public static let ownLogLimit = 16

    /// The log this session writes for the folder.
    public let url: URL
    private let lock: Int32

    private init(url: URL, lock: Int32) {
        self.url = url
        self.lock = lock
    }

    deinit { close(lock) }

    /// Claims the folder's log in `directory`, or, if another claim holds it, the first
    /// free log named for `owner`, this process.
    public static func claim(
        for root: URL, in directory: URL, owner: pid_t = getpid()
    ) throws(ServerLogError) -> ServerLogLease {
        let shared = ServerLog.url(for: root, in: directory)
        let stem = shared.deletingPathExtension().lastPathComponent + ".app-\(owner)"
        let own = (1...ownLogLimit).map { directory.appending(path: stem + ($0 == 1 ? "" : "-\($0)") + ".log") }
        do {
            try FileManager.default.createDirectory(
                at: directory, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        } catch {
            throw ServerLogError("create", directory.path(percentEncoded: false), reason: error.localizedDescription)
        }
        for candidate in [shared] + own {
            if let lock = try lockIfFree(candidate) { return ServerLogLease(url: candidate, lock: lock) }
        }
        // Each held by a session of this process still stopping, or by an earlier process
        // with this pid still exiting. Refused, not shared.
        throw ServerLogError(
            "claim", own[0].path(percentEncoded: false),
            reason: "it and the \(ownLogLimit - 1) other logs named for this process are held")
    }

    /// The lock file's descriptor, holding the claim, or nil if another claim holds it.
    private static func lockIfFree(_ log: URL) throws(ServerLogError) -> Int32? {
        let lockFile = log.deletingLastPathComponent().appending(path: ".\(log.lastPathComponent).lock")
        let path = lockFile.path(percentEncoded: false)
        let fd = open(path, O_RDWR | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw ServerLogError("claim", path, code: errno) }
        guard flock(fd, LOCK_EX | LOCK_NB) == 0 else {
            let code = errno
            close(fd)
            if code == EWOULDBLOCK { return nil }
            throw ServerLogError("claim", path, code: code)
        }
        return fd
    }
}
