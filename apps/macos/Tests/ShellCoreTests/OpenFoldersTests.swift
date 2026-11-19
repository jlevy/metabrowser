import Foundation
import Testing
@testable import ShellCore

@Suite struct OpenFoldersTests {
    @Test func foldersKeepTheOrderTheyOpenedInHoweverTheyAreShown() {
        var open = OpenFolders()
        open.open("/a")
        open.open("/b")
        open.show("/c")
        open.show("/a")
        open.open("/b")
        #expect(open.inOrderOpened == ["/a", "/b", "/c"])
    }

    @Test func recencyPutsTheLastShownFirstAndTheNeverShownLastInOpenOrder() {
        var open = OpenFolders()
        for root in ["/a", "/b", "/c", "/d"] { open.open(root) }
        open.show("/c")
        open.show("/a")
        #expect(open.byRecency == ["/a", "/c", "/b", "/d"])
        open.show("/c")
        #expect(open.byRecency == ["/c", "/a", "/b", "/d"])
    }

    @Test func aClosedFolderLeavesBothOrdersAndReopensAtTheEnd() {
        var open = OpenFolders()
        for root in ["/a", "/b", "/c"] { open.show(root) }
        open.close("/a")
        #expect(open.inOrderOpened == ["/b", "/c"])
        #expect(open.byRecency == ["/c", "/b"])
        open.open("/a")
        #expect(open.inOrderOpened == ["/b", "/c", "/a"])
        #expect(open.byRecency == ["/c", "/b", "/a"])
        #expect(!open.contains("/d"))
    }

    @Test func aPageSwitchedAwayFromIsKeptOnlyWhenItIsItsFoldersLast() {
        #expect(SwitchedAwayPage.fate(otherPages: 0) == .keepInBackground)
        #expect(SwitchedAwayPage.fate(otherPages: 1) == .close)
        #expect(SwitchedAwayPage.fate(otherPages: 3) == .close)
    }
}

@Suite struct CloseFolderTests {
    private typealias Step = CloseFolderStep<String>

    private func window(_ id: String, onScreen: Bool = true, sheet: Bool = false) -> SwitchingWindow<String> {
        SwitchingWindow(id: id, isOnScreen: onScreen, hasSheet: sheet)
    }

    private func folders(_ shown: [String]) -> OpenFolders {
        var open = OpenFolders()
        for root in shown { open.show(root) }
        return open
    }

    @Test func aWindowShowsTheBackgroundFolderShownMostRecently() {
        let open = folders(["/a", "/b", "/c", "/d"])
        // /d is closing; /c is shown in another window, so only /a and /b are background.
        #expect(open.closing("/d", windows: [window("w")], background: ["/a", "/b"]) == .steps([Step(window: "w", showing: "/b")]))
    }

    @Test func withNoFolderInTheBackgroundEveryWindowCloses() {
        let open = folders(["/a", "/d"])
        #expect(open.closing("/d", windows: [window("w"), window("v")], background: [])
            == .steps([Step(window: "w", showing: nil), Step(window: "v", showing: nil)]))
        // The folder that closes is never its own replacement, even if it reads as background.
        #expect(open.closing("/d", windows: [window("w")], background: ["/d"]) == .steps([Step(window: "w", showing: nil)]))
    }

    @Test func eachWindowTakesTheNextBackgroundFolderUntilNoneIsLeft() {
        let open = folders(["/a", "/b", "/c", "/d"])
        let plan = open.closing("/d", windows: [window("front"), window("middle"), window("back")], background: ["/a", "/b"])
        #expect(plan == .steps([
            Step(window: "front", showing: "/b"), Step(window: "middle", showing: "/a"), Step(window: "back", showing: nil),
        ]))
    }

    /// The windows on screen take the folders shown most recently; a tab hidden behind
    /// another of its group comes after them, whatever order it was given in.
    @Test func windowsOnScreenComeBeforeHiddenTabs() {
        let open = folders(["/a", "/b", "/d"])
        let plan = open.closing("/d", windows: [window("hidden", onScreen: false), window("shown")], background: ["/a", "/b"])
        #expect(plan == .steps([Step(window: "shown", showing: "/b"), Step(window: "hidden", showing: "/a")]))
    }

    /// A repository is keyed by its URL, which is no path, and is a replacement like any
    /// folder.
    @Test func aRepositoryInTheBackgroundIsAReplacement() {
        let repository = "https://github.com/o/r"
        let open = folders(["/Volumes/Home/f", repository, "/Volumes/Home/a"])
        let plan = open.closing("/Volumes/Home/a", windows: [window("w")], background: ["/Volumes/Home/f", repository])
        #expect(plan == .steps([Step(window: "w", showing: repository)]))
    }

    /// A sheet on any window of the folder holds up the whole close, so the folder never
    /// stays open in some windows and closes in others.
    @Test func aSheetOnAnyOfItsWindowsHoldsUpTheClose() {
        let open = folders(["/a", "/d"])
        let windows = [window("w"), window("sheet", sheet: true), window("tab", onScreen: false, sheet: true)]
        #expect(open.closing("/d", windows: windows, background: ["/a"]) == .refused(["sheet", "tab"]))
    }
}

