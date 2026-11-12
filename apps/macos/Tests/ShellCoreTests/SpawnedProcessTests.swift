import Darwin
import Foundation
import Testing
@testable import ShellCore

/// The real posix_spawn path, with /bin/sh as the child.
@Suite struct SpawnedProcessTests {
    private func lines(of child: SpawnedProcess) async -> [String] {
        var seen: [String] = []
        for await line in child.lines { seen.append(line) }
        return seen
    }

    @Test func childLeadsItsOwnProcessGroup() async throws {
        let child = try SpawnedProcess(LaunchSpec(executable: "/bin/sh", arguments: ["-c", "exec sleep 30"]))
        #expect(getpgid(child.pid) == child.pid)
        #expect(getpgid(child.pid) != getpgrp())
        child.signalGroup(SIGTERM)
        let status = await child.waitForExit()
        #expect(status.map(ExitStatus.init(waitStatus:)) == .signaled(SIGTERM))
    }

    @Test func childSeesOnlyTheEnvironmentItIsGiven() async throws {
        let child = try SpawnedProcess(LaunchSpec(
            executable: "/usr/bin/env", environment: ["PATH": "/usr/bin:/bin", "ONLY": "this"]))
        #expect(await lines(of: child).sorted() == ["ONLY=this", "PATH=/usr/bin:/bin"])
        #expect(await child.waitForExit() == 0)
    }

    /// stdout reaches the lines and the log; stderr only the log. The two reach the log
    /// by different paths, so their order there is not asserted.
    @Test func stdoutReachesTheLinesAndBothReachTheLog() async throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let log = directory.appending(path: "server.log")
        let child = try SpawnedProcess(LaunchSpec(
            executable: "/bin/sh", arguments: ["-c", "echo out; echo err >&2; printf 'no newline'"],
            logURL: log))
        #expect(await lines(of: child) == ["out", "no newline"])
        #expect(await child.waitForExit() == 0)
        #expect(child.recentOutput().sorted() == ["err", "no newline", "out"])
        let written = try String(contentsOf: log, encoding: .utf8)
        #expect(written.split(separator: "\n").sorted() == ["err", "no newline", "out"])
        let mode = try FileManager.default.attributesOfItem(atPath: log.path)[.posixPermissions] as? Int
        #expect(mode == 0o600)
    }

    @Test func stdinLineArrivesAndClosingTheLifelineIsEOF() async throws {
        let child = try SpawnedProcess(LaunchSpec(
            executable: "/bin/sh", arguments: ["-c", #"read t; echo "got $t"; cat >/dev/null; echo eof"#],
            stdinLine: "token"))
        var seen: [String] = []
        for await line in child.lines {
            seen.append(line)
            if line.hasPrefix("got") { child.closeLifeline() }
        }
        #expect(seen == ["got token", "eof"])
        #expect(await child.waitForExit() == 0)
    }

    @Test func workingDirectoryIsApplied() async throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let child = try SpawnedProcess(LaunchSpec(
            executable: "/bin/pwd", arguments: ["-P"], workingDirectory: directory.path))
        #expect(await lines(of: child) == [directory.path(percentEncoded: false).trimmingSuffix("/")])
    }

    /// The child must never run in another folder than the one it serves.
    @Test func aWorkingDirectoryThatIsGoneFailsTheSpawn() {
        #expect(throws: SpawnError.spawn(ENOENT)) {
            try SpawnedProcess(LaunchSpec(executable: "/bin/pwd", workingDirectory: "/nonexistent-\(UUID().uuidString)"))
        }
    }

    @Test func groupSignalReachesAGrandchild() async throws {
        let child = try SpawnedProcess(LaunchSpec(
            executable: "/bin/sh", arguments: ["-c", "sleep 30 & echo $!; wait"]))
        var grandchild: pid_t?
        for await line in child.lines {
            grandchild = pid_t(line)
            break
        }
        let pid = try #require(grandchild)
        #expect(getpgid(pid) == child.pid)
        child.signalGroup(SIGTERM)
        _ = await child.waitForExit()
        #expect(await eventually { !processExists(pid) })
    }

    @Test func relativeExecutableIsRefused() {
        // posix_spawn would resolve it inside the working directory: the served folder.
        #expect(throws: SpawnError.relativeExecutable("metab")) {
            try SpawnedProcess(LaunchSpec(executable: "metab", workingDirectory: "/tmp"))
        }
    }

    @Test func missingExecutableThrows() {
        #expect(throws: SpawnError.spawn(ENOENT)) {
            try SpawnedProcess(LaunchSpec(executable: "/nonexistent/metab"))
        }
    }
}

@Suite struct CommandRunnerTests {
    @Test func collectsOutputAndStatus() async {
        let result = await CommandRunner.run(
            LaunchSpec(executable: "/bin/sh", arguments: ["-c", "echo hello; exit 3"]), timeout: .seconds(5))
        #expect(result.output == ["hello"])
        #expect(result.status.map(ExitStatus.init(waitStatus:)) == .exited(3))
        #expect(!result.succeeded)
    }

