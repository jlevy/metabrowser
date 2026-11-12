import Darwin
import Foundation
import Testing
@testable import ShellCore

/// One gate for every server start (PR #361 A1, A2, B2, C1, C2): a folder's first start,
/// a restored folder's later start, Retry, Restart Server, and the restart after an
/// upgrade all run the runtime the app accepts at that moment, or nothing.
@Suite struct FolderServerTests {
    private let tools = ToolPaths(git: "/usr/bin/git")
    private let servingLine = "Serving /tmp/root at http://127.0.0.1:8412/view/"

    private func stamp(_ n: UInt64) -> FileFingerprint {
        FileFingerprint(device: 1, inode: n, size: 348, modified: 1_000, mode: 0o100755)
    }

    private func setup(_ executable: String, _ version: String, _ n: UInt64 = 1) -> RuntimeSetup {
        RuntimeSetup(
            runtime: Runtime(executable: executable, version: version, source: .localBin, fingerprint: stamp(n)),
            tools: tools)
    }

    private func selection(with setup: RuntimeSetup?) -> RuntimeSelection {
        RuntimeSelection(
            settings: RuntimeSettings(defaults: UserDefaults(suiteName: "shellcore-gate-\(UUID().uuidString)")!),
            setup: setup)
    }

    private func fastPolicy() -> SupervisorPolicy {
        var policy = SupervisorPolicy()
        policy.startupTimeout = .seconds(30)  // the fakes answer at once; a loaded machine is slow
        policy.shutdownGrace = .milliseconds(100)
        policy.probeInterval = .milliseconds(5)
        policy.outputSettle = .milliseconds(50)
        return policy
    }

    /// Children handed out in order, each announcing itself; `launched` records the
    /// executable of every launch.
    private final class Children: @unchecked Sendable {
        let launched = Recorder<String>()
        private(set) var made: [FakeProcess] = []
        let line: String

        init(line: String) { self.line = line }

        func make(_ spec: LaunchSpec) -> FakeProcess {
            launched.append(spec.executable)
            let child = FakeProcess(pid: pid_t(5000 + made.count))
            child.say(line)
            made.append(child)
            return child
        }
    }

    private func server(
        createdWith created: RuntimeSetup, accepted: @escaping () -> RuntimeSetup?, children: Children
    ) -> FolderServer {
        let root = URL(filePath: "/tmp/root", directoryHint: .isDirectory)
        let launch = CLIServeLaunch()
        let spec = { (setup: RuntimeSetup) in launch.spec(serving: root, with: setup, inherited: [:], logURL: nil) }
        let supervisor = ServerSupervisor(
            spec: spec(created), launch: launch, policy: fastPolicy(), makeProcess: { children.make($0) },
            probe: { _ in true })
        return FolderServer(supervisor: supervisor, accepted: accepted, spec: spec)
    }

    @Test func aStartRunsTheRuntimeAcceptedWhenItStartsNotTheOneTheFolderWasMadeWith() async {
        let children = Children(line: servingLine)
        let now = setup("/opt/b/metab", "0.13.0")
        let subject = server(createdWith: setup("/opt/a/metab", "0.12.1"), accepted: { now }, children: children)
        #expect(subject.startedRuntime == nil)
        #expect(await subject.start())
        #expect(children.launched.all == ["/opt/b/metab"])
        #expect(subject.startedRuntime == now.runtime)
    }

    /// A restored folder whose turn comes after its runtime was rejected waits for one,
    /// and starts once one is accepted.
    @Test func aStartWithoutAnAcceptedRuntimeLaunchesNothingUntilOneIs() async {
        let children = Children(line: servingLine)
        let old = setup("/opt/metab", "0.12.1")
        let runtime = selection(with: old)
        let recheck = runtime.startRecheck()
        _ = runtime.finishRecheck(recheck, fingerprint: stamp(2), result: .tooOld(version: "0.12.0"))
        let subject = server(createdWith: old, accepted: { runtime.launchableSetup }, children: children)
        #expect(await subject.start() == false)
        #expect(subject.held == .start)
        #expect(children.launched.all == [])
        #expect(subject.supervisor.state == .stopped)
        #expect(subject.startedRuntime == nil)
        await subject.resume()  // still none: nothing changes
        #expect(children.launched.all == [])
        let search = runtime.startSearch()
        let found = setup("/opt/metab", "0.13.0", 3)
        _ = runtime.finishSearch(search, with: DiscoveryReport(setup: found, tried: []))
        await subject.resume()
        #expect(children.launched.all == ["/opt/metab"])
        #expect(subject.held == nil)
        #expect(subject.startedRuntime == found.runtime)
    }

