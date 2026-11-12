import CryptoKit
import Darwin
import Foundation

/// Why a server log could not be prepared or written, with its path and the cause.
public nonisolated struct ServerLogError: Error, Equatable, CustomStringConvertible {
    /// What was being done: "create", "rotate", "open", "append to", "read", or "claim".
    public var operation: String
    public var path: String
    public var reason: String

    public init(_ operation: String, _ path: String, reason: String) {
        self.operation = operation
        self.path = path
        self.reason = reason
    }

    init(_ operation: String, _ path: String, code: Int32) {
        self.init(operation, path, reason: String(cString: strerror(code)))
    }

    public var description: String { "could not \(operation) the server log \(path): \(reason)" }
}

/// One log per served folder, mode 0600, in the variant's logs folder
/// (`AppIdentity.logsDirectory`): `~/Library/Logs/Metabrowser/` for a release.
///
/// The child writes its stderr here itself, the app appends its stdout as it reads it
/// (see `SpawnedProcess`), and the supervisor's lifecycle events go between them, so one
/// file tells the whole story of a folder's server. Console.app shows the directory
/// under Log Reports.
public nonisolated enum ServerLog {
    /// Rotated when a launch finds it larger than this; one previous file is kept.
    public static let rotationBytes = 5_000_000
    /// Starts every line the app itself writes, so a reader can tell them from the
    /// server's own.
    public static let appLinePrefix = "[metabrowser-app "
    /// The most of a child's log the error view reads, on the main thread: more than
    /// its newest lines take.
    static let tailBytes = 64 * 1024

    /// The newest `limit` lines of a run of log bytes, without the app's own lines. A run
    /// `truncated` at its start begins inside a line, which is dropped.
    static func recentLines(in data: Data, truncated: Bool, limit: Int) -> [String] {
        var lines: [String] = []
        let splitter = LineSplitter()
        splitter.append(data) { lines.append($0) }
        splitter.finish { lines.append($0) }
        if truncated, !lines.isEmpty { lines.removeFirst() }
        return Array(lines.filter { !$0.hasPrefix(appLinePrefix) }.suffix(limit))
    }

    /// `<folder name>-<8 hex digits of the path's SHA-256>.log`: readable, and distinct
    /// for two folders with the same name.
    public static func fileName(for root: URL) -> String {
        let path = root.path(percentEncoded: false)
        let digest = SHA256.hash(data: Data(path.utf8)).prefix(4).map { String(format: "%02x", $0) }.joined()
        var name = String(root.lastPathComponent.map { $0.isLetter || $0.isNumber || "._-".contains($0) ? $0 : "-" })
        name = String(name.prefix(48)).trimmingCharacters(in: CharacterSet(charactersIn: ".-"))
        return (name.isEmpty ? "root" : name) + "-" + digest + ".log"
    }

    public static func url(for root: URL, in directory: URL) -> URL {
        directory.appending(path: fileName(for: root))
    }

    /// Creates the directory (0700) and the file (0600), tightens a file that exists
    /// with wider permissions, and rotates one that has grown past `rotateAbove`.
    ///
    /// Every launch runs it first, so a log that cannot be kept is a failed launch the
    /// window reports, never a server whose output goes nowhere.
    public static func prepare(_ url: URL, rotateAbove limit: Int = rotationBytes) throws(ServerLogError) {
        let directory = url.deletingLastPathComponent()
        do {
            try FileManager.default.createDirectory(
                at: directory, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        } catch {
            throw ServerLogError("create", directory.path(percentEncoded: false), reason: error.localizedDescription)
        }
        let path = url.path(percentEncoded: false)
        var info = stat()
        if lstat(path, &info) == 0, info.st_mode & S_IFMT == S_IFREG, Int(info.st_size) > limit {
            let previous = path + ".1"
            guard unlink(previous) == 0 || errno == ENOENT else { throw ServerLogError("rotate", path, code: errno) }
            guard rename(path, previous) == 0 else { throw ServerLogError("rotate", path, code: errno) }
        }
        let fd = open(path, O_WRONLY | O_APPEND | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw ServerLogError("open", path, code: errno) }
        defer { close(fd) }
        guard fchmod(fd, 0o600) == 0 else { throw ServerLogError("open", path, code: errno) }
    }

    /// Appends `[metabrowser-app <time>] message`. Each call is one `write` to an
    /// `O_APPEND` descriptor, so it never splits a line the child is writing.
    public static func append(_ message: String, to url: URL, now: Date = Date()) throws(ServerLogError) {
        let bytes = Array("\(appLinePrefix)\(now.ISO8601Format())] \(message)\n".utf8)
        let path = url.path(percentEncoded: false)
        let fd = open(path, O_WRONLY | O_APPEND | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw ServerLogError("append to", path, code: errno) }
        defer { close(fd) }
        let written = bytes.withUnsafeBufferPointer { write(fd, $0.baseAddress, $0.count) }
        if written < 0 { throw ServerLogError("append to", path, code: errno) }
        if written != bytes.count {
            throw ServerLogError("append to", path, reason: "wrote \(written) of \(bytes.count) bytes")
        }
    }
}
