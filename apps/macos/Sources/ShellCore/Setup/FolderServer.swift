/// A folder's server, started only from the runtime the app accepts at that moment.
///
/// Every way a server starts goes through here: a folder's first start, a restored
/// folder's start when its turn or its tab comes, Retry, Restart Server, and the restart
/// an upgrade offers. Each asks `accepted` when it would launch, never the runtime the
/// folder was opened with, so a runtime rejected or unverified since starts nothing.
/// Without one the request is held, a running server keeps running, and `resume()`
/// carries the request out once a runtime is accepted.
public final class FolderServer {
    public enum Request: Equatable, Sendable {
        case start
        case restart
    }

    public let supervisor: ServerSupervisor
    /// The runtime the server last started from; nil until it first starts, as for a
    /// restored folder still waiting for its turn or its tab.
    public private(set) var startedRuntime: Runtime?
    /// What waits for an accepted runtime.
    public private(set) var held: Request?
    private let accepted: () -> RuntimeSetup?
    private let spec: (RuntimeSetup) -> LaunchSpec

    /// - Parameters:
    ///   - accepted: the runtime a server may start from now, or nil.
    ///   - spec: the command that serves the folder with a runtime.
    public init(
        supervisor: ServerSupervisor, accepted: @escaping () -> RuntimeSetup?,
        spec: @escaping (RuntimeSetup) -> LaunchSpec
    ) {
        self.supervisor = supervisor
        self.accepted = accepted
        self.spec = spec
    }

    /// Starts the server unless one is starting, running, or stopping, and returns once
    /// that start is ready or has failed. Returns false if it held the start instead.
    @discardableResult
    public func start() async -> Bool {
        switch supervisor.state {
        case .starting, .ready, .stopping: return true
        case .stopped, .failed: break
        }
        guard let setup = accepted() else {
            if held == nil { held = .start }
            return false
        }
        held = nil
        startedRuntime = setup.runtime
        await supervisor.start(using: spec(setup))
        return true
    }

    /// Stops the server and starts a fresh one from the runtime accepted now, which may
    /// not be the one it started with. Returns false if it held the restart instead,
    /// stopping nothing.
    @discardableResult
    public func restart() async -> Bool {
        guard let setup = accepted() else {
            held = .restart
            return false
        }
        held = nil
        startedRuntime = setup.runtime
        await supervisor.restart(using: spec(setup))
        return true
    }

    /// Carries out the held start or restart, if a runtime is accepted now.
    public func resume() async {
        switch held {
        case .start: await start()
        case .restart: await restart()
        case nil: return
        }
    }
}
