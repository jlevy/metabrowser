import Darwin
import Foundation
import Testing
@testable import ShellCore

/// A restored folder's session as the app makes one, without a window: a real
/// `FolderServer` and supervisor over fake children, which record the root each launch
/// was asked to serve.
private final class TestFolder: RestoredFolder, ManagedServer {
    let root: String
    let server: FolderServer

    init(root: String, runtime: @escaping () -> RuntimeSetup?, served: Recorder<String>, gate: LaunchGate? = nil) {
        self.root = root
        let launch = CLIServeLaunch()
        let url = URL(filePath: root, directoryHint: .isDirectory)
        let spec = { (setup: RuntimeSetup) in launch.spec(serving: url, with: setup, inherited: [:], logURL: nil) }
        var policy = SupervisorPolicy()
        policy.startupTimeout = startupCeiling
        policy.shutdownGrace = .milliseconds(100)
        policy.probeInterval = .milliseconds(5)
        let supervisor = ServerSupervisor(
            spec: spec(RestoreHarness.setup), launch: launch, policy: policy, gate: gate,
            makeProcess: { spec in
                var root = spec.arguments[0]  // a folder URL's path, which ends in a slash
                while root.count > 1, root.hasSuffix("/") { root.removeLast() }
                served.append(root)
                let child = FakeProcess(pid: pid_t(7000 + served.count))
                child.say("Serving \(root) at http://127.0.0.1:\(8411 + served.count)/view/")
                return child
            },
            probe: { _ in true })
        server = FolderServer(supervisor: supervisor, accepted: runtime, spec: spec)
    }

    var launchCheck: (() -> Bool)? {
        get { server.rootCheck }
        set { server.rootCheck = newValue }
    }

    var isRuntimeAccepted: Bool { server.isRuntimeAccepted }
    func startRestored() async -> FolderServer.Outcome { await server.start(holding: false) }
    func shutDown() async { await server.supervisor.shutDown() }
    var childPIDs: [pid_t] { server.supervisor.childPIDs }
}

/// What a launch does with a saved session, without windows: each tab's root admitted
/// (`SavedSession.admitted`), one session per root in a `ServerFleet`, and the restore's
/// starts (`RestoreRun`). `tabs` stands in for the windows, holding each tab's root.
private final class RestoreHarness {
    static let setup = RuntimeSetup(
        runtime: Runtime(executable: "/opt/metab", version: "0.12.1", source: .localBin), tools: ToolPaths())

    let home: String
    let fleet = ServerFleet()
    /// The launch gate the roots in `gated` wait at, as behind another server starting.
    let gate = LaunchGate()
    private let gated: Set<String>
    /// The root each spawned child serves, in spawn order.
    let served = Recorder<String>()
    /// The runtime the app has: what a server starts from, and what a session needs.
    var runtime: RuntimeSetup? = RestoreHarness.setup
    private(set) var tabs: [String] = []
    private(set) var events: [RestoreRun.Event] = []
    private(set) var deferredAtLaunch: Set<String> = []
    private(set) var run: RestoreRun!

    init(_ saved: SavedSession, home: String, gated: Set<String> = []) {
        self.gated = gated
        self.home = home
        let admitted = saved.admitted { RootAdmission.admit($0, home: home) }
        deferredAtLaunch = admitted.deferred
        for root in admitted.session.windows.flatMap({ $0.tabs.map(\.root) }) {
            tabs.append(root)
            if folder(root) == nil { make(root) }
        }
        run = RestoreRun(
            RestoreQueue(admitted.session, isProtected: admitted.deferred.contains),
            folder: { [unowned self] in self.folder($0) },
            admit: { RootAdmission.admit($0, home: home) },
            moveTabs: { [unowned self] in self.moveTabs($0, to: $1) })
        run.onEvent = { [unowned self] in self.events.append($0) }
    }

    func folder(_ path: String) -> TestFolder? { fleet[path] as? TestFolder }

