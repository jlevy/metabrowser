import Darwin
import Foundation
import Testing
@testable import ShellCore

/// Regressions from the spike's code review: each test failed before its fix.
private let servingLine = "Serving /tmp/root at http://127.0.0.1:8412/view/"
private let endpoint = ServerEndpoint(
    origin: URL(string: "http://127.0.0.1:8412")!, entryURL: URL(string: "http://127.0.0.1:8412/view/")!)
private let spec = LaunchSpec(executable: "/usr/bin/false")

private func policy(
    startup: Duration = .seconds(2), grace: Duration = .milliseconds(100), killWait: Duration = .seconds(2)
) -> SupervisorPolicy {
    var policy = SupervisorPolicy()
    policy.startupTimeout = startup
    policy.shutdownGrace = grace
    policy.killWait = killWait
    policy.probeInterval = .milliseconds(5)
    policy.outputSettle = .milliseconds(50)
    return policy
}

private func supervisor(_ child: FakeProcess, _ policy: SupervisorPolicy, gate: LaunchGate? = nil) -> ServerSupervisor {
    ServerSupervisor(
        spec: spec, launch: CLIServeLaunch(), policy: policy, gate: gate, makeProcess: { _ in child },
        probe: { _ in true })
}

@Suite struct LifecycleRegressionTests {
    /// Two restarts during one SIGTERM wait used to spawn a child that nothing ever
    /// signaled: the first launch returned without stopping it, and the second
    /// overwrote it.
    @Test(arguments: [false, true])
    func doubleRestartLeavesExactlyOneChild(withGate: Bool) async {
        var children: [FakeProcess] = []
        let subject = ServerSupervisor(
            spec: spec, launch: CLIServeLaunch(), policy: policy(), gate: withGate ? LaunchGate() : nil,
            makeProcess: { _ in
                // The first child is slow to stop, so both restarts wait on it together.
                let child = FakeProcess(pid: pid_t(100 + children.count), ignoresTerm: children.isEmpty)
                child.say(servingLine)
                children.append(child)
                return child
            },
            probe: { _ in true })
        await subject.start()
        async let first: Void = subject.restart()
        async let second: Void = subject.restart()
        _ = await (first, second)
        let running = children.filter { !$0.hasExited }
        #expect(running.count == 1)
        #expect(subject.pid == running.first?.pid)
        #expect(subject.childPIDs == running.map(\.pid))
        #expect(subject.state == .ready(endpoint))
        await subject.stop()
        let allExited = children.allSatisfy { $0.hasExited }
        #expect(allExited)
    }

    /// A stop during a failed start's grace period used to return at once, leaving a
    /// stuck server with SIGTERM but never SIGKILL, and out of reach of the exit-time
    /// kill.
    @Test func stopDuringAFailedStartWaitsForTheChildToDie() async {
        let child = FakeProcess(ignoresTerm: true)
        let subject = supervisor(child, policy(startup: .milliseconds(100), grace: .milliseconds(300)))
        let starting = Task { await subject.start() }
        #expect(await eventually { child.signals.contains(SIGTERM) })
        #expect(subject.childPIDs == [child.pid])  // visible to the exit-time kill
        await subject.stop()
        #expect(child.hasExited)
        #expect(child.exitedBy == SIGKILL)
        #expect(subject.childPIDs.isEmpty)
        await starting.value
        #expect(subject.state == .stopped)
    }

    @Test func stopWhileWaitingAtTheGateSpawnsNothingAndFreesTheGate() async {
        let gate = LaunchGate()
        await gate.acquire()  // another folder's server is starting
        let spawned = Recorder<Int>()
        let subject = ServerSupervisor(
            spec: spec, launch: CLIServeLaunch(), policy: policy(), gate: gate,
            makeProcess: { _ in
                spawned.append(1)
                return FakeProcess()
            },
            probe: { _ in true })
        let starting = Task { await subject.start() }
        #expect(await eventually { subject.state == .starting })
        await subject.stop()
        #expect(subject.state == .stopped)
        gate.release()
        await starting.value
        #expect(spawned.count == 0)
        #expect(subject.state == .stopped)
        let acquired = Recorder<Bool>()
        Task {
            await gate.acquire()
            acquired.append(true)
        }
        #expect(await eventually { acquired.count == 1 })
    }

    /// A process in uninterruptible I/O survives SIGKILL; the wait for it used to be
    /// unbounded, which hung quit and logout.
    @Test func aChildThatSurvivesSIGKILLDoesNotHangTheStop() async {
        let child = FakeProcess(ignoresTerm: true, ignoresKill: true)
        let subject = supervisor(child, policy(killWait: .milliseconds(200)))
        var events: [String] = []
        subject.onEvent = { events.append($0) }
        child.say(servingLine)
        await subject.start()
        let clock = ContinuousClock()
        let began = clock.now
        await subject.stop()
        #expect(began.duration(to: clock.now) < .seconds(2))
        #expect(subject.state == .stopped)
        #expect(Array(child.signals.prefix(2)) == [SIGTERM, SIGKILL])
        #expect(events.contains { $0.contains("did not exit within") })
    }

    @Test func commandRunnerGivesUpOnAChildThatSurvivesSIGKILL() async {
        let child = FakeProcess(ignoresTerm: true, ignoresKill: true)
        let clock = ContinuousClock()
        let began = clock.now
        let result = await CommandRunner.finish(child, timeout: .milliseconds(100), killWait: .milliseconds(100))
        #expect(result.timedOut)
        #expect(result.status == nil)
        #expect(began.duration(to: clock.now) < .seconds(2))
    }
}

