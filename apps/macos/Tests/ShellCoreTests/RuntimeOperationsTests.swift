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
    private(set) var validated: [String] = []
    private(set) var finishes: [RuntimeOperations.Finish] = []
    let subject: RuntimeOperations

    init(setup: RuntimeSetup?) {
        let settings = RuntimeSettings(defaults: UserDefaults(suiteName: "shellcore-operations-\(UUID().uuidString)")!)
        let searches = self.searches
        var validate: (String) async -> (FileFingerprint?, CandidateResult) = { _ in (nil, .missing) }
        subject = RuntimeOperations(
            selection: RuntimeSelection(settings: settings, setup: setup),
            work: RuntimeOperations.Work(
                discover: { await searches.discover() },
                validate: { await validate($0) },
                tools: { Operations.tools }))
        validate = { [unowned self] path in
            validated.append(path)
            whileValidating(path)
            return (nil, results[path] ?? .missing)
        }
        subject.onFinish = { [unowned self] in finishes.append($0) }
    }

    var selection: RuntimeSelection { subject.selection }

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
    @Test func aSearchThatAdoptsARuntimeHandsOverTheFoldersThatWaited() async {
        let operations = Operations(setup: nil)
        operations.subject.beginDiscovery()
        #expect(operations.selection.isSearching)
        #expect(operations.selection.setupForOpening(folder) == nil)
        let a = runtime("/opt/a/metab")
        await operations.searches.answer(0, with: found(a))
        #expect(await operations.waitForFinishes(1))
        #expect(operations.finishes == [
            RuntimeOperations.Finish(operation: .search(found(a)), outcome: .adopted(a), released: [folder]),
        ])
        #expect(operations.selection.waitingFolders.isEmpty)
    }

    @Test func aRecheckThatRejectsTheRuntimeSearchesForAnother() async {
        let a = runtime("/opt/a/metab")
        let operations = Operations(setup: a)
        operations.results[a.runtime.executable] = .tooOld(version: "0.12.0")
        operations.subject.beginRecheck()
        #expect(await operations.waitForFinishes(1))
        #expect(operations.finishes.first?.outcome == .notFound)
        #expect(operations.selection.isSearching)
        let b = runtime("/opt/b/metab")
        await operations.searches.answer(0, with: found(b))
        #expect(await operations.waitForFinishes(2))
        #expect(operations.finishes.last?.outcome == .adopted(b))
    }

    /// The runtime's file changed while a choice was checked, which held it off; the choice
    /// was rejected, so the runtime is checked again.
    @Test func aRejectedChoiceRechecksARuntimeWhoseFileChangedMeanwhile() async {
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
        #expect(await operations.waitForFinishes(2))
        #expect(operations.validated == ["/bin/ls", a.runtime.executable])
        #expect(operations.selection.launchableSetup?.runtime.version == "0.13.0")
    }
}
