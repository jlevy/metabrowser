import Darwin
import Foundation
import Testing
@testable import ShellCore

/// A child's pid is also its process group id, and once the exited leader is reaped and
/// its group is empty the kernel can hand that id to an unrelated group. The exit
/// handler used to reap at once, so the final group SIGKILL of every stop went to an id
/// the app no longer owned (review finding B3 on #341). Children are now reaped only by
/// `release()`, after the last signal.
private let servingLine = "Serving /tmp/root at http://127.0.0.1:8412/view/"
private let spec = LaunchSpec(executable: "/usr/bin/false")

private func policy(startup: Duration = .seconds(2), killWait: Duration = .seconds(2)) -> SupervisorPolicy {
    var policy = SupervisorPolicy()
    policy.startupTimeout = startup
    policy.shutdownGrace = .milliseconds(50)
    policy.killWait = killWait
    policy.probeInterval = .milliseconds(5)
    policy.outputSettle = .milliseconds(20)
    return policy
}

/// Every child the supervisor ended was released, and nothing was signaled after.
private func ownedToTheEnd(_ children: [FakeProcess]) -> Bool {
    children.allSatisfy { $0.isReleased && $0.signalsAfterRelease.isEmpty }
}

@Suite struct PidOwnershipTests {
    private final class Spawned {
        var all: [FakeProcess] = []
        var make: () -> FakeProcess = { FakeProcess() }
        func supervisor(_ policy: SupervisorPolicy, probe: @escaping ServerSupervisor.ReadinessProbe = { _ in true })
            -> ServerSupervisor
        {
            ServerSupervisor(
                spec: spec, launch: CLIServeLaunch(), policy: policy,
                makeProcess: { [self] _ in
                    let child = make()
                    all.append(child)
                    return child
                }, probe: probe)
        }
    }

    private func announcing(ignoresTerm: Bool = false, ignoresKill: Bool = false) -> () -> FakeProcess {
        {
            let child = FakeProcess(ignoresTerm: ignoresTerm, ignoresKill: ignoresKill)
            child.say(servingLine)
            return child
        }
    }

    @Test(arguments: [false, true])
    func aStopReleasesTheChildAfterItsLastSignal(ignoresTerm: Bool) async {
        let spawned = Spawned()
        spawned.make = announcing(ignoresTerm: ignoresTerm)
        let subject = spawned.supervisor(policy())
        await subject.start()
        await subject.stop()
        #expect(spawned.all.count == 1)
        #expect(spawned.all[0].signals.last == SIGKILL)  // the group sweep after the exit
        #expect(ownedToTheEnd(spawned.all))
    }

    @Test func aRestartReleasesTheOldChild() async {
        let spawned = Spawned()
        spawned.make = announcing()
        let subject = spawned.supervisor(policy())
        await subject.start()
        await subject.restart()
        #expect(spawned.all.count == 2)
        #expect(spawned.all[0].isReleased)
        #expect(spawned.all[0].signalsAfterRelease.isEmpty)
        #expect(!spawned.all[1].isReleased)  // still running, still owned
        await subject.stop()
        #expect(ownedToTheEnd(spawned.all))
    }

    @Test func aCrashAfterReadyIsSweptThenReleased() async {
        let spawned = Spawned()
        spawned.make = announcing()
        let subject = spawned.supervisor(policy())
        await subject.start()
        spawned.all[0].exitOnItsOwn(code: 1)
        #expect(await eventually { spawned.all[0].isReleased })
        #expect(spawned.all[0].signals == [SIGKILL])
        #expect(ownedToTheEnd(spawned.all))
    }

    @Test func aStartThatTimesOutReleasesItsChild() async {
        let spawned = Spawned()
        let subject = spawned.supervisor(policy(startup: .milliseconds(50)))
        await subject.start()  // the child never announces itself
        guard case .failed = subject.state else {
            Issue.record("expected a failure, got \(subject.state)")
            return
        }
        #expect(ownedToTheEnd(spawned.all))
    }

    @Test func aStartWhoseChildExitsReleasesIt() async {
        let spawned = Spawned()
        spawned.make = {
            let child = FakeProcess()
            child.exitOnItsOwn(code: 2)
            return child
        }
        let subject = spawned.supervisor(policy())
        await subject.start()
        #expect(ownedToTheEnd(spawned.all))
    }

    /// A child stuck in uninterruptible I/O is given up on but still released, so it is
    /// reaped whenever it does exit, and nothing signals it after that.
    @Test func aChildGivenUpOnIsReleasedToo() async {
        let spawned = Spawned()
        spawned.make = announcing(ignoresTerm: true, ignoresKill: true)
        let subject = spawned.supervisor(policy(killWait: .milliseconds(50)))
        await subject.start()
        await subject.stop()
        #expect(!spawned.all[0].hasExited)
        #expect(ownedToTheEnd(spawned.all))
    }

