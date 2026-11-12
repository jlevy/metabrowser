import Darwin
import Foundation
import Testing
@testable import ShellCore

@Suite struct ProtectedLocationsTests {
    private let home = "/Homes/me"

    @Test func foldersMacOSAsksAboutAreProtected() {
        for path in [
            "/Homes/me/Desktop", "/Homes/me/Documents/notes", "/Homes/me/Downloads/x/y",
            "/Homes/me/Library/Mobile Documents/com~apple~CloudDocs/notes",
            "/Homes/me/Library/CloudStorage/Dropbox", "/Homes/me/Library/Containers/com.example.app",
            "/Homes/me/Library/Group Containers/group.x", "/Volumes/USB", "/Volumes/Share/docs", "/Network/Servers/x",
        ] {
            #expect(ProtectedLocations.contains(path, home: home), "\(path)")
        }
    }

    @Test func aFolderThatHoldsOneIsProtectedSinceServingItReadsThem() {
        for path in ["/Homes/me", "/Homes", "/", "/Homes/me/Library"] {
            #expect(ProtectedLocations.contains(path, home: home), "\(path)")
        }
    }

    @Test func everythingElseIsNot() {
        for path in [
            "/Homes/me/wrk/github/fdu", "/Homes/me/Desktop-old", "/Homes/me/Documentsx", "/Homes/me/Library/Logs",
            "/opt/data", "/private/tmp/x", "/Homes/other/Documents", "/Volumesx",
        ] {
            #expect(!ProtectedLocations.contains(path, home: home), "\(path)")
        }
    }
}

@Suite struct RestoreQueueTests {
    private func window(_ roots: [String], selected: Int = 0) -> SavedWindow {
        SavedWindow(tabs: roots.map { SavedTab(root: $0, page: nil) }, selected: selected, frame: nil)
    }

    private func drain(_ queue: inout RestoreQueue) -> [String] {
        var started: [String] = []
        while let next = queue.next() { started.append(next) }
        return started
    }

    @Test func theFrontTabStartsFirstThenTheShownTabsThenTheRest() {
        let session = SavedSession(windows: [
            window(["/a", "/b", "/c"], selected: 1),
            window(["/d", "/e"], selected: 1),
            window(["/f"]),
        ])
        var queue = RestoreQueue(session, isProtected: { _ in false })
        #expect(drain(&queue) == ["/b", "/e", "/f", "/a", "/c", "/d"])
    }

    @Test func eachRootStartsOnceHoweverManyTabsShowIt() {
        let session = SavedSession(windows: [window(["/a", "/b", "/a"], selected: 2), window(["/b", "/a"])])
        var queue = RestoreQueue(session, isProtected: { _ in false })
        #expect(drain(&queue) == ["/a", "/b"])
    }

    @Test func aProtectedRootWaitsUntilItsTabIsSelected() {
        let session = SavedSession(windows: [
            window(["/docs", "/a"], selected: 1),
            window(["/desk"]),
        ])
        let isProtected = { (root: String) in root == "/docs" || root == "/desk" }
        var queue = RestoreQueue(session, isProtected: isProtected)
        #expect(drain(&queue) == ["/a"])
        #expect(queue.deferred == ["/desk", "/docs"])
        let moved = queue.select("/docs")
        #expect(moved)
        #expect(drain(&queue) == ["/docs"])
        #expect(queue.deferred == ["/desk"])
    }

    @Test func theFrontTabStartsEvenInAProtectedLocationSinceItIsSelected() {
        let session = SavedSession(windows: [window(["/docs"]), window(["/desk"])])
        var queue = RestoreQueue(session, isProtected: { $0 != "/a" })
        #expect(drain(&queue) == ["/docs"])
        #expect(queue.deferred == ["/desk"])
    }

    @Test func aSelectedTabJumpsTheQueue() {
        let session = SavedSession(windows: [window(["/a", "/b", "/c", "/d"])])
        var queue = RestoreQueue(session, isProtected: { _ in false })
        let first = queue.next()
        #expect(first == "/a")
        let selected = [queue.select("/d"), queue.select("/a"), queue.select("/z")]
        #expect(selected == [true, false, false], "/a has started, and /z is not part of the restore")
        #expect(drain(&queue) == ["/d", "/b", "/c"])
    }

    @Test func aRootWhoseTabsAllClosedIsForgotten() {
        let session = SavedSession(windows: [window(["/a", "/b", "/docs"])])
        var queue = RestoreQueue(session, isProtected: { $0 == "/docs" })
        queue.remove("/b")
        queue.remove("/docs")
        #expect(drain(&queue) == ["/a"])
        #expect(queue.deferred.isEmpty)
        let moved = queue.select("/docs")
        #expect(!moved)
    }
}

