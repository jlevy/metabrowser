import Darwin
import Foundation

/// The folder windows open when the app last saved, front window first, which the next
/// launch recreates.
public nonisolated struct SavedSession: Codable, Equatable, Sendable {
    public var windows: [SavedWindow]

    public init(windows: [SavedWindow]) {
        self.windows = windows
    }

    /// The session without what cannot be shown: a tab whose root is not an absolute path,
    /// or whose folder `isFolder` says is gone, and a window left with no tab. Each
    /// window's selection stays on its tab, or moves to the nearest one kept.
    ///
    /// A protected root (`ProtectedLocations`) is kept unchecked, since even looking at it
    /// could raise the privacy prompt the restore defers; if it is gone, its window says so
    /// when its tab is selected.
    public func restorable(isProtected: (String) -> Bool, isFolder: (String) -> Bool) -> SavedSession {
        var windows: [SavedWindow] = []
        for window in self.windows {
            var tabs: [SavedTab] = []
            var selected = 0
            for (index, tab) in window.tabs.enumerated()
            where tab.root.hasPrefix("/") && (isProtected(tab.root) || isFolder(tab.root)) {
                if index <= window.selected { selected = tabs.count }
                tabs.append(tab)
            }
            guard !tabs.isEmpty else { continue }
            windows.append(SavedWindow(tabs: tabs, selected: selected, frame: window.frame))
        }
        return SavedSession(windows: windows)
    }
}

/// One window and its tabs.
public nonisolated struct SavedWindow: Codable, Equatable, Sendable {
    /// In tab-bar order; a window without a tab bar has one.
    public var tabs: [SavedTab]
    /// The index of the tab the window shows.
    public var selected: Int
    /// `NSWindow.frameDescriptor`, which `NSWindow.setFrame(from:)` reads back.
    public var frame: String?

    public init(tabs: [SavedTab], selected: Int, frame: String?) {
        self.tabs = tabs
        self.selected = selected
        self.frame = frame
    }
}

public nonisolated struct SavedTab: Codable, Equatable, Sendable {
    /// The canonical path of the folder the tab's server serves.
    public var root: String
    /// The page the tab showed, or nil for the folder's entry page.
    public var page: PageAddress?

    public init(root: String, page: PageAddress?) {
        self.root = root
        self.page = page
    }
}

/// The order a restored session's servers start in, one at a time.
///
/// The front window's tab starts first, then the tabs the other windows show, front to
/// back, then every other tab, window by window. Each root starts once, however many
/// tabs show it. A root in a protected location starts only once one of its tabs is
/// selected, so a restore raises no privacy prompt for a folder nobody is looking at;
/// the front tab is selected, so it starts even there. A selected tab starts next.
public nonisolated struct RestoreQueue: Equatable, Sendable {
    /// The roots to start, in order.
    public private(set) var pending: [String] = []
    /// The protected roots waiting for one of their tabs to be selected.
    public private(set) var deferred: [String] = []

    public init(_ session: SavedSession, isProtected: (String) -> Bool) {
        let shown = session.windows.compactMap { window in
            window.tabs.indices.contains(window.selected) ? window.tabs[window.selected].root : nil
        }
        let rest = session.windows.flatMap { $0.tabs.map(\.root) }
        for (index, root) in (shown + rest).enumerated() where !pending.contains(root) && !deferred.contains(root) {
            if index > 0, isProtected(root) {
                deferred.append(root)
            } else {
                pending.append(root)
            }
        }
    }

    public var isEmpty: Bool { pending.isEmpty && deferred.isEmpty }

    public mutating func next() -> String? {
        pending.isEmpty ? nil : pending.removeFirst()
    }

    /// A tab of `root` was selected: it starts next. Returns false if `root` is not
    /// waiting to start, because it has started or is not part of the restore.
    @discardableResult
    public mutating func select(_ root: String) -> Bool {
        guard pending.contains(root) || deferred.contains(root) else { return false }
        remove(root)
        pending.insert(root, at: 0)
        return true
    }

    /// Every tab of `root` closed before its server started.
    public mutating func remove(_ root: String) {
        pending.removeAll { $0 == root }
        deferred.removeAll { $0 == root }
    }
}

/// The saved session: one JSON file, owner-only, in the app's own Application Support
/// folder, which the bundle identifier names, so each variant keeps its own.
///
/// A save publishes atomically: it writes a private temporary file beside the session
/// and renames it over the old one, so a reader, the next launch after a crash
/// included, finds the previous session or the new one and never part of one. It
/// promises atomic visibility, not durability: a power loss may lose the last save,
/// which costs only the windows of that moment.
public nonisolated struct SessionStore: Sendable {
    public static let fileName = "session.json"
    /// A session of a hundred tabs is about 20 KB; a file past this is not one.
    public static let byteLimit = 1 << 20

    public enum LoadError: Error, Equatable {
        case tooLarge(Int)
    }

    public let url: URL

    public init(directory: URL) {
        url = directory.appending(path: Self.fileName)
    }

    /// The saved session, or nil if there is none.
    public func load() throws -> SavedSession? {
        let path = url.path(percentEncoded: false)
        var info = stat()
        guard stat(path, &info) == 0 else {
            if errno == ENOENT { return nil }
            throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO)
        }
        guard Int(info.st_size) <= Self.byteLimit else { throw LoadError.tooLarge(Int(info.st_size)) }
        return try JSONDecoder().decode(SavedSession.self, from: Data(contentsOf: url))
    }

    public func save(_ session: SavedSession) throws {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
        let data = try encoder.encode(session)
        let directory = url.deletingLastPathComponent()
        try FileManager.default.createDirectory(
            at: directory, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        let temporary = directory.appending(path: ".\(Self.fileName).\(UUID().uuidString)")
        let temporaryPath = temporary.path(percentEncoded: false)
        let fd = open(temporaryPath, O_WRONLY | O_CREAT | O_EXCL | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO) }
        var published = false
        defer { if !published { unlink(temporaryPath) } }
        let written = data.withUnsafeBytes { bytes in
            var offset = 0
            while offset < bytes.count {
                let count = write(fd, bytes.baseAddress! + offset, bytes.count - offset)
                if count < 0 {
                    if errno == EINTR { continue }
                    return false
                }
                offset += count
            }
            return true
        }
        let writeError = errno
        guard close(fd) == 0, written else {
            throw POSIXError(POSIXErrorCode(rawValue: written ? errno : writeError) ?? .EIO)
        }
        guard rename(temporaryPath, url.path(percentEncoded: false)) == 0 else {
            throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO)
        }
        published = true
    }
}
