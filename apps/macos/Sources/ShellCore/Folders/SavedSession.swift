import Darwin
import Foundation

/// The folder windows open when the app last saved, front window first, which the next
/// launch recreates.
public nonisolated struct SavedSession: Codable, Equatable, Sendable {
    public var windows: [SavedWindow]

    public init(windows: [SavedWindow]) {
        self.windows = windows
    }

    /// The session with each tab's root admitted (`RootAdmission`): an open root takes its
    /// canonical identity, so aliases of one folder share one session and one server, a
    /// deferred root keeps the identity it resolved to, and a tab whose root is gone or
    /// invalid is dropped, as is a window left with no tab. Each window's selection stays
    /// on its tab, or moves to the nearest one kept. Each distinct root is admitted once.
    public func admitted(_ admit: (String) -> RootAdmission) -> AdmittedSession {
        var admissions: [String: RootAdmission] = [:]
        var deferred: Set<String> = []
        var windows: [SavedWindow] = []
        for window in self.windows {
            var tabs: [SavedTab] = []
            var selected = 0
            for (index, tab) in window.tabs.enumerated() {
                let admission = admissions[tab.root] ?? admit(tab.root)
                admissions[tab.root] = admission
                let root: String
                switch admission {
                case .open(let canonical):
                    root = canonical
                case .deferred(let resolved):
                    root = resolved
                    deferred.insert(resolved)
                case .gone, .invalid:
                    continue
                }
                if index <= window.selected { selected = tabs.count }
                tabs.append(SavedTab(root: root, page: tab.page))
            }
            guard !tabs.isEmpty else { continue }
            windows.append(SavedWindow(tabs: tabs, selected: selected, frame: window.frame))
        }
        return AdmittedSession(session: SavedSession(windows: windows), deferred: deferred)
    }

    /// The session cut to `budget`: its front windows, and in each its first tabs and the
    /// one it shows, until the budget's windows or tabs run out.
    public func limited(to budget: RestoreBudget) -> SavedSession {
        var windows: [SavedWindow] = []
        var tabsLeft = budget.tabs
        for window in self.windows.prefix(budget.windows) where tabsLeft > 0 {
            guard window.tabs.count > tabsLeft else {
                windows.append(window)
                tabsLeft -= window.tabs.count
                continue
            }
            var tabs = Array(window.tabs.prefix(tabsLeft))
            var selected = window.selected
            if !tabs.indices.contains(selected), window.tabs.indices.contains(selected) {
                tabs[tabs.count - 1] = window.tabs[selected]
                selected = tabs.count - 1
            }
            windows.append(SavedWindow(tabs: tabs, selected: selected, frame: window.frame))
            tabsLeft = 0
        }
        return SavedSession(windows: windows)
    }

    public var tabCount: Int { windows.reduce(0) { $0 + $1.tabs.count } }
}

/// A saved session after admission, and the roots in it whose servers wait for one of
/// their tabs to be selected.
public nonisolated struct AdmittedSession: Equatable, Sendable {
    public var session: SavedSession
    public var deferred: Set<String>
}

