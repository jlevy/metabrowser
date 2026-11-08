import Darwin
import Foundation
import Testing
@testable import ShellCore

private let servingLine = "Serving /tmp/root at http://127.0.0.1:8412/view/"
private let endpoint = ServerEndpoint(
    origin: URL(string: "http://127.0.0.1:8412")!, entryURL: URL(string: "http://127.0.0.1:8412/view/")!)
private let spec = LaunchSpec(executable: "/usr/bin/false")

private func fastPolicy(startup: Duration = .seconds(2)) -> SupervisorPolicy {
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
}
