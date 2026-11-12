import Darwin
import Foundation

/// Why a server is not running, with the output that explains it.
public nonisolated struct ServerFailure: Equatable, Sendable {
    public var summary: String
    public var recentOutput: [String]

    public init(summary: String, recentOutput: [String]) {
        self.summary = summary
        self.recentOutput = recentOutput
    }
}

public nonisolated enum ServerState: Equatable, Sendable {
    case stopped
    case starting
    case ready(ServerEndpoint)
    case stopping
    case failed(ServerFailure)
}

public nonisolated struct SupervisorPolicy: Sendable {
    /// From spawn to a 2xx. A first run after `uv tool install` compiles bytecode and
    /// has macOS scan seven native extensions, about 2 s in total (see the brief).
    public var startupTimeout: Duration = .seconds(60)
    /// `metab` sets uvicorn's graceful-shutdown timeout to 0, so SIGTERM returns fast.
    public var shutdownGrace: Duration = .seconds(5)
    /// Between readiness probes: short, since the socket listens moments after the
    /// announcement.
    public var probeInterval: Duration = .milliseconds(50)
    /// How long to let the output pipe drain after an exit, so the error view shows
    /// the child's last lines.
    public var outputSettle: Duration = .milliseconds(500)
    /// How long to wait for the exit after SIGKILL. A process in uninterruptible I/O
    /// (a hung network mount) ignores even SIGKILL until the I/O returns; quitting and
    /// logging out must not wait on it.
    public var killWait: Duration = .seconds(2)
    /// How long a start that ended early (the child exited, or closed its output) waits
    /// for the child's own exit before signaling it, so the failure reports the exit
    /// status the child chose.
    public var earlyExitWait: Duration = .seconds(1)
    /// How long a ready server has to answer before a window attaches to it. Measured on
    /// 2026-11-11 (a metab dev build, an Apple silicon Mac): `GET /view/` took 12 to 19 ms
    /// on a warm server, and at most 61 ms in the first 10 seconds of a server on
    /// `/usr/share` (15,730 files) with `/api/rollup` and `/api/recent` running. A server
    /// silent this long is hung, not busy.
    public var healthDeadline: Duration = .seconds(5)

    public init() {}
}

/// What a health check found.
public nonisolated enum HealthCheck: Equatable, Sendable {
    /// The server answered: attach to it here.
    case healthy(ServerEndpoint)
    /// The server is not ready: starting, stopping, stopped, failed, or it exited during
    /// the check. A window attaches once it is ready.
    case notReady
    /// The server did not answer in time, so it was stopped, and it has failed.
    case unresponsive
}

/// Owns one server child: start, readiness, and a bounded stop that leaves no orphan.
///
/// Every launch and stop bumps `generation`; work for an older generation sees the
/// mismatch and stops, which is how a stop during startup, a crash during a readiness
/// wait, and a retry cannot overwrite each other's state, and how a restart that finds a
/// newer stop when its old child is gone launches nothing. There is no automatic
/// restart: an unexpected exit is a failure the window shows with Retry.
///
/// Every child is ended by exactly one tracked termination (`retire`), whoever asks
/// for it: a stop, a restart, a newer launch, or a start that gave up. `stop()` waits
/// for all of them, and `childPIDs` lists their children until they are reaped, so no
/// path can drop a child it has not finished stopping.
public final class ServerSupervisor {
    public typealias ProcessFactory = (LaunchSpec) throws -> any ServerProcess
    public typealias ReadinessProbe = @Sendable (URL) async -> Bool

    public private(set) var state: ServerState = .stopped {
        didSet { if state != oldValue { onChange?(state) } }
    }
    public var onChange: ((ServerState) -> Void)?
    /// Lifecycle events for the server log.
    public var onEvent: ((String) -> Void)?

    /// What the next launch runs. `restart(using:)` replaces it.
    public private(set) var spec: LaunchSpec
    public let launch: any ServerLaunch
    private let policy: SupervisorPolicy
    private let gate: LaunchGate?
    private let makeProcess: ProcessFactory
    private let probe: ReadinessProbe
    private let clock = ContinuousClock()
    /// The current launch's child. A child leaves this only by being retired.
    private var process: (any ServerProcess)?
    private var generation = 0
    private var isShutDown = false
    private var terminations: [ObjectIdentifier: Termination] = [:]
    /// The health check in flight, which a check that starts meanwhile joins, and the
    /// generation it checks.
    private var healthCheck: (generation: Int, answer: Task<Bool, Never>)?
    /// How many callers are waiting on `healthCheck`, for tests that order checks.
    private(set) var healthCheckWaiters = 0

