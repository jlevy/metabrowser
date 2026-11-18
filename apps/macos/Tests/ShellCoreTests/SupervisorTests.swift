import Darwin
import Foundation
import Testing
@testable import ShellCore

private let servingLine = "Serving /tmp/root at http://127.0.0.1:8412/view/"
private let endpoint = ServerEndpoint(
    origin: URL(string: "http://127.0.0.1:8412")!, entryURL: URL(string: "http://127.0.0.1:8412/view/")!)
private let spec = LaunchSpec(executable: "/usr/bin/false")

private func fastPolicy(startup: Duration = startupCeiling) -> SupervisorPolicy {
    var policy = SupervisorPolicy()
    policy.startupTimeout = startup
    policy.shutdownGrace = .milliseconds(100)
    policy.probeInterval = .milliseconds(5)
    policy.outputSettle = .milliseconds(50)
    return policy
}

private func supervisor(
    _ child: FakeProcess, policy: SupervisorPolicy = fastPolicy(),
    probe: @escaping ServerSupervisor.ReadinessProbe = { _ in true }
) -> ServerSupervisor {
    ServerSupervisor(spec: spec, launch: CLIServeLaunch(), policy: policy, makeProcess: { _ in child }, probe: probe)
}

@Suite struct SupervisorTests {
    @Test func servingLineThenTwoXXMeansReady() async {
        let child = FakeProcess()
        let probed = Recorder<URL>()
        let subject = supervisor(child, probe: { url in
            probed.append(url)
            return true
        })
        child.say("Loading plugins")
        child.say(servingLine)
        await subject.start()
        #expect(subject.state == .ready(endpoint))
        #expect(probed.all == [endpoint.entryURL])
        #expect(subject.pid == 4242)
    }

    @Test func readinessPollsUntilTheServerAnswers() async {
        let child = FakeProcess()
        let probes = Recorder<URL>()
        let subject = supervisor(child, probe: { url in
            probes.append(url)
            return probes.count >= 4  // refused three times: announced, not yet listening
        })
        child.say(servingLine)
        await subject.start()
        #expect(subject.state == .ready(endpoint))
        #expect(probes.count == 4)
    }

    @Test func childThatExitsBeforeAnnouncingFailsWithItsOutput() async {
        let child = FakeProcess()
        let subject = supervisor(child)
        child.say("Error: ROOT does not exist")
        child.exitOnItsOwn(code: 2)
        await subject.start()
        guard case .failed(let failure) = subject.state else {
            Issue.record("expected a failure, got \(subject.state)")
            return
        }
        #expect(failure.summary.contains("exited before it was ready"))
        #expect(failure.summary.contains("exit status 2"))
        #expect(failure.recentOutput == ["Error: ROOT does not exist"])
    }

    @Test func silentChildTimesOutAndIsStopped() async {
        let child = FakeProcess()
        let subject = supervisor(child, policy: fastPolicy(startup: .milliseconds(200)))
        child.say("still importing")
        await subject.start()
        guard case .failed(let failure) = subject.state else {
            Issue.record("expected a failure, got \(subject.state)")
            return
        }
        #expect(failure.summary.contains("did not announce its address"))
        #expect(failure.recentOutput == ["still importing"])
        #expect(child.exitedBy == SIGTERM)
    }

    @Test func announcedServerThatNeverAnswersTimesOut() async {
        let child = FakeProcess()
        let subject = supervisor(child, policy: fastPolicy(startup: .milliseconds(200)), probe: { _ in false })
        child.say(servingLine)
        await subject.start()
        guard case .failed(let failure) = subject.state else {
            Issue.record("expected a failure, got \(subject.state)")
            return
        }
        #expect(failure.summary.contains("did not answer http://127.0.0.1:8412/view/ with a 2xx"))
        #expect(child.exitedBy == SIGTERM)
    }

    @Test func stopEndsAGracefulChildWithTerm() async {
        let child = FakeProcess()
        let subject = supervisor(child)
        child.say(servingLine)
        await subject.start()
        await subject.stop()
        #expect(subject.state == .stopped)
        #expect(child.exitedBy == SIGTERM)
        #expect(child.signals.first == SIGTERM)
        #expect(subject.pid == nil)
    }

    @Test func stopEscalatesToKillWhenTermIsIgnored() async {
        let child = FakeProcess(ignoresTerm: true)
        let subject = supervisor(child)
        child.say(servingLine)
        await subject.start()
        await subject.stop()
        #expect(subject.state == .stopped)
        #expect(Array(child.signals.prefix(2)) == [SIGTERM, SIGKILL])
        #expect(child.exitedBy == SIGKILL)
    }

