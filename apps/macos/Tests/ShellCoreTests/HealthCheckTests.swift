import Darwin
import Foundation
import Testing
@testable import ShellCore

/// A window attaching to a running server first asks whether it still answers: a live
/// process is not a working server, since a hung one keeps its pid.
@Suite struct HealthCheckTests {
    private let servingLine = "Serving /tmp/root at http://127.0.0.1:8412/view/"
    private let endpoint = ServerEndpoint(
        origin: URL(string: "http://127.0.0.1:8412")!, entryURL: URL(string: "http://127.0.0.1:8412/view/")!)

    /// Answers until `hang()`, then never, the way a hung server's socket accepts and
    /// stays silent; `probing` resolves once a probe is waiting on the hung server, and
    /// `answer(_:)` ends every waiting probe with that answer.
    private final class Server: Sendable {
        private let hung = Latch<Void>()
        let probing = Latch<Void>()
        private let answered = Latch<Bool>()
        let probes = Recorder<Int>()
        func hang() { hung.resolve(()) }
        func answer(_ ok: Bool) { answered.resolve(ok) }

        var probe: ServerSupervisor.ReadinessProbe {
            { [hung, probing, answered, probes] _ in
                guard hung.isResolved else { return true }
                probes.append(1)
                probing.resolve(())
                return await answered.wait() ?? false  // nil: the check's deadline passed
            }
        }
    }

    private func policy(deadline: Duration = .milliseconds(200)) -> SupervisorPolicy {
        var policy = SupervisorPolicy()
        policy.healthDeadline = deadline
        policy.shutdownGrace = .milliseconds(50)
        policy.probeInterval = .milliseconds(5)
        policy.outputSettle = .milliseconds(20)
        return policy
    }

    private func ready(
        _ child: FakeProcess, probe: @escaping ServerSupervisor.ReadinessProbe, deadline: Duration = .milliseconds(200)
    ) async -> ServerSupervisor {
        let subject = ServerSupervisor(
            spec: LaunchSpec(executable: "/usr/bin/false"), launch: CLIServeLaunch(), policy: policy(deadline: deadline),
            makeProcess: { _ in child }, probe: probe)
        child.say(servingLine)
        await subject.start()
        return subject
    }

    @Test func aServerThatAnswersIsHealthyAndKeepsRunning() async {
        let child = FakeProcess()
        let probes = Recorder<URL>()
        let subject = await ready(child) { url in
            probes.append(url)
            return true
        }
        #expect(await subject.checkHealth() == .healthy(endpoint))
        #expect(probes.all == [endpoint.entryURL, endpoint.entryURL])  // readiness, then health
        #expect(subject.state == .ready(endpoint))
        #expect(child.signals.isEmpty)
    }

    @Test func aServerThatStopsAnsweringIsStoppedAndFailsWithTheReason() async {
        let child = FakeProcess()
        let server = Server()
        let subject = await ready(child, probe: server.probe)
        child.say("INFO: still logging")
        server.hang()
        let clock = ContinuousClock()
        let began = clock.now
        #expect(await subject.checkHealth() == .unresponsive)
        #expect(began.duration(to: clock.now) < .seconds(2))  // bounded by the deadline, not the probe
        guard case .failed(let failure) = subject.state else {
            Issue.record("expected a failure, got \(subject.state)")
            return
        }
        #expect(failure.summary.contains("stopped answering"))
        #expect(failure.summary.contains("http://127.0.0.1:8412/view/"))
        #expect(failure.recentOutput.last == "INFO: still logging")
        #expect(child.exitedBy == SIGTERM)
        #expect(child.isReleased)
        #expect(subject.childPIDs.isEmpty)
    }

    @Test func aServerThatIsNotReadyIsNotProbed() async {
        let probes = Recorder<URL>()
        let subject = ServerSupervisor(
            spec: LaunchSpec(executable: "/usr/bin/false"), launch: CLIServeLaunch(), policy: policy(),
            makeProcess: { _ in FakeProcess() }, probe: { url in
                probes.append(url)
                return true
            })
        #expect(await subject.checkHealth() == .notReady)
        #expect(probes.count == 0)
        #expect(subject.state == .stopped)
    }

    /// The exit is the failure to report, with its status, not an unanswered probe. The
    /// child exits while a probe is waiting on it, and is stopped and reported once.
    @Test func aServerThatExitsDuringTheCheckFailsAsAnExit() async {
        let child = FakeProcess()
        let server = Server()
        let subject = await ready(child, probe: server.probe)
        var failures: [ServerFailure] = []
        subject.onChange = { if case .failed(let failure) = $0 { failures.append(failure) } }
        server.hang()
        let checking = Task { await subject.checkHealth() }
        #expect(await server.probing.wait() != nil)  // the check is waiting on its probe
        child.exitOnItsOwn(code: 1)
        #expect(await checking.value == .notReady)
        #expect(await eventually { !failures.isEmpty })
        #expect(failures.count == 1)
        #expect(failures.first?.summary.contains("stopped unexpectedly (exit status 1)") == true)
        #expect(child.signals == [SIGKILL])  // the sweep after the exit, and nothing from the check
        #expect(child.isReleased)
    }

    /// Two windows attaching at once to a hung server stop it once and report it once.
    @Test func concurrentChecksOfAHungServerStopItOnce() async {
        let child = FakeProcess()
        let server = Server()
        let subject = await ready(child, probe: server.probe)
        var failures = 0
        subject.onChange = { if case .failed = $0 { failures += 1 } }
        server.hang()
        async let first = subject.checkHealth()
        async let second = subject.checkHealth()
        let results = await [first, second]
        #expect(results.contains(.unresponsive))
        #expect(failures == 1)
        #expect(child.signals.filter { $0 == SIGTERM }.count == 1)
    }

    /// A check that starts while another is waiting joins it: one probe, one outcome. A
    /// second, separate probe could time out after the first succeeded and stop a server
    /// that had just answered.
    @Test func aCheckThatStartsDuringAnotherSharesItsAnswer() async {
        let child = FakeProcess()
        let server = Server()
        let subject = await ready(child, probe: server.probe, deadline: .seconds(10))
        server.hang()
        let first = Task { await subject.checkHealth() }
        #expect(await server.probing.wait() != nil)
        let second = Task { await subject.checkHealth() }
        #expect(await eventually { subject.healthCheckWaiters == 2 })
        server.answer(true)
        #expect(await first.value == .healthy(endpoint))
        #expect(await second.value == .healthy(endpoint))
        #expect(server.probes.count == 1)
        #expect(child.signals.isEmpty)
        #expect(subject.state == .ready(endpoint))
    }
}
