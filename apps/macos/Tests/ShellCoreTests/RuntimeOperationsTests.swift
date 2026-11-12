import Foundation
import Testing
@testable import ShellCore

/// Searches that wait until the test answers them, numbered in the order they started.
private final class Searches {
    private(set) var started = 0
    private var waiting: [Int: CheckedContinuation<DiscoveryReport, Never>] = [:]

    func discover() async -> DiscoveryReport {
        let number = started
        started += 1
        return await withCheckedContinuation { waiting[number] = $0 }
    }

    /// Ends search `number` with `report`, once it is waiting.
    func answer(_ number: Int, with report: DiscoveryReport) async {
        #expect(await eventually { waiting[number] != nil }, "search \(number) never started")
        waiting.removeValue(forKey: number)?.resume(returning: report)
    }
}

/// `RuntimeOperations` with fake work: searches the test answers, validations that look
/// results up by path, and every operation's end recorded.
private final class Operations {
    static let tools = ToolPaths(git: "/usr/bin/git")
    let searches = Searches()
    /// What validating each path gives; a path not listed is missing.
    var results: [String: CandidateResult] = [:]
    /// Run as a path is validated, before its result is returned.
    var whileValidating: (String) -> Void = { _ in }
    /// Paths whose validation waits until `release(_:)`.
    var holding: Set<String> = []
    private var held: [String: CheckedContinuation<Void, Never>] = [:]
    private(set) var validated: [String] = []
    /// Where each validated path came from, as the operation said.
    private(set) var sources: [RuntimeSource] = []
    private(set) var finishes: [RuntimeOperations.Finish] = []
    let subject: RuntimeOperations

    init(setup: RuntimeSetup?) {
        let settings = RuntimeSettings(defaults: UserDefaults(suiteName: "shellcore-operations-\(UUID().uuidString)")!)
        let searches = self.searches
        var validate: (String, RuntimeSource) async -> (FileFingerprint?, CandidateResult) = { _, _ in (nil, .missing) }
        subject = RuntimeOperations(
            selection: RuntimeSelection(settings: settings, setup: setup),
            work: RuntimeOperations.Work(
                discover: { await searches.discover() },
                validate: { await validate($0, $1) },
                tools: { Operations.tools }))
        validate = { [unowned self] path, source in
            validated.append(path)
            sources.append(source)
            whileValidating(path)
            if holding.contains(path) { await withCheckedContinuation { held[path] = $0 } }
            return (nil, results[path] ?? .missing)
        }
        subject.onFinish = { [unowned self] in finishes.append($0) }
    }

    var selection: RuntimeSelection { subject.selection }

    /// Lets a held validation of `path` return, once it is waiting.
    func release(_ path: String) async {
        #expect(await eventually { held[path] != nil }, "\(path) was never validated")
        held.removeValue(forKey: path)?.resume()
    }

    func waitForFinishes(_ count: Int) async -> Bool {
        await eventually { finishes.count >= count }
    }
}

private func runtime(_ executable: String, _ version: String = "0.12.1") -> RuntimeSetup {
    RuntimeSetup(runtime: Runtime(executable: executable, version: version, source: .localBin), tools: Operations.tools)
}

private func found(_ setup: RuntimeSetup?) -> DiscoveryReport {
    DiscoveryReport(setup: setup, tried: [])
}

private let folder = URL(filePath: "/tmp/notes", directoryHint: .isDirectory)

