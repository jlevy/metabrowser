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
    @Test func restorableDropsWhatCannotBeShownAndClampsTheSelection() {
        let session = SavedSession(windows: [
            SavedWindow(
                tabs: [
                    SavedTab(root: "/gone", page: nil), SavedTab(root: "relative", page: nil),
                    SavedTab(root: "/here", page: .view(of: "a.md")), SavedTab(root: "/docs", page: nil),
                ],
                selected: 7, frame: "f"),
            SavedWindow(tabs: [SavedTab(root: "/gone", page: nil)], selected: 0, frame: nil),
            SavedWindow(tabs: [], selected: 0, frame: nil),
        ])
        var checked: [String] = []
        let restorable = session.restorable(isProtected: { $0 == "/docs" }) { root in
            checked.append(root)
            return root == "/here"
        }
        #expect(restorable == SavedSession(windows: [
            SavedWindow(
                tabs: [SavedTab(root: "/here", page: .view(of: "a.md")), SavedTab(root: "/docs", page: nil)],
                selected: 1, frame: "f"),
        ]))
        // A protected root is never looked at: even a stat could raise the privacy prompt.
        #expect(!checked.contains("/docs"))
    }

    @Test func theSelectionFollowsItsTabWhenEarlierTabsAreDropped() {
        let session = SavedSession(windows: [
            SavedWindow(
                tabs: [SavedTab(root: "/gone", page: nil), SavedTab(root: "/a", page: nil), SavedTab(root: "/b", page: nil)],
                selected: 2, frame: nil),
        ])
        let restorable = session.restorable(isProtected: { _ in false }) { $0 != "/gone" }
        #expect(restorable.windows.first?.selected == 1)
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
        #expect(throws: SessionStore.LoadError.tooLarge(SessionStore.byteLimit + 1)) { try store.load() }
    }
}