@Suite struct FolderSwitchTests {
    private func window(onScreen: Bool = true, sheet: Bool = false) -> SwitchingWindow<Int> {
        SwitchingWindow(id: 1, isOnScreen: onScreen, hasSheet: sheet)
    }

    @Test func aWindowWithASheetOpenDoesNotSwitch() {
        #expect(FolderSwitch.decide(window(sheet: true), showsFolder: false, leftFolderPages: 1) == .refused)
        #expect(FolderSwitch.decide(window(onScreen: false, sheet: true), showsFolder: false, leftFolderPages: 2) == .refused)
    }

    @Test func aWindowShowingTheFolderAlreadyChangesNothing() {
        #expect(FolderSwitch.decide(window(), showsFolder: true, leftFolderPages: 1) == .alreadyShown)
        #expect(FolderSwitch.decide(window(sheet: true), showsFolder: true, leftFolderPages: 1) == .alreadyShown)
    }

    /// The page left behind stays in the background only as its folder's last page.
    @Test func thePageLeftBehindStaysOnlyAsItsFoldersLast() {
        #expect(FolderSwitch.decide(window(), showsFolder: false, leftFolderPages: 1)
            == .show(left: .keepInBackground, countsAsShown: true))
        #expect(FolderSwitch.decide(window(), showsFolder: false, leftFolderPages: 2) == .show(left: .close, countsAsShown: true))
    }

    /// A hidden tab switches without counting its new folder as shown, so it revives no
    /// page and starts no restored folder until its tab is selected.
    @Test func aHiddenTabSwitchesWithoutCountingAsShown() {
        #expect(FolderSwitch.decide(window(onScreen: false), showsFolder: false, leftFolderPages: 3)
            == .show(left: .close, countsAsShown: false))
    }
}

@Suite struct MovedPageTests {
    /// A folder whose only page is in the background moves it to a target with no page,
    /// so the target is not left with a server and no page.
    @Test func aBackgroundPageMovesToATargetWithNoPage() {
        let plan = MovedPage.plan([false], into: [])
        #expect(plan.pages == [.moveToBackground])
        #expect(!plan.closesTargetBackgroundPages)
    }

    @Test func aBackgroundPageClosesWhenTheTargetHasAPageAlready() {
        #expect(MovedPage.plan([false], into: [true]).pages == [.close])
        // The target in the background keeps its own page.
        let plan = MovedPage.plan([false], into: [false])
        #expect(plan.pages == [.close])
        #expect(!plan.closesTargetBackgroundPages)
    }

    @Test func pagesInWindowsReplaceTheirWindowsAndTheTargetsBackgroundPageCloses() {
        let plan = MovedPage.plan([true, true], into: [false])
        #expect(plan.pages == [.replaceInWindow, .replaceInWindow])
        #expect(plan.closesTargetBackgroundPages)
        #expect(!MovedPage.plan([true], into: []).closesTargetBackgroundPages)
        #expect(!MovedPage.plan([true], into: [true]).closesTargetBackgroundPages)
    }

    /// At most one page ends in the target's background, and none once a window shows it.
    @Test func theTargetKeepsAtMostOneBackgroundPage() {
        #expect(MovedPage.plan([false, false], into: []).pages == [.moveToBackground, .close])
        #expect(MovedPage.plan([false, true], into: []).pages == [.close, .replaceInWindow])
    }
}

@Suite struct BackgroundFoldersInTheSavedSessionTests {
    private func window(_ roots: [String], selected: Int = 0) -> SavedWindow {
        SavedWindow(tabs: roots.map { SavedTab(root: $0, page: nil) }, selected: selected, frame: nil)
    }

    private func tab(_ root: String) -> SavedTab { SavedTab(root: root, page: nil) }