    private struct Termination {
        let child: any ServerProcess
        let task: Task<TerminationResult, Never>
    }

    private struct TerminationResult {
        var status: Int32?
        /// Whether the child was still running when it was signaled.
        var signaled: Bool
    }

    public init(
        spec: LaunchSpec,
        launch: any ServerLaunch,
        policy: SupervisorPolicy = SupervisorPolicy(),
        gate: LaunchGate? = nil,
        makeProcess: @escaping ProcessFactory = { try SpawnedProcess($0) },
        probe: @escaping ReadinessProbe = HTTPReadiness.probe
    ) {
        self.spec = spec
        self.launch = launch
        self.policy = policy
        self.gate = gate
        self.makeProcess = makeProcess
        self.probe = probe
    }

    /// The current child's pid, which is also its process group id.
    public var pid: pid_t? { process?.pid }

    /// Every child not yet reaped: the current one and any still being stopped. Each pid
    /// is also its process group id.
    public var childPIDs: [pid_t] {
        ([process].compactMap(\.self) + terminations.values.map(\.child))
            .filter { !$0.hasExited }
            .map(\.pid)
    }

    /// Starts a server unless one is starting, running, or stopping, or the supervisor has
    /// been shut down.
    public func start() async {
        guard !isShutDown else { return }
        switch state {
        case .stopped, .failed: await launchChild()
        case .starting, .ready, .stopping: return
        }
    }

    /// Stops whatever is running, then starts a fresh child, unless a stop, another
    /// restart, or a shutdown arrived while the old child was stopping: the newest request
    /// wins, so closing a folder's last window during a restart leaves nothing running.
    ///
    /// - Parameter newSpec: what to run from now on, such as the command of a runtime
    ///   chosen since the server started; nil runs the same command again.
    public func restart(using newSpec: LaunchSpec? = nil) async {
        let mine = await halt()
        guard mine == generation, !isShutDown else { return }
        if let newSpec { spec = newSpec }
        await launchChild()
    }

    /// Ends the current child and waits for every termination in flight, including one
    /// a failed start began. Safe in any state and from concurrent callers.
    public func stop() async {
        await halt()
    }

    /// Stops for good: like `stop()`, and no later `start()` or `restart()` launches a
    /// child, including one already waiting. A folder whose windows have all closed is
    /// shut down, never just stopped.
    public func shutDown() async {
        isShutDown = true
        await halt()
    }

    /// Whether the ready server still answers, asked before a window attaches to it: a
    /// live process is not a working server, since a hung one keeps its pid. The server
    /// gets `policy.healthDeadline` to answer its readiness URL with a 2xx. One that does
    /// not is stopped and fails, so every window of the folder shows why and offers
    /// Retry; nothing restarts by itself.
    ///
    /// Checks of one child do not overlap: a check that starts while another is in flight
    /// waits for that one's answer, so a probe that times out cannot stop a server that
    /// another probe just heard from.
    public func checkHealth() async -> HealthCheck {
        guard case .ready(let endpoint) = state, let child = process else { return .notReady }
        let current = generation
        let url = launch.readinessURL(for: endpoint)
        let answer: Task<Bool, Never>
        if let inFlight = healthCheck, inFlight.generation == current {
            answer = inFlight.answer
        } else {
            answer = probeForHealth(url, child: child)
            healthCheck = (current, answer)
        }
        healthCheckWaiters += 1
        let answered = await answer.value
        healthCheckWaiters -= 1
        if healthCheck?.answer == answer { healthCheck = nil }
        // An exit is reported by `childExited`, with its status; a stop, a restart, or
        // another check meanwhile has already decided what happens.
        guard current == generation, case .ready = state, !child.hasExited else { return .notReady }
        if answered { return .healthy(endpoint) }

        generation += 1
        let mine = generation
        process = nil
        let summary = "The server stopped answering: \(url.absoluteString) gave no 2xx within \(policy.healthDeadline)."
        event("\(summary) Stopping it.")
        _ = await retire(child).value
        guard mine == generation else { return .unresponsive }
        state = .failed(ServerFailure(summary: summary, recentOutput: child.recentOutput()))
        return .unresponsive
    }

