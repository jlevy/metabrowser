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
/// waits for its tab. A selected root starts as the user's choice, without the check. A
/// root that finds no runtime goes back to the front of the queue and the restore pauses
/// until `runtimeAccepted()`, so each root is still admitted again in its turn, in order,
/// with selected tabs first.
///
/// The app (`FolderWindows`) owns one per restore, runs `start()` in a task, and shows
/// and logs what `onEvent` reports.
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
    }

    public private(set) var queue: RestoreQueue
    public var onEvent: (Event) -> Void = { _ in }
    private let folder: (String) -> (any RestoredFolder)?
    private let admit: (String) -> RootAdmission
    private var isRunning = false
    private var isWaitingForRuntime = false

    /// - Parameters:
    ///   - folder: the open session of a root, by its path.
    ///   - admit: a background root's admission now (`RootAdmission.admit`).
    public init(
        _ queue: RestoreQueue, folder: @escaping (String) -> (any RestoredFolder)?,
        admit: @escaping (String) -> RootAdmission
    ) {
        self.queue = queue
        self.folder = folder
        self.admit = admit
    }

    /// Starts the queue's roots one at a time until none is left to start or the restore
    /// waits for a runtime. A call while a run is going returns at once: that run picks up
    /// whatever changed.
    public func start() async {
        guard !isRunning else { return }
        isRunning = true
        defer { isRunning = false }
        while !isWaitingForRuntime, let path = next() {
            guard let session = folder(path) else { continue }
            switch await session.startRestored() {
            case .launched:
                queue.finish(path)
            case .refusedByRoot:
                queue.hold(path)
                onEvent(.changedWhileWaiting(path))
            case .waitingForRuntime:
                queue.putBack(path)
                // A runtime accepted since the refusal starts it at once.
                guard !session.isRuntimeAccepted else { continue }
                isWaitingForRuntime = true
                onEvent(.waitingForRuntime(queue.pending))
            }
        }
    }

    /// A tab of `path` was selected: it starts as the user's choice, even if it is already
    /// waiting at the launch gate, and next if it is waiting to start. Returns whether it
    /// waits to start, so a run must go on.
    @discardableResult
    public func select(_ path: String) -> Bool {
        folder(path)?.launchCheck = nil
        return queue.select(path)
    }

    /// Every tab of `path` closed.
    public func folderClosed(_ path: String) {
        queue.remove(path)
    }

    /// A restored background folder's restart, such as one after an upgrade, was refused
    /// by its root check: its server stays stopped until one of its tabs is selected,
    /// which starts it through the queue as the user's choice.
    public func rootRefused(_ path: String) {
        queue.hold(path)
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
    /// tab. A selected root is not checked.
    private func next() -> String? {
        let admit = self.admit
        let waiting = Set(queue.deferred)
        let next = queue.next { admit($0) == .open($0) }
        for path in queue.deferred where !waiting.contains(path) {
            onEvent(.changedBeforeItsTurn(path))
        }
        if let next, let session = folder(next) {
            session.launchCheck = queue.selected.contains(next) ? nil : { admit(next) == .open(next) }
        }
        return next
    }
}
