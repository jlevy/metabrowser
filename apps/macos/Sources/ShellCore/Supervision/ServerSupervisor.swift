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
    public var probeInterval: Duration = .milliseconds(50)
    /// How long to let the output pipe drain after an exit, so the error view shows
    /// the child's last lines.
    public var outputSettle: Duration = .milliseconds(500)

    public init() {}
}

/// Owns one server child: start, readiness, and a bounded stop that leaves no orphan.
///
/// Every launch and stop bumps `generation`; a callback from an older child sees the
/// mismatch and does nothing, which is how a stop during startup, a crash during a
/// readiness wait, and a retry cannot overwrite each other's state. There is no
/// automatic restart: an unexpected exit is a failure the window shows with Retry.
public final class ServerSupervisor {
    public typealias ProcessFactory = (LaunchSpec) throws -> any ServerProcess
    public typealias ReadinessProbe = @Sendable (URL) async -> Bool

    public private(set) var state: ServerState = .stopped {
        didSet { if state != oldValue { onChange?(state) } }
    }
    public var onChange: ((ServerState) -> Void)?
    /// Lifecycle events for the server log.
    public var onEvent: ((String) -> Void)?

    public let spec: LaunchSpec
    public let launch: any ServerLaunch
    private let policy: SupervisorPolicy
    private let gate: LaunchGate?
    private let makeProcess: ProcessFactory
    private let probe: ReadinessProbe
    private let clock = ContinuousClock()
    private var process: (any ServerProcess)?
    private var generation = 0
    private var stopping: Task<Void, Never>?

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

    /// The running child's pid, which is also its process group id.
    public var pid: pid_t? { process?.pid }

    /// Starts a server unless one is starting, running, or stopping.
    public func start() async {
        switch state {
        case .stopped, .failed: await launchChild()
        case .starting, .ready, .stopping: return
        }
    }

    /// Stops whatever is running, then starts a fresh child.
    public func restart() async {
        await stop()
        await launchChild()
    }

    /// SIGTERM to the process group, a bounded wait, then SIGKILL. Safe in any state,
    /// and concurrent callers all wait for the same stop.
    public func stop() async {
        generation += 1
        let mine = generation
        if let stopping {
            await stopping.value
        } else if let child = process {
            process = nil
            state = .stopping
            let task = Task { _ = await self.terminate(child) }
            stopping = task
            await task.value
            stopping = nil
        }
        if mine == generation { state = .stopped }
    }

    private func launchChild() async {
        generation += 1
        let current = generation
        state = .starting
        if let gate { await gate.acquire() }
        defer { gate?.release() }
        guard current == generation else { return }

        let started = clock.now
        event("starting: \(spec.commandLine)")
        let child: any ServerProcess
        do {
            child = try makeProcess(spec)
        } catch {
            let summary = "Could not start \(spec.executable): \(error)."
            event(summary)
            state = .failed(ServerFailure(summary: summary, recentOutput: []))
            return
        }
        process = child
        event("started pid \(child.pid) as the leader of its own process group")
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
        guard current == generation else { return }
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
        guard current == generation else { return }
        await abandon(
            child, timedOut: !child.hasExited, waitingFor: "answer \(url.absoluteString) with a 2xx")
    }

    /// Ends a start that never became ready. A child that exited by itself is reported
    /// with its status; one that is still running is stopped.
    private func abandon(_ child: any ServerProcess, timedOut: Bool, waitingFor what: String) async {
        generation += 1  // this exit is expected now; childExited must not report it
        let mine = generation
        process = nil
        let exited: Int32? =
            timedOut ? nil : await firstResult(within: .seconds(1), of: [{ @Sendable in await child.waitForExit() }])
        let summary: String
        if let exited {
            summary = "The server exited before it was ready (\(ExitStatus(waitStatus: exited)))."
            child.signalGroup(SIGKILL)  // anything it left in its group
            await settleOutput(child)
        } else {
            summary = "The server did not \(what) within \(policy.startupTimeout)."
            await terminate(child)
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
        child.signalGroup(SIGKILL)  // anything it left in its group
        await settleOutput(child)
        let summary = "The server stopped unexpectedly (\(ExitStatus(waitStatus: status)))."
        event(summary)
        guard mine == generation else { return }
        state = .failed(ServerFailure(summary: summary, recentOutput: child.recentOutput()))
    }

    @discardableResult
    private func terminate(_ child: any ServerProcess) async -> Int32? {
        event("stopping pid \(child.pid): SIGTERM to its process group")
        child.signalGroup(SIGTERM)
        var status = await firstResult(within: policy.shutdownGrace, of: [{ @Sendable in await child.waitForExit() }])
        if status == nil {
            event("pid \(child.pid) still running after \(policy.shutdownGrace): SIGKILL to its process group")
            child.signalGroup(SIGKILL)
            status = await child.waitForExit()
        }
        child.signalGroup(SIGKILL)  // anything still in its group after the leader exited
        await settleOutput(child)
        if let status { event("pid \(child.pid) stopped (\(ExitStatus(waitStatus: status)))") }
        return status
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