/// The app delegate's quit ordering, through the fleet it delegates to.
@Suite struct ServerFleetTests {
    private func ready(_ child: FakeProcess, grace: Duration = .milliseconds(200)) async -> ServerSupervisor {
        let subject = supervisor(child, policy(grace: grace))
        child.say(servingLine)
        await subject.start()
        return subject
    }

    @Test func quitWaitsForAServerStillStoppingFromAClosedWindow() async {
        let slow = FakeProcess(pid: 1, ignoresTerm: true)
        let quick = FakeProcess(pid: 2)
        let closed = await ready(slow)
        let open = await ready(quick)
        let fleet = ServerFleet()
        fleet.insert(closed, for: "/a")
        fleet.insert(open, for: "/b")
        fleet.retire(closed)  // its last window closed: SIGTERM, then the grace period
        #expect(fleet["/a"] == nil)
        #expect(fleet.stoppingCount == 1)
        #expect(Set(fleet.childPIDs) == [1, 2])
        await fleet.stopAll()  // Quit
        #expect(slow.exitedBy == SIGKILL)
        #expect(quick.exitedBy == SIGTERM)
        #expect(fleet.isEmpty)
        #expect(fleet.childPIDs.isEmpty)
    }

    @Test func quitDuringAFailedStartWaitsForTheKill() async {
        let child = FakeProcess(ignoresTerm: true)
        let subject = supervisor(child, policy(startup: .milliseconds(100), grace: .milliseconds(300)))
        let fleet = ServerFleet()
        fleet.insert(subject, for: "/a")
        let starting = Task { await subject.start() }
        #expect(await eventually { child.signals.contains(SIGTERM) })
        #expect(fleet.childPIDs == [child.pid])
        await fleet.stopAll()
        #expect(child.exitedBy == SIGKILL)
        await starting.value
    }

    @Test func reopeningAFolderWhileItsOldServerStopsTracksBoth() async {
        let old = FakeProcess(pid: 1, ignoresTerm: true)
        let new = FakeProcess(pid: 2)
        let previous = await ready(old)
        let fleet = ServerFleet()
        fleet.insert(previous, for: "/a")
        fleet.retire(previous)
        let current = await ready(new)
        fleet.insert(current, for: "/a")
        #expect(fleet["/a"] === current as any ManagedServer)
        #expect(fleet.stoppingCount == 1)
        fleet.retire(previous)  // a late second close is harmless
        #expect(fleet.stoppingCount == 1)
        await fleet.stopAll()
        #expect(old.hasExited)
        #expect(new.hasExited)
    }

    @Test func insertingOverAnOpenServerRetiresIt() async {
        let first = FakeProcess(pid: 1)
        let fleet = ServerFleet()
        fleet.insert(await ready(first), for: "/a")
        fleet.insert(await ready(FakeProcess(pid: 2)), for: "/a")
        await fleet.stopAll()
        #expect(first.hasExited)
    }
}

/// A restart waits for the old child to stop before it launches the next one. A stop that
/// arrives during that wait used to lose to it: the restart launched anyway, after the
/// fleet had let the server go, so closing a folder's last window during a restart left a
/// server nothing would ever stop (review findings A2 and C2 on #341).
@Suite struct RestartSupersededTests {
    /// A server whose first child holds on until the test lets it exit, and whose later
    /// children are ordinary.
    private final class Children {
        var all: [FakeProcess] = []
        func make() -> FakeProcess {
            let child = FakeProcess(pid: pid_t(100 + all.count), ignoresTerm: all.isEmpty, ignoresKill: all.isEmpty)
            child.say(servingLine)
            all.append(child)
            return child
        }
    }

    private func subject(_ children: Children) -> ServerSupervisor {
        ServerSupervisor(
            spec: spec, launch: CLIServeLaunch(), policy: policy(grace: .milliseconds(20), killWait: .seconds(5)),
            makeProcess: { _ in children.make() }, probe: { _ in true })
    }

    @Test func closingTheLastWindowDuringARestartLeavesNothingRunning() async {
        let children = Children()
        let server = subject(children)
        await server.start()
        let fleet = ServerFleet()
        fleet.insert(server, for: "/a")
        let restarting = Task { await server.restart() }
        #expect(await eventually { children.all[0].signals.contains(SIGKILL) })  // waiting on the old child
        fleet.retire(server)  // the last window closed
        children.all[0].exitOnItsOwn()
        await restarting.value
        await fleet.stopAll()
        #expect(children.all.count == 1)
        let allExited = children.all.allSatisfy { $0.hasExited }
        #expect(allExited)
        #expect(server.state == .stopped)
        #expect(fleet.isEmpty)
        #expect(fleet.childPIDs.isEmpty)
    }

    @Test func aStopDuringARestartWins() async {
        let children = Children()
        let server = subject(children)
        await server.start()
        let restarting = Task { await server.restart() }
        #expect(await eventually { children.all[0].signals.contains(SIGKILL) })
        let stopping = Task { await server.stop() }
        try? await Task.sleep(for: .milliseconds(20))
        children.all[0].exitOnItsOwn()
        await restarting.value
        await stopping.value
        #expect(children.all.count == 1)
        #expect(server.state == .stopped)
        #expect(server.childPIDs.isEmpty)
    }

    @Test func aShutDownServerStartsNothingLater() async {
        let spawned = Recorder<Int>()
        let server = ServerSupervisor(
            spec: spec, launch: CLIServeLaunch(), policy: policy(),
            makeProcess: { _ in
                spawned.append(1)
                let child = FakeProcess()
                child.say(servingLine)
                return child
            }, probe: { _ in true })
        await server.start()
        await server.shutDown()
        await server.start()
        await server.restart()
        #expect(spawned.count == 1)
        #expect(server.state == .stopped)
    }
}