    /// A1, B2: replacing a running folder's metab with an older one, and rechecking it,
    /// left no runtime, and Restart Server ran the rejected file again.
    @Test func aRestartAfterTheRuntimeWasRejectedKeepsTheRunningServer() async {
        let children = Children(line: servingLine)
        let old = setup("/opt/metab", "0.12.1")
        let runtime = selection(with: old)
        let subject = server(createdWith: old, accepted: { runtime.launchableSetup }, children: children)
        #expect(await subject.start())
        let running = subject.supervisor.state
        #expect(running == .ready(ServerEndpoint(
            origin: URL(string: "http://127.0.0.1:8412")!, entryURL: URL(string: "http://127.0.0.1:8412/view/")!)))
        let recheck = runtime.startRecheck()
        _ = runtime.finishRecheck(recheck, fingerprint: stamp(2), result: .tooOld(version: "0.12.0"))
        #expect(runtime.setup == nil)
        #expect(await subject.restart() == false)
        #expect(subject.held == .restart)
        #expect(children.made[0].signals == [])
        #expect(subject.supervisor.state == running)
        #expect(children.launched.count == 1)
        #expect(subject.startedRuntime == old.runtime)
    }

    /// A1, B2, C2: during a recheck the folder's own runtime is unchecked, so a restart
    /// waits for the recheck's answer instead of reusing it.
    @Test func aRestartDuringARecheckWaitsForItsAnswer() async {
        let children = Children(line: servingLine)
        let old = setup("/opt/metab", "0.12.1")
        let runtime = selection(with: old)
        let subject = server(createdWith: old, accepted: { runtime.launchableSetup }, children: children)
        #expect(await subject.start())
        #expect(children.made[0].signals == [])  // ready, not stopped by a slow start
        let recheck = runtime.startRecheck()
        #expect(await subject.restart() == false)
        #expect(children.made[0].signals == [])
        _ = runtime.finishRecheck(recheck, fingerprint: stamp(2), result: .valid(version: "0.13.0"))
        await subject.resume()
        #expect(children.made[0].signals.first == SIGTERM)
        #expect(children.launched.count == 2)
        #expect(subject.startedRuntime?.version == "0.13.0")
        #expect(subject.held == nil)
    }

    /// A2, C1: a restored folder in a protected location had a runtime from the moment
    /// its session was made, so an upgrade counted it as an outdated server and
    /// restarting started it, raising the privacy prompt the restore deferred.
    @Test func anUpgradeOffersToRestartOnlyServersThatStarted() async {
        let children = Children(line: servingLine)
        let old = setup("/Volumes/Home/.local/bin/metab", "0.12.1")
        let runtime = selection(with: old)
        let notes = "/Volumes/Home/notes"
        let documents = "/Volumes/Home/Documents/private"
        var queue = RestoreQueue(
            SavedSession(windows: [
                SavedWindow(
                    tabs: [SavedTab(root: notes, page: nil), SavedTab(root: documents, page: nil)], selected: 0,
                    frame: nil),
            ]),
            isProtected: { $0.hasPrefix("/Volumes/Home/Documents") })
        let servers = [notes, documents].map { _ in
            server(createdWith: old, accepted: { runtime.launchableSetup }, children: children)
        }
        while let path = queue.next() {
            await servers[path == notes ? 0 : 1].start()
        }
        #expect(queue.deferred == [documents])
        let recheck = runtime.startRecheck()
        let upgraded = setup("/Volumes/Home/.local/bin/metab", "0.13.0", 2)
        _ = runtime.finishRecheck(recheck, fingerprint: stamp(2), result: .valid(version: "0.13.0"))
        #expect(runtime.launchableSetup == upgraded)
        let started = servers.map(\.startedRuntime)
        #expect(RuntimeUpgrade.outdated(started, current: runtime.launchableSetup?.runtime) == [0])
        #expect(servers[1].supervisor.state == .stopped)
        #expect(children.launched.count == 1)
    }

    /// C2: the offer was answered after a later replacement left no runtime, and the
    /// restart fell back to the runtime the offer was made for.
    @Test func noRestartIsOutdatedWithoutAnAcceptedRuntime() {
        let started: [Runtime?] = [setup("/opt/metab", "0.12.1").runtime, nil]
        #expect(RuntimeUpgrade.outdated(started, current: nil) == [])
    }
}
