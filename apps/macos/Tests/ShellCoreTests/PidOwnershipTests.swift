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