@Suite struct SavedSessionTests {
    private func tab(_ root: String, _ page: PageAddress? = nil) -> SavedTab { SavedTab(root: root, page: page) }

    @Test func admissionDropsWhatCannotBeShownAndClampsTheSelection() {
        let session = SavedSession(windows: [
            SavedWindow(
                tabs: [tab("/gone"), tab("/bad/../x"), tab("/here", .view(of: "a.md")), tab("/docs")],
                selected: 7, frame: "f"),
            SavedWindow(tabs: [tab("/gone")], selected: 0, frame: nil),
            SavedWindow(tabs: [], selected: 0, frame: nil),
        ])
        let admitted = session.admitted { root in
            switch root {
            case "/here": .open("/here")
            case "/docs": .deferred("/docs")
            case "/gone": .gone
            default: .invalid
            }
        }
        #expect(admitted.session == SavedSession(windows: [
            SavedWindow(tabs: [tab("/here", .view(of: "a.md")), tab("/docs")], selected: 1, frame: "f"),
        ]))
        #expect(admitted.deferred == ["/docs"])
    }

    @Test func theSelectionFollowsItsTabWhenEarlierTabsAreDropped() {
        let session = SavedSession(windows: [
            SavedWindow(tabs: [tab("/gone"), tab("/a"), tab("/b")], selected: 2, frame: nil),
        ])
        let admitted = session.admitted { $0 == "/gone" ? .gone : .open($0) }
        #expect(admitted.session.windows.first?.selected == 1)
    }

    /// Aliases of one folder become one root, so they share one session and one server,
    /// and each root is resolved once however many tabs name it.
    @Test func aliasesOfOneFolderBecomeOneRootResolvedOnce() {
        let session = SavedSession(windows: [
            SavedWindow(tabs: [tab("/link"), tab("/wrk/app"), tab("/link")], selected: 0, frame: nil),
        ])
        var resolved: [String] = []
        let admitted = session.admitted { root in
            resolved.append(root)
            return .open("/wrk/app")
        }
        #expect(admitted.session.windows[0].tabs.map(\.root) == ["/wrk/app", "/wrk/app", "/wrk/app"])
        #expect(resolved == ["/link", "/wrk/app"])
        var queue = RestoreQueue(admitted.session, isProtected: admitted.deferred.contains)
        #expect(queue.next() == "/wrk/app")
        #expect(queue.next() == nil)
    }

    /// The defect B1 and C1 describe, end to end through the queue: a background root that
    /// now resolves into a protected location waits for its tab.
    @Test func aBackgroundRootThatResolvesIntoAProtectedLocationWaits() {
        let session = SavedSession(windows: [
            SavedWindow(tabs: [tab("/wrk/app"), tab("/proj")], selected: 0, frame: nil),
        ])
        let admitted = session.admitted { $0 == "/proj" ? .deferred("/Homes/me/Documents/secret") : .open($0) }
        var queue = RestoreQueue(admitted.session, isProtected: admitted.deferred.contains)
        #expect(queue.next() == "/wrk/app")
        #expect(queue.next() == nil)
        #expect(queue.deferred == ["/Homes/me/Documents/secret"])
    }

    @Test func aSessionPastTheBudgetKeepsItsFrontWindowsAndEachWindowsShownTab() {
        let window = { (count: Int, selected: Int) in
            SavedWindow(tabs: (0..<count).map { self.tab("/r\($0)") }, selected: selected, frame: nil)
        }
        let budget = RestoreBudget(windows: 2, tabs: 5)
        let session = SavedSession(windows: [window(3, 0), window(4, 3), window(1, 0)])
        let kept = session.limited(to: budget)
        #expect(kept.windows.count == 2)
        #expect(kept.windows[0] == window(3, 0))
        // Two tabs are left for the second window: its first, and the one it shows.
        #expect(kept.windows[1].tabs.map(\.root) == ["/r0", "/r3"])
        #expect(kept.windows[1].selected == 1)
        #expect(session.limited(to: RestoreBudget(windows: 9, tabs: 9)) == session)
    }

    /// Review B3's input: ten thousand windows in a file well under the byte limit. Only the
    /// budget's worth reach admission, window creation, or the queue.
    @Test func aHostileSessionBuildsOnlyTheBudget() throws {
        let session = SavedSession(windows: Array(repeating: SavedWindow(tabs: [tab("/")], selected: 0, frame: nil), count: 10_000))
        #expect(try JSONEncoder().encode(session).count < SessionStore.byteLimit)
        var admissions = 0
        let admitted = session.limited(to: .standard).admitted { root in
            admissions += 1
            return .deferred(root)
        }
        #expect(admitted.session.windows.count == RestoreBudget.standard.windows)
        #expect(admissions == 1)
        let tabs = SavedSession(windows: [SavedWindow(tabs: (0..<10_000).map { tab("/r\($0)") }, selected: 0, frame: nil)])
        #expect(tabs.limited(to: .standard).windows[0].tabs.count == RestoreBudget.standard.tabs)
    }
}