    /// What `FolderWindows` does when a selected root now leads to another folder: each
    /// tab of `saved` becomes a tab of `canonical`'s session, the open one or a new one,
    /// and `saved`'s session, left with no tab, closes. No session can be made without a
    /// runtime, as `AppDelegate.session(for:)` needs one.
    func moveTabs(_ saved: String, to canonical: String) -> Bool {
        guard folder(canonical) != nil || runtime != nil else { return false }
        if folder(canonical) == nil { make(canonical) }
        tabs = tabs.map { $0 == saved ? canonical : $0 }
        if let old = folder(saved) {
            fleet.retire(old)
            run.folderClosed(saved)
        }
        return true
    }

    /// What `AppDelegate.request` does with a folder or a file: the open session that
    /// shows it (`OpenTarget`), or a new one, started.
    func open(_ path: String) async -> TestFolder? {
        let canonical = FileChecks.canonicalPath(path)
        guard let target = OpenTarget.resolve(canonical, kind: OpenTarget.Kind(of: canonical), openRoots: roots)
        else { return nil }
        if let open = folder(target.root) { return open }
        let made = make(target.root)
        await made.server.start()
        return made
    }

    @discardableResult
    func make(_ path: String) -> TestFolder {
        let made = TestFolder(
            root: path, runtime: { [unowned self] in self.runtime }, served: served,
            gate: gated.contains(path) ? gate : nil)
        fleet.insert(made, for: path)
        return made
    }

    /// The roots with an open session.
    var roots: [String] { fleet.openServers.compactMap { ($0 as? TestFolder)?.root }.sorted() }

    /// Selects a tab of `path`, as `FolderWindows.windowShown` does, and waits for the run
    /// that starts.
    func select(_ path: String) async {
        if run.select(path) { await run.start() }
    }

    func stopAll() async { await fleet.stopAll() }
}

/// The folders a test restores: a temporary home with `notes`, `wrk/a`, `wrk/b` holding
/// `plan.md`, and `Documents/b`.
private struct Folders {
    let directory: URL
    let home: String
    var notes: String { home + "/notes" }
    var a: String { home + "/wrk/a" }
    var b: String { home + "/wrk/b" }
    var documentsB: String { home + "/Documents/b" }

    init(_ name: String = #function) throws {
        directory = try temporaryDirectory(name)
        home = FileChecks.canonicalPath(directory.path(percentEncoded: false))
        for folder in ["notes", "wrk/a", "wrk/b", "Documents/b"] {
            try FileManager.default.createDirectory(atPath: home + "/" + folder, withIntermediateDirectories: true)
        }
        try Data("# plan\n".utf8).write(to: URL(filePath: b + "/plan.md"))
    }

    /// Replaces the folder at `path` with a symbolic link to `target`.
    func relink(_ path: String, to target: String) throws {
        try FileManager.default.moveItem(atPath: path, toPath: path + "-moved")
        try FileManager.default.createSymbolicLink(atPath: path, withDestinationPath: target)
    }

    func remove() { try? FileManager.default.removeItem(at: directory) }
}

private func window(_ roots: [String], selected: Int = 0) -> SavedSession {
    SavedSession(windows: [SavedWindow(tabs: roots.map { SavedTab(root: $0, page: nil) }, selected: selected, frame: nil)])
}

/// The restore's starts, as the app runs them (`RestoreRun`).
@Suite struct RestoreRunTests {
    @Test func rootsStartInOrderAndAProtectedRootOnlyOnceItsTabIsSelected() async throws {
        let folders = try Folders()
        defer { folders.remove() }
        let restore = RestoreHarness(window([folders.notes, folders.documentsB, folders.b]), home: folders.home)
        await restore.run.start()
        #expect(restore.served.all == [folders.notes, folders.b])
        #expect(restore.run.queue.deferred == [folders.documentsB])
        await restore.select(folders.documentsB)
        #expect(restore.served.all == [folders.notes, folders.b, folders.documentsB])
        await restore.stopAll()
    }

