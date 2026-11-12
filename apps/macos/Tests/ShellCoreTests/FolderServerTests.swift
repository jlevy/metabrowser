import Darwin
import Foundation
import Testing
@testable import ShellCore

/// One gate for every server start (mb-9lh2, mb-bqxx): a folder's first start,
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

    private func fastPolicy(grace: Duration = .milliseconds(100)) -> SupervisorPolicy {
        var policy = SupervisorPolicy()
        policy.startupTimeout = .seconds(30)  // the fakes answer at once; a loaded machine is slow
        policy.shutdownGrace = grace
        policy.probeInterval = .milliseconds(5)
        policy.outputSettle = .milliseconds(50)
        return policy
    }

    /// Children handed out in order, each announcing itself; `launched` records the
    /// executable of every launch. The children numbered in `ignoringTerm` ignore SIGTERM,
    /// so stopping them takes the whole grace period.
    private final class Children: @unchecked Sendable {
        let launched = Recorder<String>()
        private(set) var made: [FakeProcess] = []
        let line: String
        let ignoringTerm: Set<Int>

        init(line: String, ignoringTerm: Set<Int> = []) {
            self.line = line
            self.ignoringTerm = ignoringTerm
        }

        func make(_ spec: LaunchSpec) -> FakeProcess {
            launched.append(spec.executable)
            let child = FakeProcess(pid: pid_t(5000 + made.count), ignoresTerm: ignoringTerm.contains(made.count))
            child.say(line)
            made.append(child)
            return child
        }
    }

    private func server(
        createdWith created: RuntimeSetup, accepted: @escaping () -> RuntimeSetup?, children: Children,
        gate: LaunchGate? = nil, grace: Duration = .milliseconds(100)
    ) -> FolderServer {
        let root = URL(filePath: "/tmp/root", directoryHint: .isDirectory)
        let launch = CLIServeLaunch()
        let spec = { (setup: RuntimeSetup) in launch.spec(serving: root, with: setup, inherited: [:], logURL: nil) }
        let supervisor = ServerSupervisor(
            spec: spec(created), launch: launch, policy: fastPolicy(grace: grace), gate: gate,
            makeProcess: { children.make($0) },
            probe: { _ in true })
        return FolderServer(supervisor: supervisor, accepted: accepted, spec: spec)
    }

    @Test func aStartRunsTheRuntimeAcceptedWhenItStartsNotTheOneTheFolderWasMadeWith() async {
        let children = Children(line: servingLine)
        let now = setup("/opt/b/metab", "0.13.0")
        let subject = server(createdWith: setup("/opt/a/metab", "0.12.1"), accepted: { now }, children: children)
        #expect(subject.startedRuntime == nil)
        #expect(await subject.start() == .launched)
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
        #expect(await subject.start() == .waitingForRuntime)
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

    /// Replacing a running folder's metab with an older one, and rechecking it,
    /// left no runtime, and Restart Server ran the rejected file again.
    @Test func aRestartAfterTheRuntimeWasRejectedKeepsTheRunningServer() async {
        let children = Children(line: servingLine)
        let old = setup("/opt/metab", "0.12.1")
        let runtime = selection(with: old)
        let subject = server(createdWith: old, accepted: { runtime.launchableSetup }, children: children)
        #expect(await subject.start() == .launched)
        let running = subject.supervisor.state
        #expect(running == .ready(ServerEndpoint(
            origin: URL(string: "http://127.0.0.1:8412")!, entryURL: URL(string: "http://127.0.0.1:8412/view/")!)))
        let recheck = runtime.startRecheck()
        _ = runtime.finishRecheck(recheck, fingerprint: stamp(2), result: .tooOld(version: "0.12.0"))
        #expect(runtime.setup == nil)
        #expect(await subject.restart() == .waitingForRuntime)
        #expect(subject.held == .restart)
        #expect(children.made[0].signals == [])
        #expect(subject.supervisor.state == running)
        #expect(children.launched.count == 1)
        #expect(subject.startedRuntime == old.runtime)
    }

    /// During a recheck the folder's own runtime is unchecked, so a restart
    /// waits for the recheck's answer instead of reusing it.
    @Test func aRestartDuringARecheckWaitsForItsAnswer() async {
        let children = Children(line: servingLine)
        let old = setup("/opt/metab", "0.12.1")
        let runtime = selection(with: old)
        let subject = server(createdWith: old, accepted: { runtime.launchableSetup }, children: children)
        #expect(await subject.start() == .launched)
        #expect(children.made[0].signals == [])  // ready, not stopped by a slow start
        let recheck = runtime.startRecheck()
        #expect(await subject.restart() == .waitingForRuntime)
        #expect(children.made[0].signals == [])
        _ = runtime.finishRecheck(recheck, fingerprint: stamp(2), result: .valid(version: "0.13.0"))
        await subject.resume()
        #expect(children.made[0].signals.first == SIGTERM)
        #expect(children.launched.count == 2)
        #expect(subject.startedRuntime?.version == "0.13.0")
        #expect(subject.held == nil)
    }

    /// A restored folder in a protected location had a runtime from the moment
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

    /// The offer was answered after a later replacement left no runtime, and the
    /// restart fell back to the runtime the offer was made for.
    @Test func noRestartIsOutdatedWithoutAnAcceptedRuntime() {
        let started: [Runtime?] = [setup("/opt/metab", "0.12.1").runtime, nil]
        #expect(RuntimeUpgrade.outdated(started, current: nil) == [])
    }

    // MARK: - The check at the moment of spawning (mb-7uqe)

    /// A start that waited behind another server at the launch gate spawned the runtime
    /// it was given before the wait, though a recheck rejected it meanwhile.
    @Test func aStartWaitingAtTheLaunchGateSpawnsNothingOnceItsRuntimeIsRejected() async {
        let children = Children(line: servingLine)
        let old = setup("/opt/metab", "0.12.1")
        let runtime = selection(with: old)
        let gate = LaunchGate()
        await gate.acquire()  // another folder's server is starting
        let subject = server(createdWith: old, accepted: { runtime.launchableSetup }, children: children, gate: gate)
        let starting = Task { await subject.start() }
        #expect(await eventually { subject.supervisor.state == .starting })
        let recheck = runtime.startRecheck()
        _ = runtime.finishRecheck(recheck, fingerprint: stamp(2), result: .tooOld(version: "0.12.0"))
        gate.release()
        #expect(await starting.value == .waitingForRuntime)
        #expect(children.launched.all == [])
        #expect(subject.startedRuntime == nil)  // nothing launched, so nothing started from it
        #expect(subject.held == .start)
        #expect(subject.supervisor.state == .stopped)
        let search = runtime.startSearch()
        let found = setup("/opt/metab", "0.13.0", 3)
        _ = runtime.finishSearch(search, with: DiscoveryReport(setup: found, tried: []))
        await subject.resume()
        #expect(children.launched.all == ["/opt/metab"])
        #expect(subject.startedRuntime == found.runtime)
    }

    /// A runtime replaced while the start waited is the one it spawns.
    @Test func aStartWaitingAtTheLaunchGateSpawnsTheRuntimeAcceptedWhenTheGateOpens() async {
        let children = Children(line: servingLine)
        let runtime = selection(with: setup("/opt/a/metab", "0.12.1"))
        let gate = LaunchGate()
        await gate.acquire()
        let subject = server(
            createdWith: setup("/opt/a/metab", "0.12.1"), accepted: { runtime.launchableSetup }, children: children,
            gate: gate)
        let starting = Task { await subject.start() }
        #expect(await eventually { subject.supervisor.state == .starting })
        let choice = runtime.startChoice()
        _ = runtime.finishChoice(choice, path: "/opt/b/metab", result: .valid(version: "0.13.0")) { tools }
        gate.release()
        #expect(await starting.value == .launched)
        #expect(children.launched.all == ["/opt/b/metab"])
        #expect(subject.startedRuntime?.executable == "/opt/b/metab")
    }

    /// A restart checked its runtime, then waited for the old server to stop, and
    /// spawned that runtime though it had been rejected while the old server stopped.
    @Test func aRestartWhoseOldServerIsStoppingSpawnsNothingOnceItsRuntimeIsRejected() async {
        let children = Children(line: servingLine, ignoringTerm: [0])
        let old = setup("/opt/metab", "0.12.1")
        let runtime = selection(with: old)
        let subject = server(
            createdWith: old, accepted: { runtime.launchableSetup }, children: children, grace: .seconds(2))
        #expect(await subject.start() == .launched)
        let restarting = Task { await subject.restart() }
        // The old server ignores SIGTERM, so the restart waits out the grace period.
        #expect(await eventually { children.made[0].signals == [SIGTERM] })
        let recheck = runtime.startRecheck()
        _ = runtime.finishRecheck(recheck, fingerprint: stamp(2), result: .tooOld(version: "0.12.0"))
        #expect(await restarting.value == .waitingForRuntime)
        #expect(children.made[0].signals.first == SIGTERM && children.made[0].signals.contains(SIGKILL))
        #expect(children.launched.count == 1)
        #expect(subject.held == .restart)
        #expect(subject.startedRuntime == old.runtime)
    }

    /// A restore's start does not wait in `held`: the restore queue keeps the root, so
    /// it is admitted again and keeps its place when a runtime is accepted.
    @Test func aRestoredStartWithoutARuntimeIsNotHeldByTheServer() async {
        let children = Children(line: servingLine)
        let runtime = selection(with: nil)
        let subject = server(
            createdWith: setup("/opt/metab", "0.12.1"), accepted: { runtime.launchableSetup }, children: children)
        #expect(await subject.start(holding: false) == .waitingForRuntime)
        #expect(subject.held == nil)
        #expect(!subject.isRuntimeAccepted)
    }

    /// The root check a restore sets for a background folder runs at the same moment,
    /// after the runtime check, and its refusal is told apart from a missing runtime.
    @Test func theRootCheckRunsBesideTheRuntimeCheckAtTheMomentOfSpawning() async {
        let children = Children(line: servingLine)
        let runtime = selection(with: setup("/opt/metab", "0.12.1"))
        let subject = server(
            createdWith: setup("/opt/metab", "0.12.1"), accepted: { runtime.launchableSetup }, children: children)
        let asked = Recorder<Int>()
        subject.rootCheck = {
            asked.append(1)
            return false
        }
        #expect(await subject.start(holding: false) == .refusedByRoot)
        #expect(asked.count == 1)
        #expect(children.launched.all == [])
        subject.rootCheck = nil  // a selected tab starts it as the user's choice
        #expect(await subject.start(holding: false) == .launched)
        #expect(children.launched.count == 1)
    }
}

