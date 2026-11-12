import Darwin
import Foundation
import Testing
@testable import ShellCore

/// A folder's server launches only into a log this app has claimed: a claim that fails
/// fails the launch, which the window shows with Retry, and Retry claims again. Falling
/// back to the shared log would let two running copies mix their servers' output there.
@Suite struct FolderLogTests {
    private let root = URL(filePath: "/tmp/notes", directoryHint: .isDirectory)
    private let servingLine = "Serving /tmp/root at http://127.0.0.1:8412/view/"

    private func policy() -> SupervisorPolicy {
        var policy = SupervisorPolicy()
        policy.shutdownGrace = .milliseconds(50)
        policy.probeInterval = .milliseconds(5)
        policy.outputSettle = .milliseconds(20)
        return policy
    }

    /// Records each spawn's spec and returns a child that announces itself.
    private func spawner(_ spawned: Recorder<LaunchSpec>) -> ServerSupervisor.ProcessFactory {
        { [servingLine] spec in
            spawned.append(spec)
            let child = FakeProcess()
            child.say(servingLine)
            return child
        }
    }

    @Test func aClaimThatFailsLaunchesNothingAndRetryClaimsAgain() async throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let attempts = Recorder<Int>()
        let log = FolderLog(root: root, directory: folder) { root, directory in
            attempts.append(1)
            if attempts.count == 1 { throw ServerLogError("claim", "/locked", reason: "Permission denied") }
            return try ServerLogLease.claim(for: root, in: directory)
        }
        let spawned = Recorder<LaunchSpec>()
        let subject = ServerSupervisor(
            spec: LaunchSpec(executable: "/usr/bin/false", logURL: log.url), launch: CLIServeLaunch(),
            policy: policy(), makeProcess: log.processFactory(spawner(spawned)), probe: { _ in true })
        await subject.start()
        guard case .failed(let failure) = subject.state else {
            Issue.record("expected the launch to fail, got \(subject.state)")
            return
        }
        #expect(failure.summary.contains("could not claim the server log"))
        #expect(spawned.count == 0)
        await subject.restart()  // Retry
        #expect(attempts.count == 2)
        #expect(spawned.count == 1)
        #expect(spawned.all.first?.logURL == ServerLog.url(for: root, in: folder))
        #expect(log.url == ServerLog.url(for: root, in: folder))
        #expect(subject.state != .stopped)
        await subject.stop()
    }

    /// The review's case: the lock file cannot be opened, while the log beside it could
    /// be prepared and written.
    @Test func aLockFileThatCannotBeOpenedLaunchesNothingThoughTheLogCouldBeWritten() async throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let shared = ServerLog.url(for: root, in: folder)
        try FileManager.default.createDirectory(
            at: folder.appending(path: ".\(shared.lastPathComponent).lock"), withIntermediateDirectories: true)
        try FileManager.default.createDirectory(
            at: folder.appending(path: ".\(shared.deletingPathExtension().lastPathComponent).app-\(getpid()).log.lock"),
            withIntermediateDirectories: true)
        try ServerLog.prepare(shared)  // the log itself is fine
        let log = FolderLog(root: root, directory: folder)
        let spawned = Recorder<LaunchSpec>()
        let subject = ServerSupervisor(
            spec: LaunchSpec(executable: "/usr/bin/false", logURL: log.url), launch: CLIServeLaunch(),
            policy: policy(), makeProcess: log.processFactory(spawner(spawned)), probe: { _ in true })
        await subject.start()
        guard case .failed(let failure) = subject.state else {
            Issue.record("expected the launch to fail, got \(subject.state)")
            return
        }
        #expect(failure.summary.contains("could not claim the server log"))
        #expect(spawned.count == 0)
    }

    /// A claim that holds is kept for every later launch of the session, and each launch
    /// writes where the claim points, even a spec built with another path.
    @Test func everyLaunchWritesTheClaimedLog() async throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let other = try ServerLogLease.claim(for: root, in: folder, owner: 1)  // another copy holds the shared log
        let log = FolderLog(root: root, directory: folder)
        let spawned = Recorder<LaunchSpec>()
        let subject = ServerSupervisor(
            spec: LaunchSpec(executable: "/usr/bin/false", logURL: ServerLog.url(for: root, in: folder)),
            launch: CLIServeLaunch(), policy: policy(), makeProcess: log.processFactory(spawner(spawned)),
            probe: { _ in true })
        await subject.start()
        await subject.restart()
        #expect(spawned.count == 2)
        #expect(Set(spawned.all.map(\.logURL)) == [log.url])
        #expect(log.url != other.url)
        await subject.stop()
    }
}