/// The runtime's searches, rechecks, and choices, and what follows each, as the app runs
/// them (`RuntimeOperations`).
@Suite struct RuntimeOperationsTests {
    @Test func aSearchThatAdoptsARuntimeHandsOverTheFoldersThatWaited() async throws {
        let operations = Operations(setup: nil)
        operations.subject.beginDiscovery()
        #expect(operations.selection.isSearching)
        #expect(operations.selection.setupForOpening(folder) == nil)
        let a = runtime("/opt/a/metab")
        await operations.searches.answer(0, with: found(a))
        try #require(await operations.waitForFinishes(1))
        #expect(operations.finishes == [
            RuntimeOperations.Finish(operation: .search(found(a)), outcome: .adopted(a), released: [folder]),
        ])
        #expect(operations.selection.waitingFolders.isEmpty)
    }

    @Test func aRecheckThatRejectsTheRuntimeSearchesForAnother() async throws {
        let a = runtime("/opt/a/metab")
        let operations = Operations(setup: a)
        operations.results[a.runtime.executable] = .tooOld(version: "0.12.0")
        operations.subject.beginRecheck()
        try #require(await operations.waitForFinishes(1))
        #expect(operations.finishes.first?.outcome == .notFound)
        #expect(operations.selection.isSearching)
        let b = runtime("/opt/b/metab")
        await operations.searches.answer(0, with: found(b))
        try #require(await operations.waitForFinishes(2))
        #expect(operations.finishes.last?.outcome == .adopted(b))
    }

    /// The runtime's file changed while a choice was checked, which held it off; the choice
    /// was rejected, so the runtime is checked again.
    @Test func aRejectedChoiceRechecksARuntimeWhoseFileChangedMeanwhile() async throws {
        let a = runtime("/opt/a/metab")
        let operations = Operations(setup: a)
        operations.results["/bin/ls"] = .rejected("not metab")
        operations.results[a.runtime.executable] = .valid(version: "0.13.0")
        operations.whileValidating = { path in
            if path == "/bin/ls" { operations.subject.beginRecheck() }  // the watch saw the change
        }
        await operations.subject.choose("/bin/ls")
        #expect(operations.finishes.first == RuntimeOperations.Finish(
            operation: .choice("/bin/ls"), outcome: .rejected(.rejected("not metab")), released: []))
        try #require(await operations.waitForFinishes(2))
        #expect(operations.validated == ["/bin/ls", a.runtime.executable])
        #expect(operations.selection.launchableSetup?.runtime.version == "0.13.0")
    }
}

