import Foundation
import Testing
@testable import ShellCore

@Suite struct WindowPreferencesTests {
    private func defaults() -> UserDefaults {
        let name = "metabrowser-tests-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: name)!
        defaults.removePersistentDomain(forName: name)
        return defaults
    }

    @Test func theLastSessionReopensByDefault() {
        #expect(WindowPreferences(defaults: defaults()).restoresLastSession)
    }

    @Test func theChoicePersists() {
        let store = defaults()
        WindowPreferences(defaults: store).restoresLastSession = false
        #expect(!WindowPreferences(defaults: store).restoresLastSession)
    }

    /// An earlier build saved where a new folder went, tabs among the choices. Every
    /// folder opens in a window of its own now, and the saved value changes nothing.
    @Test func aPlacementAnEarlierBuildSavedChangesNothing() {
        let store = defaults()
        store.set("tabs", forKey: "newFolderPlacement")
        #expect(WindowPreferences(defaults: store).restoresLastSession)
    }
}

/// No folder window takes a tab, by any path: the app never adds one, never names a
/// group for windows to tab into, and never reads the System Settings choice that would
/// put a new window in one. `FolderWindowTests` pins the windows themselves.
@Suite struct NoFolderTabsSourceTests {
    private static let sources: [(name: String, text: String)] = {
        let package = URL(filePath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent()
        let root = package.appending(path: "Sources")
        let files = FileManager.default.enumerator(at: root, includingPropertiesForKeys: nil)?
            .compactMap { $0 as? URL }.filter { $0.pathExtension == "swift" } ?? []
        return files.compactMap { file in
            (try? String(contentsOf: file, encoding: .utf8)).map { (file.lastPathComponent, $0) }
        }
    }()

    @Test func theSourcesAreFound() {
        #expect(Self.sources.contains { $0.name == "BrowserWindowController.swift" })
    }

    @Test func noSourceAddsATabOrReadsTheTabPreference() {
        for forbidden in ["addTabbedWindow", "tabbingIdentifier", "userTabbingPreference", "tabGroup", "\"newFolderPlacement\""] {
            let users = Self.sources.filter { $0.text.contains(forbidden) }.map(\.name)
            #expect(users.isEmpty, "\(forbidden) in \(users)")
        }
    }

    /// The only tabbing mode a source sets is the one that refuses tabs.
    @Test func everyTabbingModeSetIsDisallowed() throws {
        let assignment = try Regex(#"tabbingMode\s*=\s*\.(\w+)"#)
        let modes = Self.sources.flatMap { $0.text.matches(of: assignment).compactMap { $0.output[1].substring } }
        #expect(!modes.isEmpty)
        #expect(modes.allSatisfy { $0 == "disallowed" })
    }
}

@Suite struct PageDiscardPolicyTests {
    private func page(_ id: String, background: Bool = true, live: Bool = true, shown: UInt64) -> PageActivity<String> {
        PageActivity(id: id, isBackground: background, isLive: live, lastShown: shown)
    }

    @Test func backgroundPagesPastTheLimitGiveUpTheirViewsLeastRecentlyShownFirst() {
        let policy = PageDiscardPolicy(liveBackgroundPages: 2)
        let pages = [
            page("old", shown: 1), page("newest", shown: 9), page("older", shown: 0), page("newer", shown: 5),
            page("front", background: false, shown: 10),
        ]
        #expect(policy.discards(pages) == ["older", "old"])
    }

    /// A page a window shows keeps its view, minimized or not, and a discarded one has
    /// none to give up.
    @Test func shownWindowsAndDiscardedPagesAreLeftAlone() {
        let policy = PageDiscardPolicy(liveBackgroundPages: 1)
        let pages = [
            page("a", background: false, shown: 0), page("b", background: false, shown: 1),
            page("gone", live: false, shown: 2), page("kept", shown: 3),
        ]
        #expect(policy.discards(pages).isEmpty)
    }

    @Test func aLimitOfZeroDiscardsEveryBackgroundPage() {
        let policy = PageDiscardPolicy(liveBackgroundPages: 0)
        #expect(policy.discards([page("a", shown: 0), page("b", shown: 1)]) == ["a", "b"])
    }

    @Test func aNegativeLimitKeepsNone() {
        #expect(PageDiscardPolicy(liveBackgroundPages: -1).liveBackgroundPages == 0)
    }
}
