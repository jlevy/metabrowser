import Darwin
import Foundation
import os

/// One child's server log: the file the child's stderr is, where the app appends the
/// child's stdout, and where the error view reads what this child wrote.
///
/// The descriptor is opened once, read-write and append-only, and kept: the child gets
/// a copy as its stderr, appends go to the end, and reads use `pread` from where the log
/// ended when the child started, so neither an earlier run nor a rotation that renames
/// the file confuses them.
nonisolated final class ChildLog: @unchecked Sendable {
    let path: String
    let handle: FileHandle
    /// The log's length when this child started: where its output begins.
    private let start: off_t
    /// Only the one serial reader of the child's stdout appends.
    private var writable = true
    /// Why the log ends early, said once in the recent output.
    private let failure = OSAllocatedUnfairLock<String?>(initialState: nil)

    init(path: String, handle: FileHandle, start: off_t) {
        self.path = path
        self.handle = handle
        self.start = start
    }

    /// Appends, never truncates, and refuses to follow a symlink planted at the path.
    static func open(_ url: URL) throws(SpawnError) -> ChildLog {
        let path = url.path(percentEncoded: false)
        let fd = Darwin.open(path, O_RDWR | O_APPEND | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw .log(path: path, code: errno) }
        let handle = FileHandle(fileDescriptor: fd, closeOnDealloc: true)
        let end = lseek(fd, 0, SEEK_END)
        guard end >= 0 else { throw .log(path: path, code: errno) }
        return ChildLog(path: path, handle: handle, start: end)
    }

    /// Appends stdout the app read. The first write that fails (a full disk, say) ends
    /// the log, and the recent output says so: the log is where a user looks next, so it
    /// must not stop without a word.
    func append(_ chunk: Data) {
        guard writable else { return }
        do {
            try handle.write(contentsOf: chunk)
        } catch {
            writable = false
            noteFailure("could not write the server log, so it ends here: \(error.localizedDescription)")
        }
    }

    func noteFailure(_ reason: String) {
        failure.withLock { if $0 == nil { $0 = reason } }
    }

    /// The newest `limit` lines this child wrote, stdout and stderr, then why the log
    /// ends early, if it does.
    func recentLines(limit: Int) throws(ServerLogError) -> [String] {
        let fd = handle.fileDescriptor
        var info = stat()
        guard fstat(fd, &info) == 0 else { throw ServerLogError("read", path, code: errno) }
        let end = info.st_size
        let from = max(start, end - off_t(ServerLog.tailBytes))
        var data = Data(count: Int(max(0, end - from)))
        var filled = 0
        while filled < data.count {
            let read = data.withUnsafeMutableBytes { buffer in
                pread(fd, buffer.baseAddress! + filled, buffer.count - filled, from + off_t(filled))
            }
            if read < 0 { throw ServerLogError("read", path, code: errno) }
            if read == 0 { break }
            filled += read
        }
        data.removeSubrange(filled...)
        var lines = ServerLog.recentLines(in: data, truncated: from > start, limit: limit)
        if let failure = failure.withLock({ $0 }) { lines.append(failure) }
        return lines
    }
}