/// A choice rejected during the first search (mb-vh2z). The choice overtook the search,
/// and its rejection ended the only operation without a runtime: the search's late result
/// was dropped, nothing searched again, and the folders opened meanwhile, and the restore,
/// waited until Find Again.
@Suite struct RejectedChoiceDuringASearchTests {
    /// The review's sequence: the launch's search, a folder opened while it runs, a choice
    /// rejected, then the overtaken search's late answer.
    @Test func theSearchResumesAndItsRuntimeOpensTheFoldersThatWaited() async throws {
        let operations = Operations(setup: nil)
        operations.results["/bin/ls"] = .rejected("not metab")
        operations.subject.beginDiscovery()
        #expect(operations.selection.setupForOpening(folder) == nil)
        await operations.subject.choose("/bin/ls")
        #expect(operations.finishes == [RuntimeOperations.Finish(
            operation: .choice("/bin/ls"), outcome: .rejected(.rejected("not metab")), released: [])])
        #expect(operations.selection.isSearching, "a search runs again")
        #expect(await eventually { operations.searches.started == 2 })
        let a = runtime("/opt/a/metab")
        await operations.searches.answer(0, with: found(a))  // the overtaken search, late
        try #require(await operations.waitForFinishes(2))
        #expect(operations.finishes[1].outcome == .superseded)
        #expect(operations.selection.setup == nil)
        #expect(operations.selection.waitingFolders == [folder])
        await operations.searches.answer(1, with: found(a))
        try #require(await operations.waitForFinishes(3))
        #expect(operations.finishes[2] == RuntimeOperations.Finish(
            operation: .search(found(a)), outcome: .adopted(a), released: [folder]))
        #expect(operations.selection.waitingFolders.isEmpty)
        #expect(!operations.selection.isBusy)
    }

    /// The resumed search finds nothing: its end is the first-run steps' cue, and the
    /// folders keep waiting for the runtime a later search finds.
    @Test func aResumedSearchThatFindsNothingEndsAsAFirstSearchWould() async throws {
        let operations = Operations(setup: nil)
        operations.results["/opt/old/metab"] = .tooOld(version: "0.12.0")
        operations.subject.beginDiscovery()
        #expect(operations.selection.setupForOpening(folder) == nil)
        await operations.subject.choose("/opt/old/metab")
        await operations.searches.answer(1, with: found(nil))
        try #require(await operations.waitForFinishes(2))
        #expect(operations.finishes[1] == RuntimeOperations.Finish(
            operation: .search(found(nil)), outcome: .notFound, released: []))
        #expect(!operations.selection.isBusy)
        #expect(operations.selection.waitingFolders == [folder])
        await operations.searches.answer(0, with: found(runtime("/opt/a/metab")))  // still dropped
        try #require(await operations.waitForFinishes(3))
        #expect(operations.finishes[2].outcome == .superseded)
        operations.subject.beginDiscovery()  // Find Again, or the watch
        let b = runtime("/opt/b/metab")
        await operations.searches.answer(2, with: found(b))
        try #require(await operations.waitForFinishes(4))
        #expect(operations.finishes[3].released == [folder])
    }

    /// A choice that is adopted answers the search it overtook: nothing searches again, and
    /// the overtaken search's late result does not replace it.
    @Test func anAdoptedChoiceIsNotOverwrittenAndStartsNoSearch() async throws {
        let operations = Operations(setup: nil)
        operations.results["/opt/b/metab"] = .valid(version: "0.13.0")
        operations.subject.beginDiscovery()
        #expect(operations.selection.setupForOpening(folder) == nil)
        await operations.subject.choose("/opt/b/metab")
        #expect(operations.finishes.first?.released == [folder])
        #expect(!operations.selection.isSearching)
        #expect(await eventually { operations.searches.started == 1 })
        await operations.searches.answer(0, with: found(runtime("/opt/a/metab")))
        try #require(await operations.waitForFinishes(2))
        #expect(operations.finishes[1].outcome == .superseded)
        #expect(operations.selection.setup?.runtime.executable == "/opt/b/metab")
        #expect(operations.searches.started == 1)
    }

    /// Two choices during the search: the newer one's rejection resumes the search, and the
    /// older one, superseded when it ends, starts nothing more.
    @Test func onlyTheNewestChoicesRejectionResumesTheSearch() async throws {
        let operations = Operations(setup: nil)
        operations.results["/bin/ls"] = .rejected("not metab")
        operations.results["/bin/cat"] = .rejected("not metab")
        operations.holding = ["/bin/ls"]
        operations.subject.beginDiscovery()
        let first = Task { await operations.subject.choose("/bin/ls") }
        #expect(await eventually { operations.validated == ["/bin/ls"] })
        await operations.subject.choose("/bin/cat")  // a second choice, while the first is checked
        await operations.release("/bin/ls")
        await first.value
        #expect(operations.finishes.map(\.outcome) == [.rejected(.rejected("not metab")), .superseded])
        #expect(await eventually { operations.searches.started == 2 })
        #expect(operations.selection.isSearching)
        await operations.searches.answer(1, with: found(nil))
        try #require(await operations.waitForFinishes(3))
        #expect(operations.searches.started == 2, "one search resumed, not one per choice")
    }
}

/// When a search is owed again (`RuntimeSelection.needsSearch`), and what Settings says
/// meanwhile (`RuntimeActivity`).
@Suite struct OwedSearchTests {
    private func selection(_ setup: RuntimeSetup? = nil) -> RuntimeSelection {
        RuntimeSelection(
            settings: RuntimeSettings(defaults: UserDefaults(suiteName: "shellcore-owed-\(UUID().uuidString)")!),
            setup: setup)
    }

    @Test func aSearchOvertakenByARejectedChoiceIsOwedUntilANewOneStarts() {
        let subject = selection()
        _ = subject.startSearch()
        let choice = subject.startChoice()
        #expect(!subject.needsSearch, "not while the choice runs")
        _ = subject.finishChoice(choice, path: "/bin/ls", result: .rejected("not metab")) { Operations.tools }
        #expect(subject.needsSearch)
        _ = subject.startSearch()
        #expect(!subject.needsSearch)
    }