    @Test(arguments: [false, true])
    func aCommandIsReleasedAfterItsLastSignal(timesOut: Bool) async {
        let child = FakeProcess()
        if !timesOut { child.exitOnItsOwn(code: 0) }
        _ = await CommandRunner.finish(child, timeout: .milliseconds(50), killWait: .milliseconds(50))
        #expect(child.signals.last == SIGKILL)
        #expect(ownedToTheEnd([child]))
    }
}

/// What `ChildOwnership` asks of the kernel, in order.
private nonisolated enum KernelCall: Equatable, Sendable {
    case signal(Int32)
    case reap
}

/// The order of an exit's publication (review finding D1 on #341). The exit handler once
/// resumed the exit waiters before it recorded the exit, so a waiter that released the
/// child at once found it not yet exited: nothing reaped it then, and a signal sent next
/// still reached its group. Each waiter here runs inside the announcement, the earliest a
/// resumed waiter can run, so no test depends on how threads are scheduled.
@Suite struct ChildOwnershipTests {
    private func recording(_ calls: Recorder<KernelCall>) -> ChildOwnership {
        ChildOwnership(
            pid: 4242, sendToGroup: { _, signal in calls.append(.signal(signal)) },
            reapZombie: { _ in calls.append(.reap) })
    }

    @Test func aWaiterThatReleasesAtOnceReapsAndSilencesTheGroup() {
        let calls = Recorder<KernelCall>()
        let ownership = recording(calls)
        var reapedByRelease = false
        ownership.exited {
            ownership.release()
            reapedByRelease = ownership.isReaped
            ownership.signalGroup(SIGKILL)
        }
        #expect(reapedByRelease)
        #expect(calls.all == [.reap])
    }

    @Test func aChildReleasedWhileRunningIsReapedBeforeItsExitIsAnnounced() {
        let calls = Recorder<KernelCall>()
        let ownership = recording(calls)
        ownership.release()
        #expect(calls.all.isEmpty)
        var reapedBeforeAnnouncement = false
        ownership.exited { reapedBeforeAnnouncement = ownership.isReaped }
        #expect(reapedBeforeAnnouncement)
        #expect(calls.all == [.reap])
    }

    /// The stop's sweep after the leader exits still reaches the group; only the reap
    /// ends signalling.
    @Test func theGroupHearsSignalsUntilTheReap() {
        let calls = Recorder<KernelCall>()
        let ownership = recording(calls)
        ownership.signalGroup(SIGTERM)
        ownership.exited {}
        ownership.signalGroup(SIGKILL)
        ownership.release()
        ownership.signalGroup(SIGKILL)
        #expect(calls.all == [.signal(SIGTERM), .signal(SIGKILL), .reap])
    }

    /// The exit handler can run twice for one exit, and a deallocated process releases
    /// again: the child is still reaped once.
    @Test func aChildIsReapedOnce() {
        let calls = Recorder<KernelCall>()
        let ownership = recording(calls)
        ownership.exited {}
        ownership.release()
        ownership.exited {}
        ownership.release()
        #expect(calls.all == [.reap])
    }
}

/// The looks for an exit run one at a time (review finding E1 on #341). The NOTE_EXIT
/// handler and the first look once ran concurrently: a handler that found the exit
/// unpublished just before the first look published it went on to a blocking wait after
/// the owner had released and reaped the child, on a pid the kernel could by then have
/// given to another child. Here NOTE_EXIT arrives while the first look is inside its read,
/// and the owner releases the child inside the announcement, the earliest it can.
@Suite struct ExitObservationTests {
    private nonisolated enum Call: Equatable, Sendable {
        case read(waiting: Bool)
        case reap
    }

    @Test func aLookQueuedBehindAPublicationDoesNotWaitAfterTheRelease() {
        let calls = Recorder<Call>()
        let ownership = ChildOwnership(pid: 4242, sendToGroup: { _, _ in }, reapZombie: { _ in calls.append(.reap) })
        let exit = Latch<Int32>()
        let reading = DispatchSemaphore(value: 0)
        let finishRead = DispatchSemaphore(value: 0)
        let observation = ExitObservation(
            isPublished: { exit.isResolved },
            readExit: { waiting in
                calls.append(.read(waiting: waiting))
                if !waiting {
                    reading.signal()
                    finishRead.wait()
                }
                return 0
            },
            publish: { status in
                ownership.exited {
                    exit.resolve(status)
                    ownership.release()  // a waiter that releases the child the moment it resumes
                }
            })
        observation.queue.async { observation.look(waiting: false) }  // the first look finds the exit
        reading.wait()
        observation.queue.async { observation.look(waiting: true) }  // NOTE_EXIT, as the source delivers it
        finishRead.signal()
        observation.queue.sync {}  // both looks have run
        #expect(calls.all == [.read(waiting: false), .reap])
    }

