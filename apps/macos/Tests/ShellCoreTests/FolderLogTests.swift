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

    /// Review E2 on #363: closing a folder's last window retires its session, which keeps
    /// its claim until its server has stopped (`ServerFleet.retire`), and the folder can
    /// be opened again before then. The claim tried only the folder's log and one named
    /// for this process, so with both held, by another copy of the app or by an earlier
    /// session still stopping, the reopened folder's launch failed with "another process
    /// holds it", and nothing retried once the old claim was let go.
    ///
    /// Each child here ignores SIGTERM and stops only when the test lets it, so the old
    /// sessions are still stopping, and still writing, when the folder is opened again.
    @Test(arguments: [true, false])
    func aFolderReopenedWhileItsServerStopsLaunchesIntoALogOfItsOwn(anotherCopyHoldsTheFoldersLog: Bool)
        async throws
    {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let release = folder.appending(path: "release").path(percentEncoded: false)
        var policy = policy()
        policy.shutdownGrace = .seconds(60)  // each stop ends when the test lets its child go
        let fleet = ServerFleet()
        func stopAll() async {
            FileManager.default.createFile(atPath: release, contents: nil)
            await fleet.stopAll()
        }

        /// A session of the folder: its log, and a server whose child names itself `name`.
        func session(_ name: String) -> (log: FolderLog, server: ServerSupervisor) {
            let script = """
                trap '' TERM
                echo '\(servingLine)'
                echo 'output of \(name)' >&2
                while [ ! -e '\(release)' ]; do sleep 0.05; done
                echo '\(name) stopped' >&2
                """
            let log = FolderLog(root: root, directory: folder)
            let server = ServerSupervisor(
                spec: LaunchSpec(executable: "/bin/sh", arguments: ["-c", script]), launch: CLIServeLaunch(),
                policy: policy, makeProcess: log.processFactory(), probe: { _ in true })
            return (log, server)
        }

        let other = anotherCopyHoldsTheFoldersLog ? try ServerLogLease.claim(for: root, in: folder, owner: 1) : nil
        let names = anotherCopyHoldsTheFoldersLog ? ["first", "reopened"] : ["first", "second", "reopened"]
        var sessions: [(name: String, log: FolderLog)] = []
        for name in names {
            let (log, server) = session(name)
            fleet.insert(server, for: root.path)  // retires the session before it, which keeps stopping
            sessions.append((name, log))
            await server.start()  // once: no Retry
            guard case .ready = server.state else {
                Issue.record("\(name) did not launch: \(server.state)")
                await stopAll()
                return
            }
        }
        #expect(fleet.stoppingCount == names.count - 1)  // every earlier session is still stopping
        let logs = sessions.map(\.log.url)
        #expect(Set(logs).count == logs.count)
        if let other { #expect(!logs.contains(other.url)) }

        await stopAll()  // the earlier children write their last line while the reopened one runs
        for session in sessions {
            let written = try String(contentsOf: session.log.url, encoding: .utf8)
            let output = written.split(separator: "\n").map(String.init)
                .filter { !$0.hasPrefix(ServerLog.appLinePrefix) }
            #expect(Set(output) == [servingLine, "output of \(session.name)", "\(session.name) stopped"])
        }
        // Once their servers have stopped and nothing keeps the sessions, their names are
        // free again, so the names a copy uses do not run out over a long run.
        let first = logs[0]
        sessions.removeAll()
        #expect(await eventually { (try? ServerLogLease.claim(for: root, in: folder))?.url == first })
        withExtendedLifetime(other) {}
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

    /// Review F2 on #377: a development build and a release share the logs folder
    /// (mb-d71s). One copy holds the folder's log, grown past the rotation size, with an
    /// archive beside it; a second copy launches and restarts the same folder. Each launch
    /// prepares, and so may rotate, only the log it claimed: preparing the shared path
    /// while spawning into the claimed one would rotate the first copy's log under its
    /// running server.
    @Test func aSecondCopyNeverRotatesTheLogAnotherCopyHolds() async throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let other = try ServerLogLease.claim(for: root, in: folder, owner: 1)  // the first copy
        let shared = ServerLog.url(for: root, in: folder)
        #expect(other.url == shared)
        let archive = URL(filePath: shared.path(percentEncoded: false) + ".1")
        try Data("the first copy's archive\n".utf8).write(to: archive)
        try ServerLog.prepare(shared)
        let handle = try FileHandle(forWritingTo: shared)
        try handle.write(contentsOf: Data("the first copy's server\n".utf8))
        try handle.truncate(atOffset: UInt64(ServerLog.rotationBytes + 1))  // past the limit, sparse
        try handle.close()
        func identity(_ url: URL) throws -> (inode: Int, size: Int) {
            let attributes = try FileManager.default.attributesOfItem(atPath: url.path(percentEncoded: false))
            return ((attributes[.systemFileNumber] as? Int) ?? -1, (attributes[.size] as? Int) ?? -1)
        }
        let before = try identity(shared)

        let log = FolderLog(root: root, directory: folder)  // the second copy's session
        let spawned = Recorder<LaunchSpec>()
        let subject = ServerSupervisor(
            spec: LaunchSpec(executable: "/usr/bin/false", logURL: log.url), launch: CLIServeLaunch(),
            policy: policy(), makeProcess: log.processFactory(spawner(spawned)), probe: { _ in true })
        await subject.start()
        await subject.restart()
        await subject.stop()

        #expect(spawned.count == 2)
        #expect(log.url != shared)
        #expect(Set(spawned.all.map(\.logURL)) == [log.url])
        let own = try? FileManager.default.attributesOfItem(atPath: log.url.path(percentEncoded: false))
        #expect(own?[.posixPermissions] as? Int == 0o600, "the second copy prepared its own log")
        let after = try identity(shared)
        #expect(after.inode == before.inode && after.size == before.size, "the first copy's log was replaced")
        let reader = try FileHandle(forReadingFrom: shared)
        #expect(try reader.read(upToCount: 24) == Data("the first copy's server\n".utf8))
        try reader.close()
        #expect(try String(contentsOf: archive, encoding: .utf8) == "the first copy's archive\n")
        withExtendedLifetime(other) {}
    }
}
