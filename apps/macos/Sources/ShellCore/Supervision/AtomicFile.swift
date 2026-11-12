import Darwin
import Foundation

/// Why a file could not be published, with its path and the cause.
public nonisolated struct AtomicFileError: Error, Equatable, CustomStringConvertible {
    public var path: String
    public var reason: String

    public var description: String { "\(path): \(reason)" }
}

/// Publishing a small file whole: a reader sees the previous file or the complete new
/// one, never part of one.
nonisolated enum AtomicFile {
    /// Writes `data` to a private temporary file beside `url`, then renames it over `url`
    /// in one step. The folder is created owner-only (0700) if missing, and the file is
    /// owner-only (0600), as `mkstemp` creates it.
    ///
    /// This promises atomic visibility, not crash durability: there is no `fsync`. The
    /// callers keep state whose loss in a power failure costs nothing, since a power
    /// failure also ends what the state describes.
    static func write(_ data: Data, to url: URL) throws(AtomicFileError) {
        let directory = url.deletingLastPathComponent()
        let path = url.path(percentEncoded: false)
        do {
            try FileManager.default.createDirectory(
                at: directory, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        } catch {
            throw AtomicFileError(path: path, reason: error.localizedDescription)
        }
        var template = Array(directory.appending(path: ".\(url.lastPathComponent).XXXXXX").path(percentEncoded: false).utf8CString)
        let fd = template.withUnsafeMutableBufferPointer { mkstemp($0.baseAddress!) }
        guard fd >= 0 else { throw failure(path, errno) }
        let temporary = String(cString: template)
        var written = 0
        let count = data.count
        let code: Int32 = data.withUnsafeBytes { buffer in
            while written < count {
                let result = Darwin.write(fd, buffer.baseAddress! + written, count - written)
                if result < 0 { return errno }
                written += result
            }
            return 0
        }
        let closed = close(fd) == 0 ? 0 : errno
        guard code == 0, closed == 0, rename(temporary, path) == 0 else {
            let cause = code != 0 ? code : closed != 0 ? closed : errno
            unlink(temporary)
            throw failure(path, cause)
        }
    }

    private static func failure(_ path: String, _ code: Int32) -> AtomicFileError {
        AtomicFileError(path: path, reason: String(cString: strerror(code)))
    }
}
