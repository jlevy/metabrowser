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

    init(root: String, runtime: @escaping () -> RuntimeSetup?, served: Recorder<String>) {
        self.root = root
        let launch = CLIServeLaunch()
        let url = URL(filePath: root, directoryHint: .isDirectory)
        let spec = { (setup: RuntimeSetup) in launch.spec(serving: url, with: setup, inherited: [:], logURL: nil) }
        var policy = SupervisorPolicy()
        policy.startupTimeout = startupCeiling
        policy.shutdownGrace = .milliseconds(100)
        policy.probeInterval = .milliseconds(5)
        let supervisor = ServerSupervisor(
            spec: spec(RestoreHarness.setup), launch: launch, policy: policy,
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
    /// The root each spawned child serves, in spawn order.
    let served = Recorder<String>()
    /// The runtime the app has: what a server starts from, and what a session needs.
    var runtime: RuntimeSetup? = RestoreHarness.setup
    private(set) var tabs: [String] = []
    private(set) var events: [RestoreRun.Event] = []
    private(set) var deferredAtLaunch: Set<String> = []
    private(set) var run: RestoreRun!

    init(_ saved: SavedSession, home: String) {
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
            admit: { RootAdmission.admit($0, home: home) })
        run.onEvent = { [unowned self] in self.events.append($0) }
    }

    func folder(_ path: String) -> TestFolder? { fleet[path] as? TestFolder }

    @discardableResult
    func make(_ path: String) -> TestFolder {
        let made = TestFolder(root: path, runtime: { [unowned self] in self.runtime }, served: served)
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