    @Test func unexpectedExitAfterReadyIsAFailureNotARestart() async {
        let spawned = Recorder<Int>()
        let child = FakeProcess()
        let subject = ServerSupervisor(
            spec: spec, launch: CLIServeLaunch(), policy: fastPolicy(),
            makeProcess: { _ in
                spawned.append(1)
                return child
            }, probe: { _ in true })
        var states: [ServerState] = []
        subject.onChange = { states.append($0) }
        child.say(servingLine)
        await subject.start()
        child.say("Traceback: boom")
        child.exitOnItsOwn(code: 1)
        #expect(await eventually { if case .failed = subject.state { true } else { false } })
        guard case .failed(let failure) = subject.state else { return }
        #expect(failure.summary.contains("stopped unexpectedly (exit status 1)"))
        #expect(failure.recentOutput.last == "Traceback: boom")
        #expect(spawned.count == 1)
        #expect(states.first == .starting)
        #expect(states.dropFirst().first == .ready(endpoint))
    }

    @Test func retryAfterFailureStartsAFreshChild() async {
        let children = [FakeProcess(pid: 1), FakeProcess(pid: 2)]
        let spawned = Recorder<Int>()
        let subject = ServerSupervisor(
            spec: spec, launch: CLIServeLaunch(), policy: fastPolicy(),
            makeProcess: { _ in
                let child = children[spawned.count]
                spawned.append(1)
                return child
            }, probe: { _ in true })
        children[0].exitOnItsOwn(code: 1)
        await subject.start()
        guard case .failed = subject.state else {
            Issue.record("expected a failure, got \(subject.state)")
            return
        }
        children[1].say(servingLine)
        await subject.start()
        #expect(subject.state == .ready(endpoint))
        #expect(subject.pid == 2)
    }

    @Test func stopDuringStartupWinsOverALateAnnouncement() async {
        let child = FakeProcess()
        let subject = supervisor(child)
        let starting = Task { await subject.start() }
        #expect(await eventually { subject.pid != nil })
        await subject.stop()
        child.say(servingLine)  // too late: the child is already gone
        await starting.value
        #expect(subject.state == .stopped)
        #expect(child.exitedBy == SIGTERM)
    }

    @Test func spawnFailureIsReported() async {
        let subject = ServerSupervisor(
            spec: spec, launch: CLIServeLaunch(), policy: fastPolicy(),
            makeProcess: { _ in throw SpawnError.spawn(ENOENT) }, probe: { _ in true })
        await subject.start()
        guard case .failed(let failure) = subject.state else {
            Issue.record("expected a failure, got \(subject.state)")
            return
        }
        #expect(failure.summary.contains("No such file or directory"))
    }

    @Test func concurrentStopsAllWaitForTheChild() async {
        let child = FakeProcess(ignoresTerm: true)
        let subject = supervisor(child)
        child.say(servingLine)
        await subject.start()
        async let first: Void = subject.stop()
        async let second: Void = subject.stop()
        _ = await (first, second)
        #expect(child.hasExited)
        #expect(subject.state == .stopped)
    }

    @Test func gateStartsOneServerAtATime() async {
        let gate = LaunchGate()
        let first = FakeProcess(pid: 1)
        let second = FakeProcess(pid: 2)
        let released = Recorder<Bool>()
        let spawnOrder = Recorder<pid_t>()
        let slow = ServerSupervisor(
            spec: spec, launch: CLIServeLaunch(), policy: fastPolicy(), gate: gate,
            makeProcess: { _ in
                spawnOrder.append(1)
                return first
            },
            probe: { _ in released.count > 0 })
        let fast = ServerSupervisor(
            spec: spec, launch: CLIServeLaunch(), policy: fastPolicy(), gate: gate,
            makeProcess: { _ in
                spawnOrder.append(2)
                return second
            },
            probe: { _ in true })
        first.say(servingLine)
        second.say(servingLine)
        let a = Task { await slow.start() }
        #expect(await eventually { spawnOrder.count == 1 })
        let b = Task { await fast.start() }
        try? await Task.sleep(for: .milliseconds(100))
        #expect(spawnOrder.all == [1])  // the second waits while the first is not ready
        released.append(true)
        await a.value
        await b.value
        #expect(spawnOrder.all == [1, 2])
        #expect(slow.state == .ready(endpoint))
        #expect(fast.state == .ready(endpoint))
    }