    @Test func aBackgroundRootRelinkedBeforeItsTurnWaitsForItsTab() async throws {
        let folders = try Folders()
        defer { folders.remove() }
        let restore = RestoreHarness(window([folders.notes, folders.a]), home: folders.home)
        try folders.relink(folders.a, to: folders.documentsB)
        await restore.run.start()
        #expect(restore.served.all == [folders.notes])
        #expect(restore.events == [.changedBeforeItsTurn(folders.a)])
        #expect(restore.run.queue.deferred == [folders.a])
        await restore.stopAll()
    }

    @Test func aRestoreWithoutARuntimePausesAndCarriesOnInOrderOnceOneIsAccepted() async throws {
        let folders = try Folders()
        defer { folders.remove() }
        let restore = RestoreHarness(window([folders.notes, folders.b]), home: folders.home)
        restore.runtime = nil
        await restore.run.start()
        #expect(restore.served.all == [])
        #expect(restore.events == [.waitingForRuntime([folders.notes, folders.b])])
        restore.runtime = RestoreHarness.setup
        await restore.run.start()  // paused: nothing starts before the runtime is accepted
        #expect(restore.served.all == [])
        #expect(restore.run.runtimeAccepted())
        await restore.run.start()
        #expect(restore.served.all == [folders.notes, folders.b])
        await restore.stopAll()
    }
}

/// A restored root that waited under the path it was saved with, and now leads to another
/// folder (mb-kdku). Selecting its tab only cleared its check, so its server served the
/// other folder under the saved spelling: opening that folder, or a file in it, started
/// a second server, and so did selecting the tab when that folder was restored too.
@Suite struct RestoredAliasTests {
    /// The review's trace: save A, quit, replace A with a link to B, restore, select A,
    /// then open B and files in it, directly and through the link.
    @Test func aDeferredRootLeadingToAnotherFolderJoinsItAndOpeningThatFolderReusesIt() async throws {
        let folders = try Folders()
        defer { folders.remove() }
        try folders.relink(folders.a, to: folders.b)
        let restore = RestoreHarness(window([folders.notes, folders.a]), home: folders.home)
        #expect(restore.deferredAtLaunch == [folders.a])
        await restore.run.start()
        #expect(restore.served.all == [folders.notes])
        await restore.select(folders.a)
        #expect(restore.served.all == [folders.notes, folders.b])
        #expect(restore.tabs == [folders.notes, folders.b])
        #expect(restore.roots == [folders.notes, folders.b].sorted())
        let joined = try #require(restore.folder(folders.b))
        for path in [folders.b, folders.b + "/plan.md", folders.a, folders.a + "/plan.md"] {
            let shown = await restore.open(path)
            #expect(shown === joined, "\(path)")
        }
        #expect(restore.served.all == [folders.notes, folders.b])
        #expect(restore.fleet.childPIDs.count == 2)
        await restore.stopAll()
    }

    @Test func aDeferredRootLeadingToARestoredFolderJoinsItsRunningServer() async throws {
        let folders = try Folders()
        defer { folders.remove() }
        try folders.relink(folders.a, to: folders.b)
        let restore = RestoreHarness(window([folders.notes, folders.b, folders.a]), home: folders.home)
        await restore.run.start()
        #expect(restore.served.all == [folders.notes, folders.b])
        let running = try #require(restore.folder(folders.b))
        await restore.select(folders.a)
        #expect(restore.served.all == [folders.notes, folders.b])
        #expect(restore.tabs == [folders.notes, folders.b, folders.b])
        #expect(restore.folder(folders.b) === running)
        #expect(restore.roots == [folders.notes, folders.b].sorted())
        await restore.stopAll()
    }