/// How much of a saved session a launch rebuilds; the rest is dropped.
///
/// Measured on macOS 26.5.2 by building windows that each hold a never-loaded web view,
/// as a restore builds them: tabbed into one window, 20 took 588 ms, 50 took 1.76 s,
/// and 100 took 4.47 s on the main thread, about 1.1 MB each; 20 separate windows took
/// 187 ms. Each window's shown tab then loads its page, one WebContent process of 111
/// to 143 MB (`TabDiscardPolicy`), and each distinct root starts a server of about
/// 65 MB (the server-topology brief). The standard budget keeps a launch under two
/// seconds of building and under 3 GB of pages at the measured upper figure: far past
/// an everyday session, and a bound on an edited or corrupted file.
public nonisolated struct RestoreBudget: Equatable, Sendable {
    public static let standard = RestoreBudget(windows: 20, tabs: 50)

    public var windows: Int
    public var tabs: Int

    public init(windows: Int, tabs: Int) {
        self.windows = windows
        self.tabs = tabs
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
/// A background root is checked again when its turn comes (`next(stillOpen:)`), since
/// its folder can change while the roots before it start.
public nonisolated struct RestoreQueue: Equatable, Sendable {
    /// The roots to start, in order.
    public private(set) var pending: [String] = []
    /// The roots waiting for one of their tabs to be selected.
    public private(set) var deferred: [String] = []
    /// The roots whose tab was selected, the front tab's among them: they start as the
    /// user's choice, without being checked again.
    public private(set) var selected: Set<String> = []

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
                if index == 0 { selected.insert(root) }
            }
        }
    }

    public var isEmpty: Bool { pending.isEmpty && deferred.isEmpty }

    /// The next root to start. A background root that `stillOpen` no longer admits waits
    /// for its tab instead, and the next one is tried.
    public mutating func next(stillOpen: (String) -> Bool = { _ in true }) -> String? {
        while !pending.isEmpty {
            let root = pending.removeFirst()
            if selected.contains(root) || stillOpen(root) { return root }
            deferred.append(root)
        }
        return nil
    }

    /// A tab of `root` was selected: it starts next. Returns false if `root` is not
    /// waiting to start, because it has started or is not part of the restore.
    @discardableResult
    public mutating func select(_ root: String) -> Bool {
        guard pending.contains(root) || deferred.contains(root) else { return false }
        remove(root)
        pending.insert(root, at: 0)
        selected.insert(root)
        return true
    }

    /// `root`'s launch was refused at the last check before spawning: it waits for its
    /// tab, unless a tab of it was selected.
    public mutating func hold(_ root: String) {
        guard !selected.contains(root), !deferred.contains(root) else { return }
        pending.removeAll { $0 == root }
        deferred.append(root)
    }

    /// Every tab of `root` closed before its server started.
    public mutating func remove(_ root: String) {
        pending.removeAll { $0 == root }
        deferred.removeAll { $0 == root }
        selected.remove(root)
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
        /// More than `byteLimit` bytes.
        case tooLarge
        /// A link, a pipe, or anything else but a regular file.
        case notARegularFile
    }

    /// Bytes asked of each `read(2)`.
    static let readChunk = 64 * 1024

    public let url: URL

    public init(directory: URL) {
        url = directory.appending(path: Self.fileName)
    }

    /// The saved session, or nil if there is none.
    ///
    /// The file is opened once, without following a link and without waiting on a pipe,
    /// checked through that descriptor to be a regular file, and read through it to at
    /// most one byte past `byteLimit`, so neither a replacement nor growth after the check
    /// can make the read larger.
    public func load() throws -> SavedSession? {
        try load(afterOpening: nil)
    }

    /// `afterOpening` runs between the check and the read: the seam the tests use to
    /// replace or grow the file there.
    func load(afterOpening: (() throws -> Void)?) throws -> SavedSession? {
        let fd = open(url.path(percentEncoded: false), O_RDONLY | O_NOFOLLOW | O_NONBLOCK | O_CLOEXEC)
        guard fd >= 0 else {
            switch errno {
            case ENOENT: return nil
            case ELOOP: throw LoadError.notARegularFile
            default: throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO)
            }
        }
        defer { close(fd) }
        var info = stat()
        guard fstat(fd, &info) == 0 else { throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO) }
        guard info.st_mode & S_IFMT == S_IFREG else { throw LoadError.notARegularFile }
        try afterOpening?()
        var data = Data()
        var buffer = [UInt8](repeating: 0, count: Self.readChunk)
        while data.count <= Self.byteLimit {
            let count = read(fd, &buffer, min(buffer.count, Self.byteLimit + 1 - data.count))
            if count < 0 {
                if errno == EINTR { continue }
                throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO)
            }
            if count == 0 { break }
            data.append(contentsOf: buffer[..<count])
        }
        guard data.count <= Self.byteLimit else { throw LoadError.tooLarge }
        return try JSONDecoder().decode(SavedSession.self, from: data)
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