    @Test func aLookThatFindsNothingLeavesTheNextOneToRead() {
        let calls = Recorder<Call>()
        let exit = Latch<Int32>()
        let observation = ExitObservation(
            isPublished: { exit.isResolved },
            readExit: { waiting in
                calls.append(.read(waiting: waiting))
                return waiting ? 0 : nil  // still running at the first look
            },
            publish: { exit.resolve($0) })
        let first = observation.queue.sync { observation.look(waiting: false) }
        let second = observation.queue.sync { observation.look(waiting: true) }
        let third = observation.queue.sync { observation.look(waiting: true) }
        #expect([first, second, third] == [false, true, true])
        #expect(calls.all == [.read(waiting: false), .read(waiting: true)])
        #expect(exit.isResolved)
    }
}

/// The same ownership on real children.
@Suite struct SpawnedPidOwnershipTests {
    /// Whether `pid` is a child of this process that has exited and is not yet reaped.
    private func isUnreapedZombie(_ pid: pid_t) -> Bool {
        var info = siginfo_t()
        return waitid(P_PID, id_t(pid), &info, WEXITED | WNOHANG | WNOWAIT) == 0 && info.si_pid == pid
    }

    private func firstLine(of child: SpawnedProcess) async -> String? {
        for await line in child.lines { return line }
        return nil
    }

    @Test func anExitedChildKeepsItsPidUntilReleased() async throws {
        let child = try SpawnedProcess(LaunchSpec(executable: "/bin/sh", arguments: ["-c", "exit 3"]))
        let status = try #require(await child.waitForExit())
        #expect(ExitStatus(waitStatus: status) == .exited(3))
        #expect(isUnreapedZombie(child.pid))
        child.release()
        var unused: Int32 = 0
        #expect(waitpid(child.pid, &unused, WNOHANG) == -1)  // reaped: ECHILD
        #expect(errno == ECHILD)
    }

    @Test func aSignalExitDecodesFromWaitid() async throws {
        let child = try SpawnedProcess(LaunchSpec(executable: "/bin/sh", arguments: ["-c", "kill -KILL $$"]))
        let status = try #require(await child.waitForExit())
        #expect(ExitStatus(waitStatus: status) == .signaled(SIGKILL))
        child.release()
    }

    /// The leader exits and leaves a background job in its group: the sweep still
    /// reaches the job, because the unreaped leader keeps the group id.
    @Test func theSweepAfterTheLeaderExitsReachesItsGroup() async throws {
        let child = try SpawnedProcess(LaunchSpec(executable: "/bin/sh", arguments: ["-c", "sleep 30 & echo $!; exit 0"]))
        let job = try #require(await firstLine(of: child).flatMap { pid_t($0) })
        _ = await child.waitForExit()
        #expect(isUnreapedZombie(child.pid))
        #expect(processExists(job))
        child.signalGroup(SIGKILL)
        #expect(await eventually { !processExists(job) })
        child.release()
    }

    @Test func noSignalLeavesAfterRelease() async throws {
        let child = try SpawnedProcess(LaunchSpec(executable: "/bin/sh", arguments: ["-c", "sleep 30 & echo $!; exit 0"]))
        let job = try #require(await firstLine(of: child).flatMap { pid_t($0) })
        defer { kill(job, SIGKILL) }
        _ = await child.waitForExit()
        child.release()
        child.signalGroup(SIGKILL)  // dropped: the pid is no longer the app's to signal
        try await Task.sleep(for: .milliseconds(100))
        #expect(processExists(job))
    }

    /// A child released while it still runs is reaped when it exits.
    @Test func aChildReleasedWhileRunningIsReapedAtExit() async throws {
        let child = try SpawnedProcess(LaunchSpec(executable: "/bin/sh", arguments: ["-c", "read line"], stdinLine: nil))
        child.release()
        let pid = child.pid
        child.closeLifeline()  // stdin EOF: the shell exits
        _ = await child.waitForExit()
        #expect(await eventually {
            var unused: Int32 = 0
            return waitpid(pid, &unused, WNOHANG) == -1 && errno == ECHILD
        })
    }
}
