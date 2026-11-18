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

    @Test func closeFolderShowsTheBackgroundFolderShownMostRecently() {
        var open = OpenFolders()
        for root in ["/a", "/b", "/c", "/d"] { open.show(root) }
        // /d is closing; /c is shown in another window, so only /a and /b are background.
        #expect(open.replacement(closing: "/d", background: ["/a", "/b"]) == "/b")
        #expect(open.replacement(closing: "/b", background: ["/b"]) == nil)
        #expect(open.replacement(closing: "/d", background: []) == nil)
    }

    @Test func aPageSwitchedAwayFromIsKeptOnlyWhenItIsItsFoldersLast() {
        #expect(SwitchedAwayPage.fate(otherPages: 0) == .keepInBackground)
        #expect(SwitchedAwayPage.fate(otherPages: 1) == .close)
        #expect(SwitchedAwayPage.fate(otherPages: 3) == .close)
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