    @Test func stdinIsAtEOF() async {
        let result = await CommandRunner.run(
            LaunchSpec(executable: "/bin/cat"), timeout: .seconds(5))
        #expect(result.succeeded)
        #expect(result.output.isEmpty)
    }

    /// Each bound below separates the command's deadline from a wait for its 30-second
    /// sleep, so it sits halfway between them, far above the main-actor stalls of a loaded
    /// three-core CI runner, where these took 2.4 seconds against a 3-second bound.
    @Test func deadlineKillsTheCommand() async {
        let clock = ContinuousClock()
        let started = clock.now
        let result = await CommandRunner.run(
            LaunchSpec(executable: "/bin/sleep", arguments: ["30"]), timeout: .milliseconds(200))
        #expect(result.timedOut)
        #expect(result.status == nil)
        #expect(started.duration(to: clock.now) < .seconds(15))
    }

    @Test func backgroundJobDoesNotHoldTheResultOrSurvive() async {
        let clock = ContinuousClock()
        let started = clock.now
        let result = await CommandRunner.run(
            LaunchSpec(executable: "/bin/sh", arguments: ["-c", "sleep 30 & echo $!"]), timeout: .seconds(5))
        #expect(result.succeeded)
        #expect(started.duration(to: clock.now) < .seconds(15))
        let job = pid_t(result.output.first ?? "")
        #expect(job != nil)
        if let job { #expect(await eventually { !processExists(job) }) }
    }

    @Test func launchErrorIsReported() async {
        let result = await CommandRunner.run(LaunchSpec(executable: "/nonexistent/metab"), timeout: .seconds(1))
        #expect(result.launchError != nil)
        #expect(!result.succeeded)
    }
}

/// A real child under the supervisor: ready on its line, and gone after stop.
@Suite struct SupervisedProcessTests {
    private struct Interrupted: Error {}

    private func fakeServer() -> ServerSupervisor {
        let script = #"echo "Serving /tmp at http://127.0.0.1:9/view/"; exec sleep 30"#
        return ServerSupervisor(
            spec: LaunchSpec(executable: "/bin/sh", arguments: ["-c", script]),
            launch: CLIServeLaunch(), probe: { _ in true })
    }

    /// The live test's cleanup, on a child that is still running when the body throws.
    @Test func aBodyThatThrowsStillStopsTheServer() async throws {
        let subject = fakeServer()
        await subject.start()
        let pid = try #require(subject.pid)
        await #expect(throws: Interrupted.self) {
            try await stoppingAfterward(subject) {
                #expect(processExists(pid))
                throw Interrupted()
            }
        }
        #expect(subject.state == .stopped)
        #expect(!processExists(pid))
    }

    @Test func aCancelledBodyStillStopsTheServer() async throws {
        let subject = fakeServer()
        await subject.start()
        let pid = try #require(subject.pid)
        let request = Task {
            try await stoppingAfterward(subject) {
                _ = try await URLSession.shared.data(from: URL(string: "http://127.0.0.1:9/view/")!)
                try await Task.sleep(for: .seconds(30))
            }
        }
        request.cancel()
        await #expect(throws: (any Error).self) { try await request.value }
        #expect(!processExists(pid))
    }

    @Test func stopLeavesNoProcess() async throws {
        let script = #"echo "Serving /tmp at http://127.0.0.1:9/view/"; exec sleep 30"#
        var policy = SupervisorPolicy()
        policy.shutdownGrace = .seconds(2)
        let subject = ServerSupervisor(
            spec: LaunchSpec(executable: "/bin/sh", arguments: ["-c", script]),
            launch: CLIServeLaunch(), policy: policy, probe: { _ in true })
        await subject.start()
        guard case .ready(let endpoint) = subject.state else {
            Issue.record("expected ready, got \(subject.state)")
            return
        }
        #expect(endpoint.origin.absoluteString == "http://127.0.0.1:9")
        let pid = try #require(subject.pid)
        #expect(processExists(pid))
        await subject.stop()
        #expect(subject.state == .stopped)
        #expect(!processExists(pid))
    }

    @Test func childIgnoringTermIsKilledAfterTheGrace() async throws {
        let script = #"trap '' TERM; echo "Serving /tmp at http://127.0.0.1:9/view/"; while :; do sleep 1; done"#
        var policy = SupervisorPolicy()
        policy.shutdownGrace = .milliseconds(300)
        let subject = ServerSupervisor(
            spec: LaunchSpec(executable: "/bin/sh", arguments: ["-c", script]),
            launch: CLIServeLaunch(), policy: policy, probe: { _ in true })
        var events: [String] = []
        subject.onEvent = { events.append($0) }
        await subject.start()
        let pid = try #require(subject.pid)
        await subject.stop()
        #expect(!processExists(pid))
        #expect(events.contains { $0.contains("SIGKILL to its process group") })
        #expect(events.last?.contains("signal 9 (SIGKILL)") == true)
    }
}

extension String {
    fileprivate func trimmingSuffix(_ suffix: String) -> String {
        hasSuffix(suffix) && count > suffix.count ? String(dropLast(suffix.count)) : self
    }
}
