import Darwin
import Foundation

/// A download that replaces an existing file, written beside it and moved over it only
/// once it is complete.
///
/// The save panel has already asked whether to replace the file, and `WKDownload`
/// refuses a destination that exists. Removing the original at that point would lose it
/// whenever the transfer then failed, was cancelled, or the app quit, so the download
/// goes to a staging file in a temporary directory on the destination's volume, and
/// `commit()` renames it over the destination in one step. Until then the original is
/// untouched, and `discard()` leaves it that way.
public nonisolated struct StagedDownload: Equatable, Sendable {
    /// Where the user chose to save.
    public let destination: URL
    /// Where `WKDownload` writes: the only file in `directory`.
    public let staging: URL
    /// A directory of its own on the destination's volume, so `rename(2)` can replace the
    /// destination atomically. `commit()` and `discard()` remove it.
    public let directory: URL

    /// A staging file for `destination` when something is already there, or nil when the
    /// destination is free and the download can be written to it directly.
    public static func prepare(for destination: URL, fileManager: FileManager = .default) throws -> StagedDownload? {
        var info = stat()
        // lstat: a symlink, even a dangling one, is something WKDownload would refuse.
        guard lstat(destination.path(percentEncoded: false), &info) == 0 else { return nil }
        let directory = try fileManager.url(
            for: .itemReplacementDirectory, in: .userDomainMask, appropriateFor: destination, create: true)
        return StagedDownload(
            destination: destination, staging: directory.appending(path: destination.lastPathComponent),
            directory: directory)
    }

    /// Moves the finished download over the destination in one `rename(2)`, then removes
    /// the staging directory. If the rename fails, the destination is as it was.
    public func commit() throws {
        defer { discard() }
        guard rename(staging.path(percentEncoded: false), destination.path(percentEncoded: false)) == 0 else {
            throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO)
        }
    }

    /// Removes the staging directory and whatever part of the download reached it.
    ///
    /// A removal that fails leaves no user file behind: the directory is in the volume's
    /// temporary items, which macOS empties itself.
    public func discard() {
        try? FileManager.default.removeItem(at: directory)
    }
}
