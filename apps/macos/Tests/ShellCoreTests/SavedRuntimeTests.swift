import Foundation
import Testing
@testable import ShellCore

/// What a launch starts comes from the saved setup, so the saved setup must agree with
/// the runtime the app holds in memory.
@Suite struct SavedRuntimeTests {
    private let a = RuntimeSetup(
        runtime: Runtime(executable: "/opt/a/metab", version: "0.12.0", source: .localBin),
        tools: ToolPaths(git: "/usr/bin/git"))

    private func defaults() -> UserDefaults {
        UserDefaults(suiteName: "shellcore-saved-\(UUID().uuidString)")!
    }

    /// A search that rejects every candidate leaves no runtime for this run; the next
    /// launch must not start the rejected one either, since a launch checks only that
    /// the saved file is executable.
    @Test func aSearchThatFindsNothingForgetsTheSavedRuntime() {
        let settings = RuntimeSettings(defaults: defaults())
        settings.save(a)
        let selection = RuntimeSelection(settings: settings, setup: a)
        let search = selection.startSearch()
        #expect(selection.finishSearch(search, with: DiscoveryReport(setup: nil, tried: []))
            == .notFound)
        #expect(settings.load() == nil)
        #expect(settings.usable(isExecutable: { _ in true }) == nil)
    }

    @Test func aSavedSetupThisBuildCannotReadCountsAsNone() {
        let store = defaults()
        store.set(Data(#"{"runtime": {"executable": "/opt/a/metab"}}"#.utf8), forKey: RuntimeSettings.key)
        let settings = RuntimeSettings(defaults: store)
        #expect(settings.load() == nil)
        #expect(settings.usable(isExecutable: { _ in true }) == nil)
    }
}