    /// The folder it leads to waits for its own tab, in a protected location: it starts
    /// once, now, as the user's choice.
    @Test func aDeferredRootLeadingToAFolderWaitingForItsTabStartsThatFolderOnce() async throws {
        let folders = try Folders()
        defer { folders.remove() }
        try folders.relink(folders.a, to: folders.documentsB)
        let restore = RestoreHarness(window([folders.notes, folders.documentsB, folders.a]), home: folders.home)
        await restore.run.start()
        #expect(restore.served.all == [folders.notes])
        #expect(Set(restore.run.queue.deferred) == [folders.documentsB, folders.a])
        await restore.select(folders.a)
        #expect(restore.served.all == [folders.notes, folders.documentsB])
        #expect(restore.run.queue.deferred.isEmpty)
        #expect(restore.tabs == [folders.notes, folders.documentsB, folders.documentsB])
        await restore.select(folders.documentsB)  // its own tab, now: nothing more starts
        #expect(restore.served.all == [folders.notes, folders.documentsB])
        await restore.stopAll()
    }

    /// The front tab is selected, so it starts at launch, also when it waited for want of a
    /// certain identity: under the folder its path leads to.
    @Test func theFrontTabLeadingToAnotherFolderStartsThatFolder() async throws {
        let folders = try Folders()
        defer { folders.remove() }
        try folders.relink(folders.a, to: folders.b)
        let restore = RestoreHarness(window([folders.a, folders.notes]), home: folders.home)
        await restore.run.start()
        #expect(restore.served.all == [folders.b, folders.notes])
        #expect(restore.tabs == [folders.b, folders.notes])
        #expect(restore.roots == [folders.notes, folders.b].sorted())
        await restore.stopAll()
    }

    /// Without a runtime no session can be made for the folder, so the restore waits for
    /// one with the root at its front, and moves it once one is accepted.
    @Test func withoutARuntimeTheMoveWaitsForOne() async throws {
        let folders = try Folders()
        defer { folders.remove() }
        try folders.relink(folders.a, to: folders.b)
        let restore = RestoreHarness(window([folders.notes, folders.a]), home: folders.home)
        await restore.run.start()
        restore.runtime = nil
        await restore.select(folders.a)
        #expect(restore.events == [.waitingForRuntime([folders.a])])
        #expect(restore.served.all == [folders.notes])
        restore.runtime = RestoreHarness.setup
        #expect(restore.run.runtimeAccepted())
        await restore.run.start()
        #expect(restore.served.all == [folders.notes, folders.b])
        #expect(restore.tabs == [folders.notes, folders.b])
        await restore.stopAll()
    }
}

@Suite struct RootActivationTests {
    @Test func aPathThatStillNamesItsFolderStartsAsSaved() throws {
        let folders = try Folders()
        defer { folders.remove() }
        #expect(RootActivation.resolve(folders.b) == nil)
    }

    @Test func aPathThatLeadsThroughALinkToAnotherFolderResolvesToIt() throws {
        let folders = try Folders()
        defer { folders.remove() }
        try folders.relink(folders.a, to: folders.b)
        #expect(RootActivation.resolve(folders.a) == folders.b)
        // A link higher up the path counts too.
        try folders.relink(folders.home + "/wrk", to: folders.home + "/Documents")
        #expect(RootActivation.resolve(folders.home + "/wrk/b") == folders.documentsB)
    }

    /// Its server then says what it finds, as before.
    @Test func aPathThatLeadsToNoFolderStartsAsSaved() throws {
        let folders = try Folders()
        defer { folders.remove() }
        #expect(RootActivation.resolve(folders.home + "/gone") == nil)
        try folders.relink(folders.a, to: folders.b + "/plan.md")
        #expect(RootActivation.resolve(folders.a) == nil)
    }

    @Test func aFolderThatCannotBeServedIsNotJoined() {
        let resolved = RootActivation.resolve("/x", canonicalPath: { _ in "/y\nServing" }, isFolder: { _ in true })
        #expect(resolved == nil)
    }
}

@Suite struct RestoreRedirectTests {
    /// Pending `/f`, `/a`, `/b`, and `/c` waiting for its tab; `/f` started.
    private func queue() -> RestoreQueue {
        var queue = RestoreQueue(
            SavedSession(windows: [
                SavedWindow(tabs: ["/f", "/a", "/b", "/c"].map { SavedTab(root: $0, page: nil) }, selected: 0, frame: nil),
            ]),
            isProtected: { $0 == "/c" })
        let front = queue.next()
        queue.finish(front!)
        return queue
    }

