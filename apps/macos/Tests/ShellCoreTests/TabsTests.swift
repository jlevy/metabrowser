import Foundation
import Testing
@testable import ShellCore

@Suite struct FolderPlacementTests {
    @Test func tabsAndWindowsOverrideSystemSettings() {
        for system in [SystemTabbing.never, .always, .inFullScreen] {
            #expect(FolderPlacement.tabs.placement(system: system, front: .window) == .tab)
            #expect(FolderPlacement.windows.placement(system: system, front: .fullScreen) == .window)
        }
    }

    @Test func theSystemChoiceIsTheOneInSystemSettings() {
        #expect(FolderPlacement.system.placement(system: .always, front: .window) == .tab)
        #expect(FolderPlacement.system.placement(system: .never, front: .fullScreen) == .window)
        #expect(FolderPlacement.system.placement(system: .inFullScreen, front: .fullScreen) == .tab)
        #expect(FolderPlacement.system.placement(system: .inFullScreen, front: .window) == .window)
    }

    @Test func withNoFolderWindowOpenEveryFolderGetsAWindow() {
        for preference in FolderPlacement.allCases {
            #expect(preference.placement(system: .always, front: nil) == .window)
        }
    }
}

@Suite struct WindowPreferencesTests {
    private func defaults() -> UserDefaults {
        let name = "metabrowser-tests-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: name)!
        defaults.removePersistentDomain(forName: name)
        return defaults
    }

    @Test func defaultsFollowSystemSettingsAndRestoreTheSession() {
        let preferences = WindowPreferences(defaults: defaults())
        #expect(preferences.placement == .system)
        #expect(preferences.restoresLastSession)
    }

    @Test func choicesPersistAndAnUnknownValueReadsAsTheDefault() {
        let store = defaults()
        let preferences = WindowPreferences(defaults: store)
        preferences.placement = .tabs
        preferences.restoresLastSession = false
        let reread = WindowPreferences(defaults: store)
        #expect(reread.placement == .tabs)
        #expect(!reread.restoresLastSession)
        store.set("sideways", forKey: WindowPreferences.placementKey)
        #expect(reread.placement == .system)
    }
}

@Suite struct TabDiscardPolicyTests {
    private func tab(_ id: String, background: Bool = true, live: Bool = true, shown: UInt64) -> TabActivity<String> {
        TabActivity(id: id, isBackground: background, isLive: live, lastShown: shown)
    }

    @Test func backgroundTabsPastTheLimitGiveUpTheirViewsLeastRecentlyShownFirst() {
        let policy = TabDiscardPolicy(liveBackgroundTabs: 2)
        let tabs = [
            tab("old", shown: 1), tab("newest", shown: 9), tab("older", shown: 0), tab("newer", shown: 5),
            tab("front", background: false, shown: 10),
        ]
        #expect(policy.discards(tabs) == ["older", "old"])
    }

    @Test func shownWindowsAndDiscardedTabsAreLeftAlone() {
        let policy = TabDiscardPolicy(liveBackgroundTabs: 1)
        let tabs = [
            tab("a", background: false, shown: 0), tab("b", background: false, shown: 1),
            tab("gone", live: false, shown: 2), tab("kept", shown: 3),
        ]
        #expect(policy.discards(tabs).isEmpty)
    }

    @Test func aLimitOfZeroDiscardsEveryBackgroundTab() {
        let policy = TabDiscardPolicy(liveBackgroundTabs: 0)
        #expect(policy.discards([tab("a", shown: 0), tab("b", shown: 1)]) == ["a", "b"])
    }
}