    /// Probes `url` until it answers with a 2xx, the child exits, or the deadline passes.
    private func probeForHealth(_ url: URL, child: any ServerProcess) -> Task<Bool, Never> {
        let probe = self.probe
        let interval = policy.probeInterval
        let deadline = policy.healthDeadline
        return Task {
            await firstResult(within: deadline, of: [
                { @Sendable in
                    while !Task.isCancelled, !child.hasExited {
                        if await probe(url) { return true }
                        try? await Task.sleep(for: interval)  // cancelled: the deadline passed
                    }
                    return nil
                },
            ]) ?? false
        }
    }

    /// `stop()`, returning the generation it began, which a restart compares after the
    /// wait to see whether anything newer happened.
    @discardableResult
    private func halt() async -> Int {
        generation += 1
        let mine = generation
        if let child = process {
            process = nil
            retire(child)
        }
        if !terminations.isEmpty { state = .stopping }
        await awaitTerminations()
        if mine == generation { state = .stopped }
        return mine
    }

    private func launchChild() async {
        generation += 1
        let current = generation
        state = .starting
        // A child a superseded launch left behind is stopped before another starts,
        // which also frees its port for the next port walk.
        if let previous = process {
            process = nil
            retire(previous)
        }
        await awaitTerminations()
        guard current == generation, !isShutDown else { return }
        if let gate { await gate.acquire() }
        defer { gate?.release() }
        guard current == generation else { return }

        let started = clock.now
        // The first event follows the factory, which may prepare (and rotate) the log the
        // events are written to.
        let child: any ServerProcess
        do {
            child = try makeProcess(spec)
        } catch {
            let summary = "Could not start \(spec.executable): \(error)."
            event("could not start \(spec.commandLine): \(error)")
            state = .failed(ServerFailure(summary: summary, recentOutput: []))
            return
        }
        process = child
        event("started pid \(child.pid), the leader of its own process group: \(spec.commandLine)")
        // Exits before ready are this function's to report (the race below watches for
        // them); this task reports an exit after ready.
        Task { [weak self] in
            guard let status = await child.waitForExit() else { return }
            await self?.childExited(child, status: status, generation: current)
        }

        // The announcement, or the child's exit, or the deadline, whichever is first.
        let lines = child.lines
        let launch = self.launch
        let endpoint = await firstResult(within: policy.startupTimeout, of: [
            { @Sendable in
                for await line in lines {
                    if let found = launch.endpoint(announcedBy: line) { return found }
                }
                return nil
            },
            { @Sendable in
                _ = await child.waitForExit()
                return nil
            },
        ])
        guard current == generation else { return superseded(child) }
        guard let endpoint else {
            let timedOut = started.duration(to: clock.now) >= policy.startupTimeout
            await abandon(child, timedOut: timedOut, waitingFor: "announce its address")
            return
        }
        event("announced \(endpoint.entryURL.absoluteString)")

        // The announcement prints before the socket listens.
        let url = launch.readinessURL(for: endpoint)
        let deadline = started.advanced(by: policy.startupTimeout)
        while current == generation, clock.now < deadline, !child.hasExited {
            if await probe(url) {
                guard current == generation, !child.hasExited else { break }
                let elapsed = Self.milliseconds(started.duration(to: clock.now))
                event("ready: \(url.absoluteString) answered 2xx, \(elapsed) ms after spawn")
                state = .ready(endpoint)
                return
            }
            try? await clock.sleep(for: policy.probeInterval)
        }
        guard current == generation else { return superseded(child) }
        await abandon(
            child, timedOut: !child.hasExited, waitingFor: "answer \(url.absoluteString) with a 2xx")
    }

    /// A launch overtaken after it spawned ends its own child, unless whatever overtook
    /// it already did (every path that bumps the generation retires the current child).
    private func superseded(_ child: any ServerProcess) {
        guard process === child else { return }
        process = nil
        retire(child)
    }