    @Test func anAdoptedChoiceAnswersTheSearchItOvertook() {
        let subject = selection()
        _ = subject.startSearch()
        let choice = subject.startChoice()
        _ = subject.finishChoice(choice, path: "/opt/b/metab", result: .valid(version: "0.13.0")) { Operations.tools }
        #expect(!subject.needsSearch)
    }

    /// Find Again with a runtime in use is the user's search too.
    @Test func aRejectedChoiceOwesFindAgainEvenWithARuntime() {
        let subject = selection(runtime("/opt/a/metab"))
        _ = subject.startSearch()
        let choice = subject.startChoice()
        _ = subject.finishChoice(choice, path: "/bin/ls", result: .tooOld(version: "0.12.0")) { Operations.tools }
        #expect(subject.needsSearch)
        #expect(subject.setup?.runtime.executable == "/opt/a/metab")
    }

    @Test func aChoiceThatOvertookNoSearchOwesNone() {
        let subject = selection()
        let choice = subject.startChoice()
        _ = subject.finishChoice(choice, path: "/bin/ls", result: .rejected("not metab")) { Operations.tools }
        #expect(!subject.needsSearch)
    }

    @Test func settingsSaysItIsLookingOnlyWhileASearchRuns() {
        #expect(RuntimeActivity(isSearching: true, isChoosing: false, isPreparingSteps: true) == .searching)
        #expect(RuntimeActivity(isSearching: false, isChoosing: true, isPreparingSteps: false) == .checkingChoice)
        #expect(RuntimeActivity(isSearching: false, isChoosing: false, isPreparingSteps: true) == .preparingSteps)
        #expect(RuntimeActivity(isSearching: false, isChoosing: false, isPreparingSteps: false) == .idle)
    }
}

/// A recheck runs the runtime's file again, so it is held to the check the search that
/// found it was (review D1 on #363, mb-3o3h): the watch saw the file change, and the
/// recheck ran `--version` on it whoever could change it. Only a file the user chose is
/// run as chosen.
@Suite struct RecheckTrustTests {
    private let shared = "/opt/homebrew/bin is writable by its group"

    /// The operations as the app builds them, with discovery's own validation over a fake
    /// command runner and trust check.
    private func operations(
        setup: RuntimeSetup, refused: [String: String], ran: Recorder<String>
    ) -> (RuntimeOperations, Searches) {
        let searches = Searches()
        let env = DiscoveryEnvironment(
            home: "/Volumes/Home", environment: [:], saved: nil, shell: nil,
            isExecutable: { _ in true }, canonicalPath: { $0 },
            run: { spec, _ in
                ran.append(spec.executable)
                return CommandResult(status: 0, output: ["metab 0.13.0"])
            },
            refusal: { refused[$0] })
        let subject = RuntimeOperations(
            selection: RuntimeSelection(
                settings: RuntimeSettings(defaults: UserDefaults(suiteName: "shellcore-recheck-trust-\(UUID().uuidString)")!),
                setup: setup),
            work: RuntimeOperations.Work(
                discover: { await searches.discover() },
                validate: { path, source in (nil, await RuntimeDiscovery.validate(path, env, source: source)) },
                tools: { ToolPaths() }))
        return (subject, searches)
    }

    @Test func aRecheckOfARuntimeAnotherAccountCanChangeNeverRunsIt() async {
        let homebrew = RuntimeSetup(
            runtime: Runtime(executable: "/opt/homebrew/bin/metab", version: "0.12.1", source: .homebrew),
            tools: ToolPaths())
        let ran = Recorder<String>()
        let (subject, searches) = operations(setup: homebrew, refused: ["/opt/homebrew/bin/metab": shared], ran: ran)
        var finishes: [RuntimeOperations.Finish] = []
        subject.onFinish = { finishes.append($0) }
        subject.beginRecheck()
        #expect(await eventually { finishes.count == 1 })
        #expect(finishes.first?.operation == .recheck("/opt/homebrew/bin/metab", .untrusted(shared)))
        #expect(finishes.first?.outcome == .notFound)
        #expect(ran.all.isEmpty)
        #expect(subject.selection.launchableSetup == nil)
        #expect(await eventually { searches.started == 1 }, "a search looks for another")
    }

