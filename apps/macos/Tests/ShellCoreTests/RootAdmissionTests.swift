import Darwin
import Foundation
import Testing
@testable import ShellCore

/// A filesystem of directories and symbolic links that records every path looked at.
private final class FakeFileSystem {
    private let entries: [String: PathEntry]
    private(set) var inspected: [String] = []

    init(_ entries: [String: PathEntry]) {
        self.entries = entries
    }

    func inspect(_ path: String) -> PathEntry {
        inspected.append(path)
        return entries[path] ?? .missing
    }

    /// Whether any path at or below `location` was looked at.
    func looked(within location: String) -> Bool {
        inspected.contains { $0 == location || $0.hasPrefix(location + "/") }
    }
}

@Suite struct RootAdmissionTests {
    private let home = "/Homes/me"
    private let documents = "/Homes/me/Documents"
    private let base: [String: PathEntry] = [
        "/Homes": .directory, "/Homes/me": .directory, "/Homes/me/wrk": .directory,
        "/Homes/me/wrk/app": .directory, "/Homes/me/Library": .directory, "/Homes/me/notes.md": .other,
    ]

    private func admit(_ root: String, _ extra: [String: PathEntry] = [:]) -> (RootAdmission, FakeFileSystem) {
        let files = FakeFileSystem(base.merging(extra) { $1 })
        return (RootAdmission.admit(root, home: home, inspect: files.inspect), files)
    }

    @Test func aCanonicalRootOutsideProtectedLocationsMayStart() {
        #expect(admit("/Homes/me/wrk/app").0 == .open("/Homes/me/wrk/app"))
    }

    /// The defect: a saved folder replaced by a link into Documents passed as unprotected,
    /// and its server read Documents before its tab was selected.
    @Test func aRootReplacedByALinkIntoDocumentsWaitsAndDocumentsIsNotLookedAt() {
        for target in ["/Homes/me/Documents/secret", "../me/Documents/secret", "/Homes/me/Documents"] {
            let (admission, files) = admit("/Homes/me/proj/app", ["/Homes/me/proj": .symlink(target)])
            let resolved = target.hasSuffix("secret") ? "/Homes/me/Documents/secret/app" : "/Homes/me/Documents/app"
            #expect(admission == .deferred(resolved), "\(target)")
            #expect(!files.looked(within: documents), "\(files.inspected)")
        }
    }

    @Test func aLinkElsewhereIsFollowedToTheCanonicalRoot() {
        let (admission, _) = admit("/Homes/me/link", ["/Homes/me/link": .symlink("wrk/./app")])
        #expect(admission == .open("/Homes/me/wrk/app"))
        let (absolute, _) = admit("/Homes/me/far", ["/Homes/me/far": .symlink("/Homes/me/wrk/../wrk/app")])
        #expect(absolute == .open("/Homes/me/wrk/app"))
    }

    @Test func otherSpellingsAreRefusedWithoutLookingAtAnything() {
        for root in [
            "/Homes/me/wrk/../Documents", "/Homes/me/./wrk", "/Homes/me//wrk", "/Homes/me/wrk/", "wrk/app", "",
            "/Homes/me/wrk\napp",
        ] {
            let (admission, files) = admit(root)
            #expect(admission == .invalid, "\(root)")
            #expect(files.inspected.isEmpty, "\(root)")
        }
    }

    @Test func aProtectedSpellingWaitsWithoutLookingInside() {
        for root in ["/Homes/me/Documents/notes", "/Volumes/USB/photos", "/Homes/me/Library/Mobile Documents/x"] {
            let (admission, files) = admit(root)
            #expect(admission == .deferred(root), "\(root)")
            for location in [documents, "/Volumes", "/Homes/me/Library/Mobile Documents"] {
                #expect(!files.looked(within: location), "\(root): \(files.inspected)")
            }
        }
    }

    @Test func aFolderThatHoldsAProtectedLocationWaits() {
        #expect(admit("/Homes/me").0 == .deferred("/Homes/me"))
        #expect(admit("/").0 == .deferred("/"))
    }

    @Test func aRootThatIsGoneOrNotAFolderIsDropped() {
        #expect(admit("/Homes/me/gone").0 == .gone)
        #expect(admit("/Homes/me/notes.md").0 == .gone)
        #expect(admit("/Homes/me/dangling", ["/Homes/me/dangling": .symlink("nowhere")]).0 == .gone)
    }

    @Test func aLinkLoopIsRefused() {
        let (admission, files) = admit("/Homes/me/a", ["/Homes/me/a": .symlink("b"), "/Homes/me/b": .symlink("a")])
        #expect(admission == .invalid)
        #expect(files.inspected.count <= RootAdmission.linkLimit * 2 + 4)
    }

    /// Against the real filesystem: links are read with lstat and readlink, and an
    /// unprotected root resolves as realpath(3) does.
    @Test func theRealFilesystemResolvesAsRealpathDoes() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let home = FileChecks.canonicalPath(directory.path(percentEncoded: false))
        let manager = FileManager.default
        try manager.createDirectory(atPath: home + "/wrk/app", withIntermediateDirectories: true)
        try manager.createDirectory(atPath: home + "/Documents/secret", withIntermediateDirectories: true)
        try manager.createSymbolicLink(atPath: home + "/link", withDestinationPath: "wrk/app")
        try manager.createSymbolicLink(atPath: home + "/proj", withDestinationPath: home + "/Documents/secret")

        // The temporary directory is under /var, itself a link to /private/var.
        let spelled = directory.path(percentEncoded: false).replacingOccurrences(of: "/private/var/", with: "/var/")
        let viaLink = (spelled.hasSuffix("/") ? String(spelled.dropLast()) : spelled) + "/link"
        #expect(RootAdmission.admit(viaLink, home: home) == .open(home + "/wrk/app"))
        #expect(FileChecks.canonicalPath(viaLink) == home + "/wrk/app")
        #expect(RootAdmission.admit(home + "/proj", home: home) == .deferred(home + "/Documents/secret"))
        #expect(PathEntry.inspect(home + "/link") == .symlink("wrk/app"))
        #expect(PathEntry.inspect(home + "/wrk") == .directory)
        #expect(PathEntry.inspect(home + "/missing") == .missing)
    }
}
