import Darwin

/// What a file is on disk, cheap to take and to compare. A new fingerprint means the
/// file was replaced or rewritten, as `uv tool upgrade` replaces `metab`, without
/// running it: an installer that renames a new file over the old one changes the
/// inode, one that rewrites in place changes the modification time, and `chmod +x`,
/// which can be all that stands between a file and a working `metab`, changes the mode.
public nonisolated struct FileFingerprint: Codable, Equatable, Sendable {
    public var device: Int32
    public var inode: UInt64
    public var size: Int64
    /// The modification time in nanoseconds since 1970.
    public var modified: Int64
    /// `st_mode`: the file's type and permission bits.
    public var mode: UInt16

    public init(device: Int32, inode: UInt64, size: Int64, modified: Int64, mode: UInt16) {
        self.device = device
        self.inode = inode
        self.size = size
        self.modified = modified
        self.mode = mode
    }

    /// The file `path` names, after symbolic links (uv's tool links among them), or nil
    /// when there is none.
    public static func of(_ path: String) -> FileFingerprint? {
        var info = stat()
        guard stat(path, &info) == 0 else { return nil }
        let nanosecondsPerSecond: Int64 = 1_000_000_000
        return FileFingerprint(
            device: info.st_dev, inode: info.st_ino, size: info.st_size,
            modified: Int64(info.st_mtimespec.tv_sec) * nanosecondsPerSecond + Int64(info.st_mtimespec.tv_nsec),
            mode: info.st_mode)
    }
}

/// Notices files that change and then stay changed.
///
/// A change counts once two looks in a row see the same new state. That debounces an
/// install seen halfway, a file removed and not yet written again, without proving the
/// installer is done with it: whatever the change leads to checks the file again, and a
/// later change is a new one.
public final class FileWatch {
    private enum Seen: Equatable {
        case nothing
        case file(FileFingerprint)

        init(_ fingerprint: FileFingerprint?) {
            self = fingerprint.map(Seen.file) ?? .nothing
        }
    }

    private struct Entry {
        let path: String
        var reported: Seen
        var pending: Seen?
    }

    private var entries: [Entry]
    private let fingerprint: (String) -> FileFingerprint?

    /// Watches each path for changes from the state given for it.
    public init(baseline: [(path: String, fingerprint: FileFingerprint?)], fingerprint: @escaping (String) -> FileFingerprint?) {
        entries = baseline.map { Entry(path: $0.path, reported: Seen($0.fingerprint)) }
        self.fingerprint = fingerprint
    }

    /// Watches each path for changes from its state now.
    public convenience init(watching paths: [String], fingerprint: @escaping (String) -> FileFingerprint?) {
        self.init(baseline: paths.map { ($0, fingerprint($0)) }, fingerprint: fingerprint)
    }

    /// The paths whose change settled since the last look, in the order given.
    public func look() -> [String] {
        var settled: [String] = []
        for index in entries.indices {
            let now = Seen(fingerprint(entries[index].path))
            if now == entries[index].reported {
                entries[index].pending = nil
            } else if now == entries[index].pending {
                entries[index].reported = now
                entries[index].pending = nil
                settled.append(entries[index].path)
            } else {
                entries[index].pending = now
            }
        }
        return settled
    }
}

/// What the app watches between folders, and what it does when a watched file settles.
///
/// With a runtime it watches that runtime's executable against the fingerprint taken
/// when it was validated, so an upgrade made in Terminal, even before the watch began,
/// leads to a recheck. Without one it waits: for `metab` to appear where discovery
/// looks, and for `uv`, which changes the steps the first-run screen shows.
public final class SetupWatch {
    public enum Action: Equatable, Sendable {
        /// Validate the runtime again (`RuntimeDiscovery.validate`).
        case recheck
        /// Search for `metab` again: one appeared, changed, or went away.
        case discover
        /// Work out the first-run steps again: `uv` appeared or went away.
        case replan
    }

    /// How often the app looks. Each look is one `stat` per watched path.
    public static let interval: Duration = .seconds(1)

    private let files: FileWatch
    private let metabPaths: Set<String>
    private let watchesRuntime: Bool

    public init(runtime: Runtime, fingerprint: @escaping (String) -> FileFingerprint? = FileFingerprint.of) {
        files = FileWatch(baseline: [(runtime.executable, runtime.fingerprint)], fingerprint: fingerprint)
        metabPaths = [runtime.executable]
        watchesRuntime = true
    }

    public init(
        waitingFor metabPaths: [String], uv uvPaths: [String],
        fingerprint: @escaping (String) -> FileFingerprint? = FileFingerprint.of
    ) {
        files = FileWatch(watching: metabPaths + uvPaths, fingerprint: fingerprint)
        self.metabPaths = Set(metabPaths)
        watchesRuntime = false
    }

    /// Where to wait for `metab`, in order and once each: the places discovery looks
    /// without a shell, every candidate the last search tried (those it found on the
    /// login shell's `PATH` among them, so upgrading one found there is noticed too), and
    /// the directory uv said it installs into.
    public static func metabPaths(cheap: [String], tried: [CandidateOutcome], binDirectory: String?) -> [String] {
        var paths: [String] = []
        for path in cheap + tried.map(\.path) + [binDirectory.map { $0 + "/metab" }].compactMap(\.self)
        where !paths.contains(path) {
            paths.append(path)
        }
        return paths
    }

    public func look() -> Action? {
        let changed = files.look()
        if changed.isEmpty { return nil }
        if watchesRuntime { return .recheck }
        return changed.contains(where: metabPaths.contains) ? .discover : .replan
    }
}