    @Test func aRecheckOfAChosenRuntimeRunsItAsChosen() async {
        let chosen = RuntimeSetup(
            runtime: Runtime(executable: "/opt/homebrew/bin/metab", version: "0.12.1", source: .chosen),
            tools: ToolPaths())
        let ran = Recorder<String>()
        let (subject, _) = operations(setup: chosen, refused: ["/opt/homebrew/bin/metab": shared], ran: ran)
        var finishes: [RuntimeOperations.Finish] = []
        subject.onFinish = { finishes.append($0) }
        subject.beginRecheck()
        #expect(await eventually { finishes.count == 1 })
        #expect(ran.all == ["/opt/homebrew/bin/metab"])
        #expect(subject.selection.launchableSetup?.runtime.version == "0.13.0")
    }
}

/// The trust check at the moment of spawning (review A1 on #377, mb-c505). Discovery,
/// the launch's saved setup, and rechecks checked who could change the runtime's file,
/// but a start then asked only for the selected runtime, so a folder on its path made
/// writable by its group, or a link on it led elsewhere, while the start waited at the
/// launch gate still spawned it: neither changes the file's fingerprint, which is all
/// the watch compares.
@Suite struct LaunchTrustTests {
    /// A runtime the app found in `home/link/bin/metab`, where `link` leads to `opt`, and
    /// a folder server held behind a busy launch gate whose children the test counts.
    private final class Fixture {
        let directory: URL
        let home: String
        let executable: String
        let searches = Searches()
        let gate = LaunchGate()
        let spawned = Recorder<String>()
        private(set) var finishes: [RuntimeOperations.Finish] = []
        let operations: RuntimeOperations
        let server: FolderServer

        init(source: RuntimeSource = .localBin, name: String = #function) throws {
            directory = try temporaryDirectory(name)
            home = FileChecks.canonicalPath(directory.path(percentEncoded: false))
            for folder in ["opt/bin", "shared/bin"] {
                try FileManager.default.createDirectory(atPath: home + "/" + folder, withIntermediateDirectories: true)
                let metab = home + "/" + folder + "/metab"
                try Data("#!/bin/sh\necho metab 0.13.0\n".utf8).write(to: URL(filePath: metab))
                chmod(metab, 0o755)
                chmod(home + "/" + folder, 0o755)
            }
            chmod(home + "/shared", 0o775)  // its group can change what is in it
            try FileManager.default.createSymbolicLink(atPath: home + "/link", withDestinationPath: home + "/opt")
            executable = home + "/link/bin/metab"
            let setup = RuntimeSetup(
                runtime: Runtime(executable: executable, version: "0.12.1", source: source), tools: ToolPaths())
            let ran = Recorder<String>()
            let env = DiscoveryEnvironment(
                home: home, environment: [:], saved: nil, shell: nil,
                isExecutable: FileChecks.isExecutableFile, canonicalPath: FileChecks.canonicalPath,
                run: { spec, _ in
                    ran.append(spec.executable)
                    return CommandResult(status: 0, output: ["metab 0.13.0"])
                })
            let searches = self.searches
            let operations = RuntimeOperations(
                selection: RuntimeSelection(
                    settings: RuntimeSettings(defaults: UserDefaults(suiteName: "shellcore-launch-trust-\(UUID().uuidString)")!),
                    setup: setup),
                work: RuntimeOperations.Work(
                    discover: { await searches.discover() },
                    validate: { path, source in (nil, await RuntimeDiscovery.validate(path, env, source: source)) },
                    tools: { ToolPaths() }))
            self.operations = operations
            let launch = CLIServeLaunch()
            let root = URL(filePath: home + "/notes", directoryHint: .isDirectory)
            let spec = { (setup: RuntimeSetup) in launch.spec(serving: root, with: setup, inherited: [:], logURL: nil) }
            var policy = SupervisorPolicy()
            policy.startupTimeout = startupCeiling
            policy.shutdownGrace = .milliseconds(100)
            policy.probeInterval = .milliseconds(5)
            let spawned = self.spawned
            let supervisor = ServerSupervisor(
                spec: spec(setup), launch: launch, policy: policy, gate: gate,
                makeProcess: { spec in
                    spawned.append(spec.executable)
                    let child = FakeProcess(pid: pid_t(8000 + spawned.count))
                    child.say("Serving /tmp/notes at http://127.0.0.1:8412/view/")
                    return child
                },
                probe: { _ in true })
            server = FolderServer(supervisor: supervisor, accepted: { operations.launchableSetup() }, spec: spec)
            operations.onFinish = { [unowned self] in finishes.append($0) }
        }