    @Test func aRootWaitingToStartStartsNextAsTheUsersChoice() {
        var subject = queue()
        _ = subject.select("/a")
        #expect(subject.next() == "/a")
        subject.redirect("/a", to: "/b", isOpen: true)
        #expect(subject.pending == ["/b"])
        #expect(subject.selected.contains("/b") && !subject.selected.contains("/a"))
        // One waiting for its tab starts too, unchecked.
        #expect(subject.next() == "/b")
        subject.redirect("/b", to: "/c", isOpen: true)
        #expect(subject.pending == ["/c"])
        #expect(subject.deferred.isEmpty)
        #expect(subject.next(stillOpen: { _ in false }) == "/c")
    }

    @Test func aFolderWithNoSessionStartsNextAndAnOpenOneOutsideTheRestoreIsLeftAsItIs() {
        var subject = queue()
        subject.redirect("/a", to: "/elsewhere", isOpen: false)
        #expect(subject.pending == ["/elsewhere", "/b"])
        #expect(subject.selected.contains("/elsewhere"))
        subject.redirect("/b", to: "/open", isOpen: true)
        #expect(subject.pending == ["/elsewhere"])
        #expect(!subject.selected.contains("/open"))
    }
}

/// A tab selected while its root's start waited at the launch gate (review A2 on #377,
/// mb-x5yz). The selection cleared the root's check, but the queue does not hand out a
/// root whose start is outstanding again, so its saved path was never resolved: when the
/// gate opened, the saved spelling spawned, serving the folder it now leads to under the
/// saved key, and opening that folder or a file in it started a second server.
@Suite struct SelectedWhileWaitingTests {
    /// The review's sequence: background A waits behind another server at the gate, A is
    /// replaced by a link to B, A's tab is selected, then the gate opens.
    @Test func aRootThatNowLeadsElsewhereJoinsThatFolderBeforeAnyChildSpawns() async throws {
        let folders = try Folders()
        defer { folders.remove() }
        let restore = RestoreHarness(window([folders.notes, folders.a]), home: folders.home, gated: [folders.a])
        let a = try #require(restore.folder(folders.a))
        await restore.gate.acquire()  // another folder's server is starting
        let running = Task { await restore.run.start() }
        #expect(await eventually { restore.served.all == [folders.notes] && a.server.supervisor.state == .starting })
        try folders.relink(folders.a, to: folders.b)
        await restore.select(folders.a)
        restore.gate.release()
        await running.value
        #expect(restore.served.all == [folders.notes, folders.b])
        #expect(restore.tabs == [folders.notes, folders.b], "the saved session names the folder")
        #expect(restore.roots == [folders.notes, folders.b].sorted())
        let joined = try #require(restore.folder(folders.b))
        for path in [folders.b, folders.b + "/plan.md", folders.a + "/plan.md"] {
            let shown = await restore.open(path)
            #expect(shown === joined, "\(path)")
        }
        #expect(restore.served.all == [folders.notes, folders.b])
        await restore.stopAll()
    }

    /// A root selected at the gate whose path still names its folder starts once, as saved.
    @Test func aRootThatStillNamesItsFolderStartsOnceAsSaved() async throws {
        let folders = try Folders()
        defer { folders.remove() }
        let restore = RestoreHarness(window([folders.notes, folders.a]), home: folders.home, gated: [folders.a])
        let a = try #require(restore.folder(folders.a))
        await restore.gate.acquire()
        let running = Task { await restore.run.start() }
        #expect(await eventually { restore.served.all == [folders.notes] && a.server.supervisor.state == .starting })
        await restore.select(folders.a)
        restore.gate.release()
        await running.value
        #expect(restore.served.all == [folders.notes, folders.a])
        #expect(restore.tabs == [folders.notes, folders.a])
        #expect(restore.events.isEmpty)
        await restore.stopAll()
    }
}
