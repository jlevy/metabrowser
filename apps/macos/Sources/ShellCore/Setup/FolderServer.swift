/// A folder's server, started only from the runtime the app accepts at the moment it
/// spawns.
///
/// Every way a server starts goes through here: a folder's first start, a restored
/// folder's start when its turn or its tab comes, Retry, Restart Server, and the restart
/// an upgrade offers. Each asks `accepted` twice: before it stops anything, and again at
/// the last moment before the child spawns, after the launch gate and any earlier
/// child's termination (`ServerSupervisor.mayLaunch`), beside a restore's `rootCheck`.
/// The second answer must be the runtime the command was built from; a runtime replaced
/// meanwhile is taken up and tried once more, and with none, nothing spawns. A request
/// the user made is then held, and `resume()` carries it out once a runtime is accepted;
/// a restore's is not, since its queue keeps the root (`RestoreQueue.putBack`).
public final class FolderServer {
    public enum Request: Equatable, Sendable {
        case start
        case restart
    }

    /// How a start or restart ended.
    public enum Outcome: Equatable, Sendable {
        /// It spawned, or a server was already starting or running, or a newer request
        /// took its place.
        case launched
        /// No runtime was accepted, before it stopped anything or at the moment of
        /// spawning.
        case waitingForRuntime
        /// `rootCheck` refused it at the moment of spawning.
        case refusedByRoot
    }

    public let supervisor: ServerSupervisor
    /// The runtime the server last spawned a child from; nil until a child is first
    /// created, as for a restored folder still waiting for its turn or its tab, or one whose
    /// child could not be created. Set when the supervisor reports the child created
    /// (`ServerSupervisor.onSpawn`).
    public private(set) var startedRuntime: Runtime?
    /// What waits for an accepted runtime.
    public private(set) var held: Request?
    /// For a restored background folder, its root admitted again at the moment of
    /// spawning; nil once one of its tabs is selected, which starts it as the user's choice.
    public var rootCheck: (() -> Bool)?
    private let accepted: () -> RuntimeSetup?
    private let spec: (RuntimeSetup) -> LaunchSpec
    /// The runtime the newest launch's command was built from, with its number.
    private var launching: (attempt: Int, setup: RuntimeSetup)?
    private var attempts = 0
    /// Why the check at the moment of spawning refused a launch, by its number.
    private var refusal: (attempt: Int, outcome: Outcome)?
    /// The runtime the check at the moment of spawning let through, which becomes
    /// `startedRuntime` once the child is created.
    private var approved: Runtime?

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
        supervisor.mayLaunch = { [weak self] in self?.mayLaunchNow() ?? false }
        supervisor.onSpawn = { [weak self] in self?.spawned() }
    }

    /// Whether a runtime is accepted now.
    public var isRuntimeAccepted: Bool { accepted() != nil }

    /// Starts the server unless one is starting, running, or stopping, and returns once
    /// that start is ready or has failed, or did not spawn.
    ///
    /// - Parameter holding: whether a start that found no runtime waits in `held` for
    ///   `resume()`; a restore passes false and keeps the root in its own queue.
    @discardableResult
    public func start(holding: Bool = true) async -> Outcome {
        switch supervisor.state {
        case .starting, .ready, .stopping: return .launched
        case .stopped, .failed: break
        }
        guard let setup = accepted() else { return waiting(.start, holding: holding) }
        let outcome = await launch(setup) { await self.supervisor.start(using: $0) }
        return outcome == .waitingForRuntime ? waiting(.start, holding: holding) : outcome
    }

    /// Stops the server and starts a fresh one from the runtime accepted now, which may
    /// not be the one it started with. With none, it stops nothing and holds the restart;
    /// with one rejected while the old server stopped, it spawns nothing and holds it.
    @discardableResult
    public func restart() async -> Outcome {
        guard let setup = accepted() else { return waiting(.restart, holding: true) }
        let outcome = await launch(setup) { await self.supervisor.restart(using: $0) }
        return outcome == .waitingForRuntime ? waiting(.restart, holding: true) : outcome
    }

    /// Carries out the held start or restart, if a runtime is accepted now, and returns how
    /// it ended; nil if nothing was held.
    @discardableResult
    public func resume() async -> Outcome? {
        switch held {
        case .start: await start()
        case .restart: await restart()
        case nil: nil
        }
    }

    /// Runs `run` with `setup`'s command, and again with the runtime accepted when the
    /// check at the moment of spawning refused the one it was built from, if there is one.
    private func launch(_ first: RuntimeSetup, _ run: (LaunchSpec) async -> Void) async -> Outcome {
        var setup = first
        while true {
            attempts += 1
            let attempt = attempts
            launching = (attempt, setup)
            await run(spec(setup))
            if launching?.attempt == attempt { launching = nil }
            guard let refused = refusal, refused.attempt == attempt else { return .launched }
            guard refused.outcome == .waitingForRuntime, let now = accepted() else { return refused.outcome }
            setup = now  // replaced while it waited: the command is built again from the new one
        }
    }

    /// The check the supervisor makes just before a child spawns.
    private func mayLaunchNow() -> Bool {
        guard let launching else { return false }
        guard accepted() == launching.setup else {
            refusal = (launching.attempt, .waitingForRuntime)
            return false
        }
        if let rootCheck, !rootCheck() {
            refusal = (launching.attempt, .refusedByRoot)
            return false
        }
        approved = launching.setup.runtime
        held = nil  // whatever was held is what spawns now
        return true
    }

    /// The child was created: until now, `startedRuntime` still names the one before, so a
    /// process factory that throws leaves it as it was.
    private func spawned() {
        if let approved { startedRuntime = approved }
        approved = nil
    }

    private func waiting(_ request: Request, holding: Bool) -> Outcome {
        if holding { held = request }
        return .waitingForRuntime
    }
}