    /// Ends a start that never became ready. A child that exited by itself is reported
    /// with its status; one that is still running is stopped. Either way the ending is
    /// a tracked termination, so a stop or quit meanwhile waits for it.
    private func abandon(_ child: any ServerProcess, timedOut: Bool, waitingFor what: String) async {
        generation += 1  // this exit is expected now; childExited must not report it
        let mine = generation
        if process === child { process = nil }
        let result = await retire(child, allowingNaturalExitFor: timedOut ? .zero : policy.earlyExitWait).value
        let summary: String
        if timedOut {
            summary = "The server did not \(what) within \(policy.startupTimeout)."
        } else if !result.signaled, let status = result.status {
            summary = "The server exited before it was ready (\(ExitStatus(waitStatus: status)))."
        } else {
            summary = "The server closed its output before it was ready."
        }
        event(summary)
        guard mine == generation else { return }
        state = .failed(ServerFailure(summary: summary, recentOutput: child.recentOutput()))
    }

    private func childExited(_ child: any ServerProcess, status: Int32, generation exited: Int) async {
        // A stop or an abandoned start asked for this exit, or the start is still in
        // progress and will report it itself.
        guard exited == generation, case .ready = state else { return }
        generation += 1
        let mine = generation
        process = nil
        _ = await retire(child).value  // already exited: sweeps its group and drains output
        let summary = "The server stopped unexpectedly (\(ExitStatus(waitStatus: status)))."
        event(summary)
        guard mine == generation else { return }
        state = .failed(ServerFailure(summary: summary, recentOutput: child.recentOutput()))
    }

    /// Starts the one termination of `child`, or returns the one already running.
    @discardableResult
    private func retire(
        _ child: any ServerProcess, allowingNaturalExitFor wait: Duration = .zero
    ) -> Task<TerminationResult, Never> {
        let id = ObjectIdentifier(child)
        if let running = terminations[id] { return running.task }
        let task = Task {
            let result = await self.terminate(child, allowingNaturalExitFor: wait)
            self.terminations[id] = nil
            return result
        }
        terminations[id] = Termination(child: child, task: task)
        return task
    }

    private func awaitTerminations() async {
        while let next = terminations.values.first {
            _ = await next.task.value
        }
    }

    /// SIGTERM to the process group, a bounded wait, SIGKILL, another bounded wait,
    /// and a final SIGKILL to anything left in the group.
    private func terminate(
        _ child: any ServerProcess, allowingNaturalExitFor wait: Duration
    ) async -> TerminationResult {
        var status: Int32?
        if wait > .zero {
            status = await firstResult(within: wait, of: [{ @Sendable in await child.waitForExit() }])
        }
        var signaled = false
        if status == nil, child.hasExited {
            status = await child.waitForExit()  // resolved already
        } else if status == nil {
            signaled = true
            event("stopping pid \(child.pid): SIGTERM to its process group")
            child.signalGroup(SIGTERM)
            status = await firstResult(within: policy.shutdownGrace, of: [{ @Sendable in await child.waitForExit() }])
            if status == nil {
                event("pid \(child.pid) still running after \(policy.shutdownGrace): SIGKILL to its process group")
                child.signalGroup(SIGKILL)
                status = await firstResult(within: policy.killWait, of: [{ @Sendable in await child.waitForExit() }])
                if status == nil {
                    event("pid \(child.pid) did not exit within \(policy.killWait) of SIGKILL (uninterruptible I/O?); giving up on it")
                }
            }
        }
        // Anything still in its group after the leader exited. The exited leader is not
        // reaped until `release()`, so its pid, and the group id, are still this child's.
        child.signalGroup(SIGKILL)
        await settleOutput(child)
        child.release()  // the last thing this child is sent; reaped once it has exited
        if let status { event("pid \(child.pid) stopped (\(ExitStatus(waitStatus: status)))") }
        return TerminationResult(status: status, signaled: signaled)
    }

    private func settleOutput(_ child: any ServerProcess) async {
        _ = await firstResult(within: policy.outputSettle, of: [{ @Sendable in await child.waitForOutputEnd() }])
    }

    private func event(_ message: String) {
        onEvent?(message)
    }

    private static func milliseconds(_ duration: Duration) -> Int {
        Int((duration / .milliseconds(1)).rounded())
    }
}
