import Foundation

/// A restored folder's session as the restore starts it: `FolderSession` in the app.
public protocol RestoredFolder: AnyObject {
    /// The root check made just before its server spawns (`FolderServer.rootCheck`); nil
    /// starts it as the user's choice.
    var launchCheck: (() -> Bool)? { get set }
    /// Whether a runtime is accepted now.
    var isRuntimeAccepted: Bool { get }
    /// Starts its server without holding the start for a runtime, and returns once that
    /// start is ready or has failed, or did not spawn (`FolderServer.start(holding:)`).
    func startRestored() async -> FolderServer.Outcome
}

/// The restored session's servers, started one at a time in `RestoreQueue`'s order, each
/// after the one before it is ready or has failed.
///
/// A background root is admitted again when its turn comes, and once more just before
/// its server spawns (`RestoredFolder.launchCheck`), since it can change while the roots
/// before it start and while it waits at the launch gate; one that no longer is admitted
/// waits for its tab. A selected root starts as the user's choice, without that check,
/// but its saved path is resolved first (`RootActivation`): one that now leads to another
/// folder moves its tabs to that folder's session, the open one or a new one, and that
/// folder starts in its place, so a folder keeps one session and one server however its
/// tabs were saved (`RestoreQueue.redirect`). Its check from then on, for this start and
/// every later restart, is that its saved path still names its own folder: a start that
/// finds otherwise spawns nothing, and the root is resolved again as the user's choice,
/// at its turn (`start`) or, for a later restart, at once (`rootRefused`). A root that
/// finds no runtime goes back to
/// the front of the queue and the restore pauses until `runtimeAccepted()`, so each root
/// is still admitted again in its turn, in order, with selected tabs first.
///
/// The app (`FolderWindows`) owns one per restore, runs `start()` in a task, moves the
/// tabs, and shows and logs what `onEvent` reports.
public final class RestoreRun {
    /// What the windows of a root show, and the log says, because of the restore.
    public enum Event: Equatable, Sendable {
        /// A background root changed since the launch admitted it, found when its turn
        /// came: it starts when one of its tabs is selected.
        case changedBeforeItsTurn(String)
        /// A background root changed while it waited to start, found just before its
        /// server would spawn: it starts when one of its tabs is selected.
        case changedWhileWaiting(String)
        /// A root found no runtime to start from: the restore waits for one, with these
        /// roots still to start.
        case waitingForRuntime([String])
        /// A selected root's saved path now leads to another folder: its tabs show that
        /// folder now.
        case moved(String, to: String)
    }

    public private(set) var queue: RestoreQueue
    public var onEvent: (Event) -> Void = { _ in }
    private let folder: (String) -> (any RestoredFolder)?
    private let admit: (String) -> RootAdmission
    private let resolve: (String) -> String?
    private let moveTabs: (String, String) -> Bool
    private var isRunning = false
    private var isWaitingForRuntime = false

    /// - Parameters:
    ///   - folder: the open session of a root, by its path.
    ///   - admit: a background root's admission now (`RootAdmission.admit`).
    ///   - resolve: the other folder a selected root's saved path leads to now, or nil to
    ///     start it as saved (`RootActivation.resolve`).
    ///   - moveTabs: moves every tab of the first root to the session of the second, the
    ///     open one or else a new one; false if no session can be made for it now, as
    ///     without a runtime, which leaves the tabs where they are.
    public init(
        _ queue: RestoreQueue, folder: @escaping (String) -> (any RestoredFolder)?,
        admit: @escaping (String) -> RootAdmission,
        resolve: @escaping (String) -> String? = { RootActivation.resolve($0) },
        moveTabs: @escaping (String, String) -> Bool
    ) {
        self.queue = queue
        self.folder = folder
        self.admit = admit
        self.resolve = resolve
        self.moveTabs = moveTabs
    }

    /// Starts the queue's roots one at a time until none is left to start or the restore
    /// waits for a runtime. A call while a run is going returns at once: that run picks up
    /// whatever changed.
    public func start() async {
        guard !isRunning else { return }
        isRunning = true
        defer { isRunning = false }
        while !isWaitingForRuntime, let path = next() {
            if queue.selected.contains(path), let canonical = resolve(path), canonical != path {
                let isOpen = folder(canonical) != nil
                guard moveTabs(path, canonical) else {
                    queue.putBack(path)
                    waitForRuntime()
                    continue
                }
                queue.redirect(path, to: canonical, isOpen: isOpen)
                // Its tabs, shown by the user's choice, now show that folder.
                if queue.selected.contains(canonical) { folder(canonical)?.launchCheck = namesItself(canonical) }
                onEvent(.moved(path, to: canonical))
                continue
            }
            guard let session = folder(path) else { continue }
            switch await session.startRestored() {
            case .launched:
                queue.finish(path)
            case .refusedByRoot where queue.selected.contains(path):
                // Selected, and its path led to another folder when it would have spawned,
                // as when its tab is selected while it waits at the gate: it is next again,
                // as the user's choice, and resolved like any selected start, so its tabs
                // move before anything spawns.
                queue.putBack(path)
            case .refusedByRoot:
                queue.hold(path)
                onEvent(.changedWhileWaiting(path))
            case .waitingForRuntime:
                queue.putBack(path)
                // A runtime accepted since the refusal starts it at once.
                guard !session.isRuntimeAccepted else { continue }
                waitForRuntime()
            }
        }
    }

