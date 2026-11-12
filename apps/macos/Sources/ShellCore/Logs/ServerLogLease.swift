import Darwin
import Foundation

/// One app process's claim on a folder's server log, held for as long as it serves the
/// folder.
///
/// Two copies of the app with one bundle identifier, such as development builds run from
/// two checkouts, share a logs folder and can serve the same folder at once. Both writing
/// one log would mix their servers' output, and each error view, which reads its server's
/// part of the log, would show the other's lines. So the first copy claims the folder's
/// log, `<folder>-<hash>.log`, and a copy that finds it claimed writes
/// `<folder>-<hash>.app-<pid>.log` beside it instead.
///
/// The claim is an exclusive `flock` on a hidden lock file beside the log, so rotating the
/// log does not move it. The kernel releases it when this lease goes away, and when the
/// process ends however it ends, so a crashed copy holds no claim.
public nonisolated final class ServerLogLease: Sendable {
    /// The log this copy writes for the folder.
    public let url: URL
    private let lock: Int32

    private init(url: URL, lock: Int32) {
        self.url = url
        self.lock = lock
    }

    deinit { close(lock) }

    /// Claims the folder's log in `directory`, or, if another live process holds it, a
    /// log named for `owner`, this process.
    public static func claim(
        for root: URL, in directory: URL, owner: pid_t = getpid()
    ) throws(ServerLogError) -> ServerLogLease {
        let shared = ServerLog.url(for: root, in: directory)
        let own = directory.appending(path: shared.deletingPathExtension().lastPathComponent + ".app-\(owner).log")
        do {
            try FileManager.default.createDirectory(
                at: directory, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        } catch {
            throw ServerLogError("create", directory.path(percentEncoded: false), reason: error.localizedDescription)
        }
        for candidate in [shared, own] {
            if let lock = try lockIfFree(candidate) { return ServerLogLease(url: candidate, lock: lock) }
        }
        // A log named for this pid held by another live process: possible only while an
        // earlier process with this pid is still exiting. Refused, not shared.
        throw ServerLogError("claim", own.path(percentEncoded: false), reason: "another process holds it")
    }

    /// The lock file's descriptor, holding the claim, or nil if another process holds it.
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