    /// A start that waits at a held gate says so, and says when it has the gate, so a
    /// repository's window can say it waits for another's start (review A4 on #539).
    @Test func aStartWaitingAtTheGateSaysSo() async {
        let gate = LaunchGate()
        await gate.acquire()  // another start holds it
        let child = FakeProcess()
        child.say(servingLine)
        let subject = ServerSupervisor(
            spec: spec, launch: CLIServeLaunch(), policy: fastPolicy(), gate: gate, makeProcess: { _ in child },
            probe: { _ in true })
        let waits = Recorder<Bool>()
        let events = Recorder<String>()
        subject.onGateWait = { waits.append($0) }
        subject.onEvent = { events.append($0) }
        let started = Task { await subject.start() }
        #expect(await eventually { waits.all == [true] })
        #expect(events.all.first?.hasPrefix("waiting for another server") == true)
        gate.release()
        await started.value
        #expect(waits.all == [true, false])
        #expect(subject.state == .ready(endpoint))
        await subject.stop()
    }

    /// A ready server, its children, and the gate it starts behind, for the restarts below.
    private func gatedServer() async -> (ServerSupervisor, LaunchGate, () -> [FakeProcess]) {
        let gate = LaunchGate()
        var children: [FakeProcess] = []
        let subject = ServerSupervisor(
            spec: spec, launch: CLIServeLaunch(), policy: fastPolicy(), gate: gate,
            makeProcess: { _ in
                let child = FakeProcess(pid: pid_t(100 + children.count))
                child.say(servingLine)
                children.append(child)
                return child
            },
            probe: { _ in true })
        await subject.start()
        return (subject, gate, { children })
    }

    /// C2 on #539: a restart of a ready server whose gate another start holds, such as
    /// another repository's first clone, leaves the server serving until it has the gate,
    /// and only then stops it.
    @Test func aReadyServerServesUntilItsRestartHasTheGate() async {
        let (subject, gate, children) = await gatedServer()
        #expect(subject.state == .ready(endpoint))
        await gate.acquire()  // another start holds it
        let waits = Recorder<Bool>()
        let events = Recorder<String>()
        subject.onGateWait = { waits.append($0) }
        subject.onEvent = { events.append($0) }
        let next = LaunchSpec(executable: "/usr/bin/true")
        let restarted = Task { await subject.restart(using: next) }
        #expect(await eventually { waits.all == [true] })
        #expect(events.all.last?.hasPrefix("waiting for another server's start to finish before this one restarts") == true)
        try? await Task.sleep(for: .milliseconds(50))
        #expect(subject.state == .ready(endpoint))
        #expect(children().count == 1)
        #expect(children()[0].signals.isEmpty)
        gate.release()
        await restarted.value
        #expect(waits.all == [true, false])
        #expect(children().count == 2)
        #expect(children()[0].hasExited)
        #expect(subject.pid == 101)
        #expect(subject.spec == next)
        #expect(subject.state == .ready(endpoint))
        #expect(!gate.isHeld)
        await subject.stop()
    }

    /// A newer restart takes the place of one waiting at the gate, so one child starts, on
    /// the newest command; a stop meanwhile wins, and starts none.
    @Test func aNewerRequestReplacesARestartWaitingAtTheGate() async {
        let (subject, gate, children) = await gatedServer()
        await gate.acquire()
        let older = LaunchSpec(executable: "/usr/bin/older")
        let newer = LaunchSpec(executable: "/usr/bin/newer")
        let first = Task { await subject.restart(using: older) }
        #expect(await eventually { gate.isHeld && subject.state == .ready(endpoint) })
        try? await Task.sleep(for: .milliseconds(20))
        let second = Task { await subject.restart(using: newer) }
        try? await Task.sleep(for: .milliseconds(20))
        gate.release()
        await first.value
        await second.value
        #expect(children().count == 2)
        #expect(subject.spec == newer)
        #expect(subject.state == .ready(endpoint))
        #expect(!gate.isHeld)

        await gate.acquire()
        let waiting = Task { await subject.restart(using: older) }
        try? await Task.sleep(for: .milliseconds(20))
        await subject.stop()
        #expect(subject.state == .stopped)
        gate.release()
        await waiting.value
        #expect(children().count == 2)
        #expect(subject.state == .stopped)
        #expect(!gate.isHeld)
    }

    /// The ready server failing while its restart waits at the gate does not cancel the
    /// restart: the link it was asked for still opens.
    @Test func aCrashWhileARestartWaitsDoesNotCancelIt() async {
        let (subject, gate, children) = await gatedServer()
        await gate.acquire()
        let restarted = Task { await subject.restart() }
        try? await Task.sleep(for: .milliseconds(20))
        children()[0].exitOnItsOwn(code: 1)
        #expect(await eventually { if case .failed = subject.state { true } else { false } })
        gate.release()
        await restarted.value
        #expect(children().count == 2)
        #expect(subject.state == .ready(endpoint))
        await subject.stop()
    }
}