@Suite struct SessionStoreTests {
    private let session = SavedSession(windows: [
        SavedWindow(
            tabs: [SavedTab(root: "/Homes/me/notes", page: .view(of: "plan.md")), SavedTab(root: "/opt/x", page: nil)],
            selected: 1, frame: "0 0 1200 820 0 0 1512 949 "),
    ])

    private func mode(_ path: String) throws -> Int? {
        try FileManager.default.attributesOfItem(atPath: path)[.posixPermissions] as? Int
    }

    @Test func savesPrivatelyAndReadsBack() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let store = SessionStore(directory: directory.appending(path: "Application Support/app"))
        #expect(try store.load() == nil)
        try store.save(session)
        #expect(try store.load() == session)
        #expect(try mode(store.url.path(percentEncoded: false)) == 0o600)
        #expect(try mode(store.url.deletingLastPathComponent().path(percentEncoded: false)) == 0o700)
    }

    @Test func aSaveReplacesTheFileWholeAndLeavesNoTemporaryFile() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let store = SessionStore(directory: directory)
        try store.save(session)
        try store.save(SavedSession(windows: []))
        #expect(try store.load() == SavedSession(windows: []))
        #expect(try FileManager.default.contentsOfDirectory(atPath: directory.path(percentEncoded: false))
            == [SessionStore.fileName])
    }

    @Test func aFailedSaveKeepsThePreviousFile() throws {
        let directory = try temporaryDirectory()
        defer {
            chmod(directory.path(percentEncoded: false), 0o700)
            try? FileManager.default.removeItem(at: directory)
        }
        let store = SessionStore(directory: directory)
        try store.save(session)
        chmod(directory.path(percentEncoded: false), 0o500)  // no new file can be created here
        #expect(throws: (any Error).self) { try store.save(SavedSession(windows: [])) }
        #expect(try store.load() == session)
    }

    @Test func anUnreadableFileIsAnErrorNotAnEmptySession() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let store = SessionStore(directory: directory)
        try Data("{\"windows\": [{\"tabs\": 3}]}".utf8).write(to: store.url)
        #expect(throws: DecodingError.self) { try store.load() }
        try Data(repeating: 0x20, count: SessionStore.byteLimit + 1).write(to: store.url)
        #expect(throws: SessionStore.LoadError.tooLarge) { try store.load() }
    }

    /// A pipe would block the launch on open, and a link could point anywhere: neither is
    /// read.
    @Test func aPipeOrALinkIsNotASessionAndOpeningOneDoesNotBlock() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let store = SessionStore(directory: directory)
        let path = store.url.path(percentEncoded: false)
        #expect(mkfifo(path, 0o600) == 0)
        #expect(throws: SessionStore.LoadError.notARegularFile) { try store.load() }
        unlink(path)
        let real = directory.appending(path: "elsewhere.json")
        try SessionStore(directory: directory.appending(path: "other")).save(session)
        try FileManager.default.moveItem(at: directory.appending(path: "other/session.json"), to: real)
        try FileManager.default.createSymbolicLink(at: store.url, withDestinationURL: real)
        #expect(throws: SessionStore.LoadError.notARegularFile) { try store.load() }
    }

    /// The defect: the size was checked on one lookup and the file read on another, with no
    /// bound on the read. Bytes appended after the file is opened and checked still count.
    @Test func theLimitBoundsTheBytesReadNotASizeCheckedBefore() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let store = SessionStore(directory: directory)
        try store.save(session)
        #expect(throws: SessionStore.LoadError.tooLarge) {
            try store.load(afterOpening: {
                let handle = try FileHandle(forWritingTo: store.url)
                try handle.seekToEnd()
                try handle.write(contentsOf: Data(repeating: 0x20, count: SessionStore.byteLimit))
                try handle.close()
            })
        }
    }

    @Test func aReplacementAfterOpeningReadsTheFileThatWasOpened() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let store = SessionStore(directory: directory)
        try store.save(session)
        let huge = directory.appending(path: "huge.json")
        try Data(repeating: 0x20, count: SessionStore.byteLimit * 2).write(to: huge)
        let loaded = try store.load(afterOpening: {
            guard rename(huge.path(percentEncoded: false), store.url.path(percentEncoded: false)) == 0 else {
                throw POSIXError(.EIO)
            }
        })
        #expect(loaded == session)
    }
}
