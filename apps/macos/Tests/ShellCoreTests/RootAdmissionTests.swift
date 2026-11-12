import Darwin
import Foundation
import Testing
@testable import ShellCore

/// A home folder in a temporary directory, with Documents in it, and a record of every
/// path admission is about to open.
private final class Fixture {
    let directory: URL
    /// Canonical, as `F_GETPATH` names it.
    let home: String
    private(set) var looked: [String] = []
    /// Runs before admission opens a path, as the test's chance to change the filesystem.
    var beforeOpening: ((String) -> Void)?

    init(_ name: String = #function) throws {
        directory = try temporaryDirectory(name)
        home = FileChecks.canonicalPath(directory.path(percentEncoded: false))
        for folder in ["wrk/app/sub", "Documents/secret", "other/leaf"] {
            try FileManager.default.createDirectory(atPath: home + "/" + folder, withIntermediateDirectories: true)
        }
        FileManager.default.createFile(atPath: home + "/notes.md", contents: Data("# notes\n".utf8))
    }

    deinit { try? FileManager.default.removeItem(at: directory) }

    func admit(_ root: String, homeDevice: dev_t? = nil) -> RootAdmission {
        RootAdmission.admit(root, home: home, homeDevice: homeDevice) { path in
            self.looked.append(path)
            self.beforeOpening?(path)
        }
    }

    func link(_ path: String, to target: String) throws {
        try FileManager.default.createSymbolicLink(atPath: home + "/" + path, withDestinationPath: target)
    }

    /// Whether admission opened anything at or below `location`, in any spelling of it.
    func lookedWithin(_ location: String) -> Bool {
        let spellings = [location, "/System/Volumes/Data" + location].map { $0.lowercased() }
        return looked.contains { path in
            spellings.contains { path.lowercased() == $0 || path.lowercased().hasPrefix($0 + "/") }
        }
    }

    var documentsLooked: Bool { lookedWithin(home + "/Documents") }
}

@Suite struct RootAdmissionTests {
    @Test func aCleanRootUnderTheHomeFolderMayStartUnderItsCanonicalIdentity() throws {
        let fixture = try Fixture()
        #expect(fixture.admit(fixture.home + "/wrk/app") == .open(fixture.home + "/wrk/app"))
        #expect(!fixture.documentsLooked)
    }

    /// Review D1: `F_GETPATH` names the folder as the kernel does, so a case variant and a
    /// Data-volume spelling are one root with one identity.
    @Test func caseAndDataVolumeSpellingsOfOneFolderShareItsIdentity() throws {
        let fixture = try Fixture()
        let canonical = RootAdmission.open(fixture.home + "/wrk/app")
        #expect(fixture.admit("/System/Volumes/Data" + fixture.home + "/wrk/app") == canonical)
        let caseSensitive = try URL(filePath: fixture.home).resourceValues(forKeys: [.volumeSupportsCaseSensitiveNamesKey])
            .volumeSupportsCaseSensitiveNames ?? true
        if !caseSensitive {
            #expect(fixture.admit(fixture.home + "/WRK/App") == canonical)
        }
    }

    /// Review D1: case variants and Data-volume aliases of protected locations wait, and
    /// nothing in them is opened.
    @Test func everySpellingOfAProtectedLocationWaitsUnopened() throws {
        let fixture = try Fixture()
        for root in [
            "/volumes/x", "/VOLUMES/x", "/System/Volumes/Data/Volumes/x",
            fixture.home + "/Documents/secret", fixture.home + "/documents/secret", fixture.home + "/DOCUMENTS",
            "/System/Volumes/Data" + fixture.home + "/Documents/secret",
        ] {
            #expect(fixture.admit(root) == .deferred(root), "\(root)")
            #expect(!fixture.documentsLooked && !fixture.lookedWithin("/Volumes"), "\(root): \(fixture.looked)")
        }
    }

    @Test func aFolderThatHoldsAProtectedLocationWaits() throws {
        let fixture = try Fixture()
        #expect(fixture.admit(fixture.home) == .deferred(fixture.home))
        #expect(fixture.admit("/") == .deferred("/"))
        #expect(fixture.admit("/System/Volumes/Data") == .deferred("/System/Volumes/Data"))
        #expect(!fixture.documentsLooked)
    }

    /// A link anywhere on the path means the folder has changed since it was saved, so its
    /// identity is not established: it waits under the saved spelling, unopened past the
    /// link, whatever the link points at.
    @Test func aRootReplacedByALinkWaitsUnderItsSavedSpelling() throws {
        let fixture = try Fixture()
        try fixture.link("proj", to: fixture.home + "/Documents/secret")
        try fixture.link("elsewhere", to: "other/leaf")
        for root in [fixture.home + "/proj", fixture.home + "/proj/inner", fixture.home + "/elsewhere"] {
            #expect(fixture.admit(root) == .deferred(root), "\(root)")
        }
        #expect(!fixture.documentsLooked)
    }

