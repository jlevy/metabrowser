import Darwin
import Foundation

/// What a window does with the file an Open link names once it is on this disk, the
/// folder's own file or a downloaded copy (`OpenFilePlan`): open it in the app macOS
/// assigns to its type, or, where no app is assigned to it, save it to Downloads, as a
/// browser downloads a file it cannot show. Opening a file no app is assigned to only
/// fails, with an alert that leaves the user nothing to do with the file.
public nonisolated enum OpenFileHandoff: Equatable, Sendable {
    /// Open it in the app macOS assigns to its type.
    case open(URL)
    /// Save a copy of it in the user's Downloads folder (`OpenFileSaves`).
    case saveToDownloads(URL)

    /// `defaultApp` is Launch Services' answer for a file, which the app gives as
    /// `NSWorkspace.urlForApplication(toOpen:)`: nil when no app is assigned to its type.
    public static func decide(_ file: URL, defaultApp: (URL) -> URL?) -> OpenFileHandoff {
        defaultApp(file) == nil ? .saveToDownloads(file) : .open(file)
    }
}

/// Saves a copy of a file to the user's Downloads folder, for an Open link whose file no
/// app on this Mac opens (`OpenFileHandoff.saveToDownloads`).
///
/// A save never replaces a file. It takes the first free name of the file's, the name
/// itself and then the name numbered before its extension, `report 2.pdf`, as Finder's
/// Keep Both numbers a copy, and creates each exclusively, so a file that appears between
/// two tries is passed over too. The copy keeps the file's extended attributes and mode,
/// so a pinned revision's copy stays quarantined as a web download
/// (`OpenFileDownloads.seal`), and its owner may write it, as any download, since it is
/// the user's now. It shares the file's blocks where the volume clones (`clonefile`) and
/// is written byte by byte otherwise, so a save can take a while and runs off the main
/// thread.
///
/// Writing to Downloads raises macOS's privacy prompt once, in Metabrowser's name, as
/// opening a folder there does (`ProtectedLocations`); `NSDownloadsFolderUsageDescription`
/// in `Info.plist` says why. A refusal reads as `EPERM` (`failure`).
public nonisolated enum OpenFileSaves {
    /// How many names a save tries: the name, then `name 2` through `name 1000`. Each try
    /// is one exclusive create, and a Downloads folder that already holds a thousand
    /// copies of one name is worth an alert rather than a longer search.
    public static let attempts = 1000

    /// The user's Downloads folder.
    public static var downloads: URL {
        FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask)[0]
    }

    /// The name a save tries at `attempt`, counting from 1: `name` itself, then its stem
    /// numbered before its extension, cut to fit a file name (`OpenFileTypes.fitted`).
    static func name(_ name: String, attempt: Int) -> String {
        guard attempt > 1 else { return name }
        let pathExtension = (name as NSString).pathExtension
        let stem = (name as NSString).deletingPathExtension
        return OpenFileTypes.fitted(stem, " \(attempt)" + (pathExtension.isEmpty ? "" : "." + pathExtension))
    }

    /// Copies `file` into `downloads` under the first free name of `attempts`
    /// (`name(_:attempt:)`), and returns the copy.
    public static func save(_ file: URL, into downloads: URL, attempts: Int = attempts) throws(OpenFileFailure) -> URL {
        let source = file.path(percentEncoded: false)
        let original = file.lastPathComponent
        for attempt in 1...max(attempts, 1) {
            let copy = downloads.appending(path: name(original, attempt: attempt), directoryHint: .notDirectory)
            switch place(source, at: copy.path(percentEncoded: false)) {
            case .placed:
                ownerMayWrite(copy.path(percentEncoded: false))
                return copy
            case .taken:
                continue
            case .failed(let code):
                throw failure(original, code)
            }
        }
        throw OpenFileFailure(
            name: original, reason: "no app on this Mac opens it, and Downloads already holds a file of every name it could be saved under")
    }

    /// What one try made of its name.
    enum Placement: Equatable {
        case placed
        /// A file of that name is there already.
        case taken
        case failed(Int32)
    }

    /// Creates `target` as a copy of `source`: a clone, which creates `target` whole or
    /// not at all, or, on another volume or one that does not clone, `copyBytes`.
    static func place(_ source: String, at target: String) -> Placement {
        if clonefile(source, target, 0) == 0 { return .placed }
        let code = errno
        switch code {
        case EEXIST: return .taken
        case EXDEV, ENOTSUP: return copyBytes(source, to: target)
        default: return .failed(code)
        }
    }

    /// Creates `target` exclusively and copies `source`'s bytes, extended attributes, and
    /// mode into it (`COPYFILE_ALL`). A copy that fails part way is removed: this call
    /// created it.
    static func copyBytes(_ source: String, to target: String) -> Placement {
        let input = open(source, O_RDONLY | O_CLOEXEC)
        guard input >= 0 else { return .failed(errno) }
        defer { close(input) }
        let output = open(target, O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0o600)
        guard output >= 0 else {
            let code = errno
            return code == EEXIST ? .taken : .failed(code)
        }
        let copied = fcopyfile(input, output, nil, copyfile_flags_t(COPYFILE_ALL)) == 0
        let code = errno
        close(output)
        guard copied else {
            unlink(target)
            return .failed(code)
        }
        return .placed
    }

    /// Lets the copy's owner write it, keeping the rest of its mode. A copy whose mode
    /// cannot be changed stays as it is: read-only is no reason to fail a save.
    static func ownerMayWrite(_ path: String) {
        var info = stat()
        guard stat(path, &info) == 0 else { return }
        _ = chmod(path, (info.st_mode & 0o7777) | S_IWUSR)
    }

    /// Why a save that could not create its copy failed, by `errno`. A refusal by macOS's
    /// privacy system (`EPERM`) says where to allow it, the one thing the user can do.
    static func failure(_ name: String, _ code: Int32) -> OpenFileFailure {
        guard code != EPERM else {
            return OpenFileFailure(
                name: name,
                reason: "no app on this Mac opens it, and Metabrowser is not allowed to save to Downloads. "
                    + "Allow it in System Settings > Privacy & Security > Files & Folders")
        }
        let because = String(cString: strerror(code))
        return OpenFileFailure(
            name: name, reason: "no app on this Mac opens it, and it could not be saved to Downloads (\(because))")
    }
}

/// What the app says once an Open link's file is saved to Downloads, in an alert that
/// offers Show in Finder: where the file went, and why it did not open.
public nonisolated struct OpenFileSaved: Equatable, Sendable {
    /// The copy in Downloads.
    public var copy: URL

    public init(copy: URL) {
        self.copy = copy
    }

    public var title: String { "Saved “\(copy.lastPathComponent)” to Downloads" }
    public var message: String { "No app on this Mac opens this kind of file." }
}
