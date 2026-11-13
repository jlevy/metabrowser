import CryptoKit
import Darwin
import Foundation

/// One log per served folder under `~/Library/Logs/Metabrowser/`, mode 0600.
///
/// The child's stdout and stderr are appended as written (see `SpawnedProcess`), and
/// the supervisor's lifecycle events are appended between them, so one file tells the
/// whole story of a folder's server. Console.app shows the directory under Log Reports.
public nonisolated enum ServerLog {
    /// Rotated when a launch finds it larger than this; one previous file is kept.
    public static let rotationBytes = 5_000_000

    public static func directory(home: URL = URL(filePath: NSHomeDirectory())) -> URL {
        home.appending(path: "Library/Logs/Metabrowser", directoryHint: .isDirectory)
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

    public static func url(for root: URL, home: URL = URL(filePath: NSHomeDirectory())) -> URL {
        directory(home: home).appending(path: fileName(for: root))
    }

    /// Creates the directory (0700) and the file (0600), tightens a file that exists
    /// with wider permissions, and rotates one that has grown past `rotateAbove`.
    public static func prepare(_ url: URL, rotateAbove limit: Int = rotationBytes) throws {
        let directory = url.deletingLastPathComponent()
        try FileManager.default.createDirectory(
            at: directory, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        let path = url.path(percentEncoded: false)
        var info = stat()
        if lstat(path, &info) == 0, info.st_mode & S_IFMT == S_IFREG, Int(info.st_size) > limit {
            let previous = path + ".1"
            _ = unlink(previous)
            _ = rename(path, previous)
        }
        let fd = open(path, O_WRONLY | O_APPEND | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO) }
        defer { close(fd) }
        guard fchmod(fd, 0o600) == 0 else { throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO) }
    }

    /// Appends `[metabrowser-app <time>] message`. Each call is one `write` to an
    /// `O_APPEND` descriptor, so it never splits a line the child is writing.
    public static func append(_ message: String, to url: URL, now: Date = Date()) {
        let line = "[metabrowser-app \(now.ISO8601Format())] \(message)\n"
        let fd = open(url.path(percentEncoded: false), O_WRONLY | O_APPEND | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { return }
        defer { close(fd) }
        _ = line.utf8CString.withUnsafeBufferPointer { buffer in
            write(fd, buffer.baseAddress, buffer.count - 1)
        }
    }
}