        /// Runs `request` while the launch gate is held, makes the change once the request
        /// waits there, then opens the gate.
        func whileWaitingAtTheGate(
            _ request: @escaping () async -> FolderServer.Outcome, change: () throws -> Void
        ) async throws -> FolderServer.Outcome {
            await gate.acquire()
            let waiting = Task { await request() }
            #expect(await eventually { server.supervisor.state == .starting })
            try change()
            gate.release()
            return await waiting.value
        }

        func remove() {
            chmod(home + "/opt/bin", 0o755)
            try? FileManager.default.removeItem(at: directory)
        }
    }

    @Test func aRestoredStartSpawnsNothingOnceAFolderOnItsPathBecomesWritableByItsGroup() async throws {
        let fixture = try Fixture()
        defer { fixture.remove() }
        let server = fixture.server
        let outcome = try await fixture.whileWaitingAtTheGate({ await server.start(holding: false) }) {
            chmod(fixture.home + "/opt/bin", 0o775)
        }
        #expect(outcome == .waitingForRuntime)
        #expect(fixture.spawned.all.isEmpty)
        #expect(fixture.operations.selection.launchableSetup == nil, "held off until something validates one")
        // The recheck refuses the file too, and a search looks for another.
        #expect(await eventually { fixture.finishes.count == 1 })
        guard case .recheck(_, .untrusted(let reason))? = fixture.finishes.first?.operation else {
            Issue.record("expected a recheck that refused the file, got \(fixture.finishes)")
            return
        }
        #expect(reason.contains("can be changed by its group"))
        #expect(await eventually { fixture.searches.started == 1 })
    }

    @Test func aRestartSpawnsNothingOnceALinkOnItsPathLeadsToAFolderOthersCanChange() async throws {
        let fixture = try Fixture()
        defer { fixture.remove() }
        let server = fixture.server
        #expect(await server.start() == .launched)
        #expect(fixture.spawned.count == 1)
        let outcome = try await fixture.whileWaitingAtTheGate({ await server.restart() }) {
            try FileManager.default.removeItem(atPath: fixture.home + "/link")
            try FileManager.default.createSymbolicLink(atPath: fixture.home + "/link", withDestinationPath: fixture.home + "/shared")
        }
        #expect(outcome == .waitingForRuntime)
        #expect(fixture.spawned.count == 1, "no replacement child")
        #expect(server.held == .restart)
        #expect(await eventually { fixture.searches.started == 1 })
        await server.supervisor.shutDown()
    }

    /// A file the user chose is run as chosen, at its launches too.
    @Test func aChosenRuntimeStillLaunches() async throws {
        let fixture = try Fixture(source: .chosen)
        defer { fixture.remove() }
        let server = fixture.server
        let outcome = try await fixture.whileWaitingAtTheGate({ await server.start(holding: false) }) {
            chmod(fixture.home + "/opt/bin", 0o775)
        }
        #expect(outcome == .launched)
        #expect(fixture.spawned.all == [fixture.executable])
        #expect(fixture.searches.started == 0)
        await server.supervisor.shutDown()
    }

    /// Nothing changed: the start spawns, after one check at the gate.
    @Test func anUnchangedRuntimeLaunches() async throws {
        let fixture = try Fixture()
        defer { fixture.remove() }
        let server = fixture.server
        let outcome = try await fixture.whileWaitingAtTheGate({ await server.start(holding: false) }) {}
        #expect(outcome == .launched)
        #expect(fixture.spawned.all == [fixture.executable])
        #expect(fixture.operations.selection.launchableSetup != nil)
        await server.supervisor.shutDown()
    }
}