/// A restore that paused for want of a runtime (mb-nwr5): the root goes back to the
/// front of the queue, so it is admitted again before it starts, keeps its place, can
/// still be selected first, and is dropped if its tabs close.
@Suite struct RestorePauseTests {
    private func queue(_ roots: [String], selectedFront: Bool = true) -> RestoreQueue {
        RestoreQueue(
            SavedSession(windows: roots.map { SavedWindow(tabs: [SavedTab(root: $0, page: nil)], selected: 0, frame: nil) }),
            isProtected: { _ in false })
    }

    @Test func aRootPutBackStartsNextAndKeepsItsOrder() {
        var subject = queue(["/r/a", "/r/b", "/r/c"])
        #expect(subject.next() == "/r/a")
        #expect(subject.next() == "/r/b")
        subject.putBack("/r/b")
        #expect(subject.pending == ["/r/b", "/r/c"])
        // Selecting another tab while the restore waits puts it first.
        let selectedC = subject.select("/r/c")
        #expect(selectedC)
        #expect(subject.pending == ["/r/c", "/r/b"])
        // Closing a waiting root's tabs drops it.
        subject.remove("/r/b")
        #expect(subject.pending == ["/r/c"])
        #expect(subject.next() == "/r/c")
        #expect(subject.next() == nil)
    }