    /// Review D3's example: a link whose target runs through a protected location and back
    /// out with `..`. The saved spelling is kept, never shortened to the volume.
    @Test func aLinkThroughAProtectedLocationKeepsTheSavedSpelling() throws {
        let fixture = try Fixture()
        try fixture.link("bridge", to: "/Volumes/TestDisk/bridge/..")
        #expect(fixture.admit(fixture.home + "/bridge") == .deferred(fixture.home + "/bridge"))
        #expect(!fixture.lookedWithin("/Volumes"))
    }

    /// Review D2: each component is opened relative to the one before, without following a
    /// link, so an ancestor replaced after it was opened cannot redirect the rest of the
    /// walk. A walk by absolute paths would have followed the new link into Documents,
    /// where a `sub` folder waits.
    @Test func anAncestorReplacedDuringAdmissionIsNotFollowed() throws {
        let fixture = try Fixture()
        try FileManager.default.createDirectory(atPath: fixture.home + "/Documents/secret/sub", withIntermediateDirectories: true)
        let ancestor = fixture.home + "/wrk/app"
        fixture.beforeOpening = { path in
            guard path == ancestor + "/sub" else { return }
            // app is open; replace it with a link into Documents before sub is opened.
            try? FileManager.default.moveItem(atPath: ancestor, toPath: fixture.home + "/wrk/app-moved")
            try? FileManager.default.createSymbolicLink(atPath: ancestor, withDestinationPath: fixture.home + "/Documents/secret")
        }
        // The walk ends at the folder it opened, now named app-moved/sub, never in Documents.
        #expect(fixture.admit(ancestor + "/sub") == .open(fixture.home + "/wrk/app-moved/sub"))
        #expect(!fixture.documentsLooked, "\(fixture.looked)")
        // Swapped before it is opened, the component is a link, and the root waits.
        fixture.beforeOpening = { path in
            guard path == fixture.home + "/other/leaf" else { return }
            try? FileManager.default.moveItem(atPath: path, toPath: path + "-moved")
            try? FileManager.default.createSymbolicLink(atPath: path, withDestinationPath: fixture.home + "/Documents/secret")
        }
        #expect(fixture.admit(fixture.home + "/other/leaf") == .deferred(fixture.home + "/other/leaf"))
        #expect(!fixture.documentsLooked, "\(fixture.looked)")
    }

    @Test func aRootOnAnotherVolumeWaits() throws {
        let fixture = try Fixture()
        var info = stat()
        #expect(stat(fixture.home, &info) == 0)
        #expect(fixture.admit(fixture.home + "/wrk/app", homeDevice: info.st_dev &+ 1)
            == .deferred(fixture.home + "/wrk/app"))
    }

    @Test func otherSpellingsAreRefusedUnopened() throws {
        let fixture = try Fixture()
        for root in [
            fixture.home + "/wrk/../Documents", fixture.home + "/./wrk", fixture.home + "//wrk", fixture.home + "/wrk/",
            "wrk/app", "", fixture.home + "/wrk\napp",
        ] {
            #expect(fixture.admit(root) == .invalid, "\(root)")
        }
        #expect(fixture.looked.isEmpty)
    }

    @Test func aRootThatIsGoneOrNotAFolderIsDropped() throws {
        let fixture = try Fixture()
        #expect(fixture.admit(fixture.home + "/gone") == .gone)
        #expect(fixture.admit(fixture.home + "/notes.md") == .gone)
        #expect(fixture.admit(fixture.home + "/notes.md/below") == .gone)
    }

    /// Review D2: a root admitted at launch is checked again when its turn to start comes.
    /// One replaced by a link while an earlier server was starting waits for its tab.
    @Test func aQueuedRootReplacedWhileAnEarlierStartIsSuspendedWaits() throws {
        let fixture = try Fixture()
        let first = fixture.home + "/other/leaf"
        let second = fixture.home + "/wrk/app"
        let window = SavedWindow(
            tabs: [SavedTab(root: first, page: nil), SavedTab(root: second, page: nil)], selected: 0, frame: nil)
        let admitted = SavedSession(windows: [window]).admitted { fixture.admit($0) }
        #expect(admitted.deferred.isEmpty)
        var queue = RestoreQueue(admitted.session, isProtected: admitted.deferred.contains)
        let stillOpen = { (root: String) in fixture.admit(root) == .open(root) }
        let started = queue.next(stillOpen: stillOpen)
        #expect(started == first)
        // The first server is starting; meanwhile the second root becomes a link into Documents.
        try FileManager.default.moveItem(atPath: second, toPath: second + "-moved")
        try fixture.link("wrk/app", to: fixture.home + "/Documents/secret")
        let held = queue.next(stillOpen: stillOpen)
        #expect(held == nil)
        #expect(queue.deferred == [second])
        #expect(!fixture.documentsLooked)
        // Selecting its tab starts it: that is the user's choice.
        let selected = queue.select(second)
        let chosen = queue.next(stillOpen: { _ in false })
        #expect(selected && chosen == second)
    }

    /// The front tab is selected, so it starts without being checked again.
    @Test func theFrontTabIsNotHeldBack() {
        let window = SavedWindow(tabs: [SavedTab(root: "/front", page: nil)], selected: 0, frame: nil)
        var queue = RestoreQueue(SavedSession(windows: [window]), isProtected: { _ in false })
        let front = queue.next(stillOpen: { _ in false })
        #expect(front == "/front")
    }
}
