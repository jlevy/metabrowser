import Foundation
import Testing
@testable import ShellCore

/// A runtime chosen in Settings reaches an open folder at its next Retry or Restart
/// Server (review findings A3 and C4 on #341). Each folder's command used to be fixed
/// when the folder opened, so a restart ran the old `metab` again.
@Suite struct RuntimeSwitchTests {
    private let servingLine = "Serving /tmp/root at http://127.0.0.1:8412/view/"
    private let root = URL(filePath: "/tmp/notes", directoryHint: .isDirectory)

    private func setup(_ executable: String, git: String) -> RuntimeSetup {
        RuntimeSetup(runtime: Runtime(executable: executable, version: "0.12.0", source: .chosen), tools: ToolPaths(git: git))
    }

    @Test func aRestartWithANewCommandRunsIt() async {
        let launch = CLIServeLaunch()
        let old = launch.spec(serving: root, with: setup("/opt/a/metab", git: "/opt/a/bin/git"), inherited: [:], logURL: nil)
        let new = launch.spec(serving: root, with: setup("/opt/b/metab", git: "/opt/b/bin/git"), inherited: [:], logURL: nil)
        let spawned = Recorder<LaunchSpec>()
        var policy = SupervisorPolicy()
        policy.shutdownGrace = .milliseconds(50)
        policy.outputSettle = .milliseconds(10)
        let line = servingLine
        let subject = ServerSupervisor(
            spec: old, launch: launch, policy: policy,
            makeProcess: { spec in
                spawned.append(spec)
                let child = FakeProcess()
                child.say(line)
                return child
            }, probe: { _ in true })
        await subject.start()
        await subject.restart(using: new)
        #expect(spawned.all.map(\.executable) == ["/opt/a/metab", "/opt/b/metab"])
        #expect(spawned.all.last?.environment["PATH"]?.hasPrefix("/opt/b/bin:") == true)
        #expect(subject.spec == new)
        await subject.restart()  // no new command: the same one again
        #expect(spawned.all.last == new)
        await subject.stop()
    }

    @Test func aFolderCommandComesFromItsSetup() {
        let spec = CLIServeLaunch().spec(
            serving: root, with: setup("/opt/b/metab", git: "/opt/b/bin/git"),
            inherited: ["HOME": "/Users/someone", "VIRTUAL_ENV": "/tmp/venv"], logURL: URL(filePath: "/tmp/notes.log"))
        #expect(spec.executable == "/opt/b/metab")
        #expect(spec.arguments == CLIServeLaunch().arguments(serving: root))
        #expect(spec.workingDirectory == "/tmp/notes/")
        #expect(spec.environment["HOME"] == "/Users/someone")
        #expect(spec.environment["VIRTUAL_ENV"] == nil)
        #expect(spec.environment["PATH"]?.hasPrefix("/opt/b/bin:") == true)
        #expect(spec.logURL == URL(filePath: "/tmp/notes.log"))
    }
}