    /// A background root that waited for a runtime and was replaced meanwhile by a link
    /// into Documents waits for its tab instead, as at any other turn.
    @Test func aRootPutBackIsAdmittedAgainWhenItsTurnComes() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let home = FileChecks.canonicalPath(directory.path(percentEncoded: false))
        for folder in ["notes", "wrk/app", "Documents/secret"] {
            try FileManager.default.createDirectory(atPath: home + "/" + folder, withIntermediateDirectories: true)
        }
        let front = home + "/notes"
        let background = home + "/wrk/app"
        var subject = queue([front, background])
        let admitted = { (root: String) in RootAdmission.admit(root, home: home) == .open(root) }
        #expect(subject.next(stillOpen: admitted) == front)
        #expect(subject.next(stillOpen: admitted) == background)
        subject.putBack(background)  // its start found no runtime
        try FileManager.default.moveItem(atPath: background, toPath: background + "-moved")
        try FileManager.default.createSymbolicLink(atPath: background, withDestinationPath: home + "/Documents/secret")
        #expect(subject.next(stillOpen: admitted) == nil)
        #expect(subject.deferred == [background])
    }

    @Test func aSelectedRootPutBackStaysSelected() {
        var subject = queue(["/r/a", "/r/b"])
        _ = subject.next()
        let selectedB = subject.select("/r/b")
        #expect(selectedB)
        #expect(subject.next() == "/r/b")
        subject.putBack("/r/b")
        #expect(subject.selected.contains("/r/b"))
        #expect(subject.next(stillOpen: { _ in false }) == "/r/b")  // the user's choice is not checked again
    }
}
