import Darwin
import Foundation
import Testing
@testable import ShellCore

/// The last check before a restored background server spawns: after the launch gate and
/// any earlier child's termination, not before them (review E1).
@Suite struct RestoreLaunchTests {
    private let spec = LaunchSpec(executable: "/usr/bin/false")

    private func policy() -> SupervisorPolicy {
        var policy = SupervisorPolicy()
        policy.startupTimeout = .seconds(2)
        policy.shutdownGrace = .milliseconds(100)
        policy.probeInterval = .milliseconds(5)
        return policy
    }

    /// A home folder in a temporary directory with an ordinary root and Documents.
    private func folders() throws -> (directory: URL, home: String, root: String) {
        let directory = try temporaryDirectory()
        let home = FileChecks.canonicalPath(directory.path(percentEncoded: false))
        for folder in ["wrk/app", "Documents/secret"] {
            try FileManager.default.createDirectory(atPath: home + "/" + folder, withIntermediateDirectories: true)
        }
        return (directory, home, home + "/wrk/app")
    }

    private func supervisor(gate: LaunchGate, spawned: Recorder<Int>) -> ServerSupervisor {
        ServerSupervisor(
            spec: spec, launch: CLIServeLaunch(), policy: policy(), gate: gate,
            makeProcess: { _ in
                spawned.append(1)
                let child = FakeProcess()
                child.say("Serving /tmp/root at http://127.0.0.1:8412/view/")
                return child
            },
            probe: { _ in true })
    }

    @Test func aRootReplacedWhileItsServerWaitsAtTheGateIsNotSpawned() async throws {
        let (directory, home, root) = try folders()
        defer { try? FileManager.default.removeItem(at: directory) }
        #expect(RootAdmission.admit(root, home: home) == .open(root))
        let gate = LaunchGate()
        await gate.acquire()  // an earlier folder's server is starting
        let spawned = Recorder<Int>()
        let checks = Recorder<Bool>()
        let subject = supervisor(gate: gate, spawned: spawned)
        subject.mayLaunch = {
            let admitted = RootAdmission.admit(root, home: home) == .open(root)
            checks.append(admitted)
            return admitted
        }
        let starting = Task { await subject.start() }
        #expect(await eventually { subject.state == .starting })
        // While it waits behind the gate, the root becomes a link into Documents.
        try FileManager.default.moveItem(atPath: root, toPath: root + "-moved")
        try FileManager.default.createSymbolicLink(atPath: root, withDestinationPath: home + "/Documents/secret")
        gate.release()
        await starting.value
        #expect(checks.all == [false])
        #expect(spawned.count == 0)
        #expect(subject.state == .stopped)
        #expect(subject.launchWasRefused)
        // The gate is free for the next server.
        let acquired = Recorder<Bool>()
        Task {
            await gate.acquire()
            acquired.append(true)
        }
        #expect(await eventually { acquired.count == 1 })
    }

    @Test func anUnchangedRootStartsAndAClearedCheckIsNotAsked() async throws {
        let (directory, home, root) = try folders()
        defer { try? FileManager.default.removeItem(at: directory) }
        let spawned = Recorder<Int>()
        let subject = supervisor(gate: LaunchGate(), spawned: spawned)
        subject.mayLaunch = { RootAdmission.admit(root, home: home) == .open(root) }
        await subject.start()
        #expect(spawned.count == 1)
        #expect(!subject.launchWasRefused)
        await subject.stop()

        // A selected tab clears the check: it starts as the user's choice.
        subject.mayLaunch = { Issue.record("a cleared check was asked"); return false }
        subject.mayLaunch = nil
        await subject.start()
        #expect(spawned.count == 2)
        await subject.stop()
    }
}
