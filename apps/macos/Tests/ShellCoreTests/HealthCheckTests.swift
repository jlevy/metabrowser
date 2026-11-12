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
    /// stays silent.
    private final class Server: Sendable {
        private let hung = Latch<Void>()
        func hang() { hung.resolve(()) }

        var probe: ServerSupervisor.ReadinessProbe {
            { [hung] _ in
                guard hung.isResolved else { return true }
                try? await Task.sleep(for: .seconds(30))
                return false
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

    private func ready(_ child: FakeProcess, probe: @escaping ServerSupervisor.ReadinessProbe) async -> ServerSupervisor {
        let subject = ServerSupervisor(
            spec: LaunchSpec(executable: "/usr/bin/false"), launch: CLIServeLaunch(), policy: policy(),
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

    /// The exit is the failure to report, with its status, not an unanswered probe.
    @Test func aServerThatExitsDuringTheCheckFailsAsAnExit() async {
        let child = FakeProcess()
        let server = Server()
        let subject = await ready(child, probe: server.probe)
        server.hang()
        var events: [String] = []
        subject.onEvent = { events.append($0) }
        let checking = Task { await subject.checkHealth() }
        child.exitOnItsOwn(code: 1)
        #expect(await checking.value == .notReady)
        let failed = await eventually { if case .failed = subject.state { true } else { false } }
        #expect(failed, "events: \(events)")
        guard case .failed(let failure) = subject.state else {
            Issue.record("expected a failure, got \(subject.state)")
            return
        }
        #expect(failure.summary.contains("stopped unexpectedly (exit status 1)"))
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
}
