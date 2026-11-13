import Foundation
import Testing
@testable import ShellCore

/// Find Again and Choose metab… overlapping, and a search that finds nothing (review
/// findings A4, C3, and A5 on #341). The app delegate used to apply every result as it
/// arrived and kept its own copy of the runtime beside the window's.
@Suite struct RuntimeSelectionTests {
    private let tools = ToolPaths(git: "/usr/bin/git")
    private var a: RuntimeSetup {
        RuntimeSetup(runtime: Runtime(executable: "/opt/a/metab", version: "0.12.0", source: .localBin), tools: tools)
    }
    private let folder = URL(filePath: "/tmp/notes", directoryHint: .isDirectory)

    private func settings() -> RuntimeSettings {
        let suite = "shellcore-selection-\(UUID().uuidString)"
        return RuntimeSettings(defaults: UserDefaults(suiteName: suite)!)
    }

    private func found(_ setup: RuntimeSetup?) -> DiscoveryReport {
        DiscoveryReport(setup: setup, tried: [], consultedLoginShell: false)
    }

    @Test func anOlderSearchFinishingAfterAChoiceChangesNothing() {
        let saved = settings()
        let selection = RuntimeSelection(settings: saved, setup: nil)
        let search = selection.startSearch()
        let choice = selection.startChoice()
        #expect(!selection.isSearching)  // the choice overtook the search
        let chosen = selection.finishChoice(choice, path: "/opt/b/metab", result: .valid(version: "0.13.0")) { tools }
        guard case .adopted(let b) = chosen else {
            Issue.record("expected the choice to be adopted, got \(chosen)")
            return
        }
        #expect(selection.finishSearch(search, with: found(a)) == .superseded)
        #expect(selection.setup == b)
        #expect(saved.load() == b)
        #expect(!selection.isSearching)
    }

    @Test func anOlderSearchThatFoundNothingKeepsTheChoice() {
        let selection = RuntimeSelection(settings: settings(), setup: nil)
        let search = selection.startSearch()
        let choice = selection.startChoice()
        _ = selection.finishChoice(choice, path: "/opt/b/metab", result: .valid(version: "0.13.0")) { tools }
        #expect(selection.finishSearch(search, with: found(nil)) == .superseded)
        #expect(selection.setup?.runtime.executable == "/opt/b/metab")
    }

    @Test func aSearchStartedAfterAChoiceWinsOverIt() {
        let saved = settings()
        let selection = RuntimeSelection(settings: saved, setup: nil)
        let choice = selection.startChoice()
        let search = selection.startSearch()
        #expect(selection.finishSearch(search, with: found(a)) == .adopted(a))
        let late = selection.finishChoice(choice, path: "/opt/b/metab", result: .valid(version: "0.13.0")) { tools }
        #expect(late == .superseded)
        #expect(selection.setup == a)
        #expect(saved.load() == a)
    }

    @Test func aStaleRejectionIsNotReported() {
        let selection = RuntimeSelection(settings: settings(), setup: a)
        let choice = selection.startChoice()
        _ = selection.startChoice()
        #expect(selection.finishChoice(choice, path: "/bin/ls", result: .rejected("not metab")) { tools } == .superseded)
    }

    @Test func aRejectedChoiceChangesNothing() {
        let saved = settings()
        let selection = RuntimeSelection(settings: saved, setup: a)
        let choice = selection.startChoice()
        let outcome = selection.finishChoice(choice, path: "/bin/ls", result: .rejected("not metab")) { tools }
        #expect(outcome == .rejected(.rejected("not metab")))
        #expect(selection.setup == a)
        #expect(saved.load() == nil)
    }

    @Test func aChoiceKeepsTheToolsAlreadyFound() {
        let selection = RuntimeSelection(settings: settings(), setup: a)
        let choice = selection.startChoice()
        _ = selection.finishChoice(choice, path: "/opt/b/metab", result: .valid(version: "0.13.0")) { ToolPaths() }
        #expect(selection.setup?.tools == tools)
        #expect(selection.setup?.runtime.source == .chosen)
    }

    /// A5: the search found nothing, so the runtime is gone for launches too, and the
    /// next folder waits for one instead of starting the rejected `metab`.
    @Test func aSearchThatFindsNothingStopsNewFoldersUsingTheOldRuntime() {
        let selection = RuntimeSelection(settings: settings(), setup: a)
        #expect(selection.setupForOpening(folder) == a)
        let search = selection.startSearch()
        #expect(selection.finishSearch(search, with: found(nil)) == .notFound)
        #expect(selection.setup == nil)
        #expect(selection.setupForOpening(folder) == nil)
        #expect(selection.waitingFolders == [folder])
        let again = selection.startSearch()
        #expect(selection.finishSearch(again, with: found(a)) == .adopted(a))
        #expect(selection.takeWaitingFolders() == [folder])
        #expect(selection.waitingFolders.isEmpty)
    }

    @Test func aFolderAskedForTwiceWaitsOnce() {
        let selection = RuntimeSelection(settings: settings(), setup: nil)
        _ = selection.startSearch()
        #expect(selection.setupForOpening(folder) == nil)
        #expect(selection.setupForOpening(folder) == nil)
        #expect(selection.waitingFolders == [folder])
    }

    @Test func aSearchCountsAsRunningFromItsStart() {
        let selection = RuntimeSelection(settings: settings(), setup: nil)
        let search = selection.startSearch()
        #expect(selection.isSearching)
        _ = selection.finishSearch(search, with: found(nil))
        #expect(!selection.isSearching)
    }
}