    private func waitForRuntime() {
        isWaitingForRuntime = true
        onEvent(.waitingForRuntime(queue.pending))
    }

    /// A tab of `path` was selected: it starts as the user's choice, next if it is waiting
    /// to start. Returns whether it waits to start, so a run must go on.
    ///
    /// Its background check gives way to the check every selected root keeps, made at the
    /// moment of spawning: that its saved path still names its own folder. That covers a
    /// start already waiting at the launch gate, which was handed out before it was
    /// selected and so was not resolved, and every later restart. A folder not part of
    /// the restore is left unchecked.
    @discardableResult
    public func select(_ path: String) -> Bool {
        let waits = queue.select(path)
        folder(path)?.launchCheck = queue.selected.contains(path) ? namesItself(path) : nil
        return waits
    }

    /// The check of a selected root: its saved path still names its own folder, or
    /// nothing that can be served, which its server then reports (`RootActivation`).
    private func namesItself(_ path: String) -> () -> Bool {
        let resolve = self.resolve
        return { resolve(path) == nil }
    }

    /// Every tab of `path` closed.
    public func folderClosed(_ path: String) {
        queue.remove(path)
    }

    /// A restored folder's restart, such as Restart Server or the one after an upgrade, was
    /// refused by its root check. A background one's server stays stopped until one of its
    /// tabs is selected, which starts it through the queue as the user's choice. A selected
    /// one's saved path now leads to another folder: it starts next as the user's choice,
    /// resolved, so its tabs move to that folder's session, which starts in its place.
    /// Returns whether a run must go on.
    @discardableResult
    public func rootRefused(_ path: String) -> Bool {
        guard queue.selected.contains(path) else {
            queue.hold(path)
            return false
        }
        queue.requeue(path)
        return true
    }

    /// A runtime was accepted. Returns whether the restore was waiting for one, so a run
    /// must go on.
    public func runtimeAccepted() -> Bool {
        guard isWaitingForRuntime else { return false }
        isWaitingForRuntime = false
        return true
    }

    /// The next root to start. A background root is admitted again now and gets the check
    /// made just before its server spawns; one that no longer is admitted waits for its
    /// tab. A selected root gets the check that its saved path still names its folder.
    private func next() -> String? {
        let admit = self.admit
        let waiting = Set(queue.deferred)
        let next = queue.next { admit($0) == .open($0) }
        for path in queue.deferred where !waiting.contains(path) {
            onEvent(.changedBeforeItsTurn(path))
        }
        if let next, let session = folder(next) {
            session.launchCheck = queue.selected.contains(next) ? namesItself(next) : { admit(next) == .open(next) }
        }
        return next
    }
}

/// Where a restored root's saved path leads once one of its tabs is selected.
///
/// A launch admits a saved root without following a link (`RootAdmission`), so a root
/// with a link on its path waits under the spelling it was saved with. Selecting one of
/// its tabs is the user's choice, so the path is resolved then, as `metab` and every
/// other way of opening a folder resolve it (`FileChecks.canonicalPath`), and a path that
/// now leads to another folder takes that folder's identity: its tabs share that
/// folder's session and server, and the server is started with the folder's own path.
public nonisolated enum RootActivation {
    /// The other folder `saved` leads to now, or nil to start `saved` as it is: it still
    /// names its folder, or leads to nothing that can be served as a folder (gone, a file,
    /// a path with a line break), which its server then reports, as before.
    public static func resolve(
        _ saved: String, canonicalPath: (String) -> String = FileChecks.canonicalPath,
        isFolder: (String) -> Bool = FileChecks.isDirectory
    ) -> String? {
        let resolved = canonicalPath(saved)
        guard resolved != saved, resolved.hasPrefix("/"), isFolder(resolved),
              CLIServeLaunch.unservableReason(URL(filePath: resolved, directoryHint: .isDirectory)) == nil
        else { return nil }
        return resolved
    }
}