    @Test func aFileSavedBeforeBackgroundFoldersReadsAsHavingNone() throws {
        let json = #"{"windows":[{"tabs":[{"root":"/a"}],"selected":0}]}"#
        let session = try JSONDecoder().decode(SavedSession.self, from: Data(json.utf8))
        #expect(session == SavedSession(windows: [window(["/a"])]))
    }

    @Test func backgroundFoldersSurviveASaveAndALoad() throws {
        let directory = FileManager.default.temporaryDirectory.appending(path: "metabrowser-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: directory) }
        let store = SessionStore(directory: directory)
        let session = SavedSession(
            windows: [window(["/a"])],
            background: [SavedTab(root: "/b", page: .view(of: "notes.md")), tab("/c")])
        try store.save(session)
        #expect(try store.load() == session)
    }

    @Test func backgroundFoldersAreAdmittedAndDroppedWhenGoneShownOrRepeated() {
        let session = SavedSession(
            windows: [window(["/a"])],
            background: [tab("/b"), tab("/gone"), tab("/a"), tab("/alias-of-b"), tab("/protected"), tab("/c")])
        let admitted = session.admitted { root in
            switch root {
            case "/gone": .gone
            case "/alias-of-b": .open("/b")
            case "/protected": .deferred("/protected")
            default: .open(root)
            }
        }
        #expect(admitted.session.background.map(\.root) == ["/b", "/protected", "/c"])
        #expect(admitted.deferred == ["/protected"])
    }

    @Test func theBudgetCountsBackgroundFoldersAfterEveryWindowTab() {
        let session = SavedSession(
            windows: [window(["/a", "/b"]), window(["/c"])], background: [tab("/d"), tab("/e"), tab("/f")])
        #expect(session.tabCount == 6)
        let limited = session.limited(to: RestoreBudget(windows: 5, tabs: 4))
        #expect(limited.windows.count == 2)
        #expect(limited.background.map(\.root) == ["/d"])
        #expect(session.limited(to: RestoreBudget(windows: 5, tabs: 2)).background.isEmpty)
    }

    @Test func theFoldersOpenInTheOrderTheWindowsStandInThenTheBackgroundOnes() {
        let session = SavedSession(
            windows: [window(["/a", "/b", "/a"]), window(["/c", "/b"])], background: [tab("/d"), tab("/e")])
        #expect(session.roots == ["/a", "/b", "/c", "/d", "/e"])
    }

    /// A session with folders in the background and no window would open to nothing: the
    /// background folder shown most recently, listed first, gets a window and starts first.
    @Test func aSessionWithNoWindowShowsItsFirstBackgroundFolder() {
        let saved = SavedSession(windows: [], background: [SavedTab(root: "/b", page: .view(of: "notes.md")), tab("/c")])
        let session = saved.withFrontWindow
        #expect(session == SavedSession(
            windows: [SavedWindow(tabs: [SavedTab(root: "/b", page: .view(of: "notes.md"))], selected: 0, frame: nil)],
            background: [tab("/c")]))
        #expect(session.tabCount == saved.tabCount)
        var queue = RestoreQueue(session, isProtected: { _ in true })
        #expect(queue.selected == ["/b"])
        #expect(queue.deferred == ["/c"])
        let next = queue.next()
        #expect(next == "/b")
    }

    /// Every saved window's folder gone, the background ones remain: one of them is shown.
    @Test func aSessionWhoseWindowsAreAllGoneShowsABackgroundFolder() {
        let saved = SavedSession(windows: [window(["/gone"])], background: [tab("/b")])
        let admitted = saved.admitted { $0 == "/gone" ? .gone : .open($0) }
        #expect(admitted.session.withFrontWindow.windows.map { $0.tabs.map(\.root) } == [["/b"]])
        #expect(admitted.session.withFrontWindow.background.isEmpty)
    }

    @Test func aSessionWithAWindowOrNothingIsLeftAsItIs() {
        let session = SavedSession(windows: [window(["/a"])], background: [tab("/b")])
        #expect(session.withFrontWindow == session)
        #expect(SavedSession(windows: []).withFrontWindow == SavedSession(windows: []))
    }

    @Test func aBackgroundFolderWaitsForAWindowToShowIt() {
        let session = SavedSession(windows: [window(["/a", "/b"])], background: [tab("/c"), tab("/d")])
        var queue = RestoreQueue(session, isProtected: { _ in false })
        var started: [String] = []
        while let next = queue.next() {
            started.append(next)
            queue.finish(next)
        }
        #expect(started == ["/a", "/b"])
        #expect(queue.deferred == ["/c", "/d"])
        let selected = queue.select("/d")
        #expect(selected)
        let next = queue.next()
        #expect(next == "/d")
    }
}
