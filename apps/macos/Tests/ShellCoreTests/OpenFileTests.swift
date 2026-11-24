import CoreServices
import Foundation
import Testing
import UniformTypeIdentifiers
@testable import ShellCore

/// The message a click on a page's Open link posts (`OpenFileRequests.Request`).
@Suite struct OpenFileRequestTests {
    private func request(
        _ href: Any? = "http://127.0.0.1:8411/raw?path=docs%2Fa%20b.pdf", subject: Any? = "filesystem",
        name: Any? = "a b.pdf"
    ) -> OpenFileRequests.Request? {
        var body: [String: Any] = [:]
        body["href"] = href
        body["subject"] = subject
        body["name"] = name
        return OpenFileRequests.Request(body)
    }

    @Test func theLinkTheScriptPostsIsRead() throws {
        let read = try #require(request())
        #expect(read.href.absoluteString == "http://127.0.0.1:8411/raw?path=docs%2Fa%20b.pdf")
        #expect(read.subject == .filesystem)
        #expect(read.path == "docs/a b.pdf")
        #expect(read.name == "a b.pdf")
        let pinned = try #require(request("https://127.0.0.1:8411/raw?path=g1-abc_DEF", subject: "git_revision"))
        #expect(pinned.subject == .gitRevision)
        #expect(pinned.path == "g1-abc_DEF")
    }

    /// The server reads a query as a form: `+` is a space, and `%2B` is a plus sign.
    @Test func thePathIsDecodedAsTheServerDecodesIt() {
        #expect(request("http://127.0.0.1:8411/raw?path=a+b%2Bc.pdf")?.path == "a b+c.pdf")
        #expect(request("http://127.0.0.1:8411/raw?path=%E9%9B%AA.pdf&plain=1")?.path == "雪.pdf")
    }

    @Test func aMessageOfAnyOtherShapeIsDropped() {
        #expect(OpenFileRequests.Request("http://127.0.0.1:8411/raw?path=a.pdf") == nil)
        #expect(OpenFileRequests.Request(["href": 1, "subject": "filesystem", "name": "a.pdf"]) == nil)
        #expect(request(nil) == nil)
        for href in [
            "", "/raw?path=a.pdf", "file:///raw?path=a.pdf", "javascript:alert(1)", "data:text/html,x",
            "http:///raw?path=a.pdf", "http://127.0.0.1:8411/raw/a.pdf", "http://127.0.0.1:8411/view?path=a.pdf",
            "http://127.0.0.1:8411/raw/?path=a.pdf", "http://127.0.0.1:8411/raw", "http://127.0.0.1:8411/raw?path=",
            "http://127.0.0.1:8411/raw?file=a.pdf", "http://127.0.0.1:8411/raw?path=a.pdf&path=b.pdf",
            "http://127.0.0.1:8411/raw?path=a%00.pdf",
        ] {
            #expect(request(href) == nil, "\(href)")
        }
        for subject: Any? in [nil, "", "Filesystem", "git-revision", "repository", 1] {
            #expect(request(subject: subject) == nil, "\(String(describing: subject))")
        }
    }

    /// A `download` name that cannot name a file in a folder of its own falls back to the
    /// last part of the path.
    @Test func anUnusableNameFallsBackToThePathsLastPart() {
        for name: Any? in [nil, "", ".", "..", "a/b.pdf", "a\0.pdf", String(repeating: "a", count: 252) + ".pdf", 7] {
            #expect(request(name: name)?.name == "a b.pdf", "\(String(describing: name).prefix(40))")
        }
        #expect(request(name: String(repeating: "a", count: 251) + ".pdf")?.name.utf8.count == 255)
        #expect(request("http://127.0.0.1:8411/raw?path=docs/", name: "") == nil)
        #expect(request("http://127.0.0.1:8411/raw?path=docs/..", name: "") == nil)
    }
}

/// Which clicks a window answers, by the document's origin and the link's.
@Suite struct OpenFilePolicyTests {
    private let policy = NavigationPolicy(origin: URL(string: "http://127.0.0.1:8412")!)
    private let file = URL(string: "http://127.0.0.1:8412/raw?path=a.pdf")!

    @Test func theServersOwnPageMayOpenTheServersOwnFile() {
        #expect(policy.allowsOpenFile(file, scheme: "http", host: "127.0.0.1", port: 8412, isMainFrame: true))
        #expect(!policy.allowsOpenFile(file, scheme: "http", host: "127.0.0.1", port: 8412, isMainFrame: false))
    }

    /// A sandboxed `/raw` document has an opaque origin, which WebKit reports with no
    /// scheme and no host.
    @Test func anOpaqueOriginOpensNothing() {
        #expect(!policy.allowsOpenFile(file, scheme: "", host: "", port: 0, isMainFrame: true))
    }

    @Test func aLinkToAnotherOriginOpensNothing() {
        for href in [
            "http://127.0.0.1:8413/raw?path=a.pdf", "https://127.0.0.1:8412/raw?path=a.pdf",
            "http://localhost:8412/raw?path=a.pdf", "http://example.com/raw?path=a.pdf",
        ] {
            #expect(!policy.allowsOpenFile(
                URL(string: href)!, scheme: "http", host: "127.0.0.1", port: 8412, isMainFrame: true), "\(href)")
        }
        #expect(!NavigationPolicy().allowsOpenFile(file, scheme: "http", host: "127.0.0.1", port: 8412, isMainFrame: true))
    }
}

/// What a window does with a click, from what it serves, against a real folder.
@Suite struct OpenFilePlanTests {
    private let pdf = Data("%PDF-1.4\n%\u{E2}\u{E3}\n".utf8)

    private func request(
        _ path: String, subject: OpenFileRequests.Request.Subject = .filesystem, name: String? = nil
    ) throws -> OpenFileRequests.Request {
        var parts = URLComponents(string: "http://127.0.0.1:8411/raw")!
        parts.queryItems = [URLQueryItem(name: "path", value: path)]
        let href = try #require(parts.url?.absoluteString)
        let fallback = (path as NSString).lastPathComponent
        return try #require(OpenFileRequests.Request([
            "href": href, "subject": subject.rawValue, "name": name ?? fallback,
        ]))
    }

    /// A folder with `docs/a b.pdf`, a script, an SVG, a link to a file outside it, and a
    /// link to a folder outside it; and the outside folder.
    private func folder() throws -> (root: URL, outside: URL) {
        let root = try temporaryDirectory()
        let outside = try temporaryDirectory()
        let manager = FileManager.default
        try manager.createDirectory(at: root.appending(path: "docs"), withIntermediateDirectories: true)
        try pdf.write(to: root.appending(path: "docs/a b.pdf"))
        try Data("#!/bin/sh\necho hi\n".utf8).write(to: root.appending(path: "run.command"))
        try Data("<svg xmlns='http://www.w3.org/2000/svg'/>".utf8).write(to: root.appending(path: "mark.svg"))
        try pdf.write(to: outside.appending(path: "secret.pdf"))
        try manager.createSymbolicLink(
            atPath: root.appending(path: "escape.pdf").path, withDestinationPath: outside.appending(path: "secret.pdf").path)
        try manager.createSymbolicLink(atPath: root.appending(path: "away").path, withDestinationPath: outside.path)
        try manager.createSymbolicLink(atPath: root.appending(path: "here.pdf").path, withDestinationPath: "docs/a b.pdf")
        return (root, outside)
    }

    private func remove(_ folders: (root: URL, outside: URL)) {
        try? FileManager.default.removeItem(at: folders.root)
        try? FileManager.default.removeItem(at: folders.outside)
    }

    private func refusal(_ plan: OpenFilePlan) -> OpenFileFailure? {
        if case .refuse(let failure) = plan { return failure }
        return nil
    }

    @Test func aFileInTheFolderOpensAtItsRealPath() throws {
        let folders = try folder()
        defer { remove(folders) }
        let file = folders.root.appending(path: "docs/a b.pdf")
        #expect(OpenFilePlan.resolve(try request("docs/a b.pdf"), in: .folder(folders.root)) == .openFile(file))
        // A link to a file in the folder opens the file it names.
        #expect(OpenFilePlan.resolve(try request("here.pdf"), in: .folder(folders.root)) == .openFile(file))
    }

    /// The folder's root is compared by its real path too.
    @Test func aRootReachedThroughALinkIsItsRealPath() throws {
        let folders = try folder()
        defer { remove(folders) }
        let link = folders.outside.appending(path: "root-link")
        try FileManager.default.createSymbolicLink(atPath: link.path, withDestinationPath: folders.root.path)
        #expect(OpenFilePlan.resolve(try request("docs/a b.pdf"), in: .folder(link))
            == .openFile(folders.root.appending(path: "docs/a b.pdf")))
    }

    @Test func aPathThatLeavesTheFolderIsRefused() throws {
        let folders = try folder()
        defer { remove(folders) }
        let outside = folders.outside.lastPathComponent
        for path in [
            "../\(outside)/secret.pdf", "docs/../docs/a b.pdf", "./docs/a b.pdf", "docs//a b.pdf", "docs/a b.pdf/",
            folders.outside.appending(path: "secret.pdf").path, "/docs/a b.pdf",
        ] {
            let failure = refusal(OpenFilePlan.resolve(try request(path, name: "secret.pdf"), in: .folder(folders.root)))
            #expect(failure?.reason == "its path does not name a file in this folder", "\(path)")
            #expect(failure?.reveal == nil)
        }
    }

    /// A link in the folder to a file, or through a folder, outside it opens nothing.
    @Test func aLinkOutOfTheFolderIsRefused() throws {
        let folders = try folder()
        defer { remove(folders) }
        for path in ["escape.pdf", "away/secret.pdf"] {
            let failure = refusal(OpenFilePlan.resolve(try request(path), in: .folder(folders.root)))
            #expect(failure?.reason == "it is a link to a file outside this folder", "\(path)")
            #expect(failure?.reveal == nil)
        }
    }

    @Test func aFolderOrAMissingFileIsRefused() throws {
        let folders = try folder()
        defer { remove(folders) }
        #expect(refusal(OpenFilePlan.resolve(try request("docs"), in: .folder(folders.root)))?.reason == "it is not a file")
        #expect(refusal(OpenFilePlan.resolve(try request("docs/gone.pdf"), in: .folder(folders.root)))?.reason
            == "it is not in this folder any more")
    }

    /// A type the app does not open is refused, and the file is offered to Finder.
    @Test func aTypeTheAppDoesNotOpenIsOfferedToFinder() throws {
        let folders = try folder()
        defer { remove(folders) }
        for name in ["run.command", "mark.svg"] {
            let failure = try #require(refusal(OpenFilePlan.resolve(try request(name), in: .folder(folders.root))))
            #expect(failure.reason == OpenFileTypes.refusal)
            #expect(failure.reveal == folders.root.appending(path: name))
            #expect(failure.message == "Could not open “\(name)”: \(OpenFileTypes.refusal).")
        }
    }

    /// A pinned revision's path, or any path in a repository's window, has no file on this
    /// disk: its bytes are downloaded from the link.
    @Test func whatHasNoFileOnDiskIsDownloaded() throws {
        let folders = try folder()
        defer { remove(folders) }
        let pinned = try request("g1-abc", subject: .gitRevision, name: "a b.pdf")
        #expect(OpenFilePlan.resolve(pinned, in: .folder(folders.root)) == .downloadThenOpen(pinned.href, name: "a b.pdf"))
        let repository = SessionRoot.repository(URL(string: "https://github.com/octo/demo")!)
        #expect(OpenFilePlan.resolve(pinned, in: repository) == .downloadThenOpen(pinned.href, name: "a b.pdf"))
        let mirrored = try request("docs/a b.pdf")
        #expect(OpenFilePlan.resolve(mirrored, in: repository) == .downloadThenOpen(mirrored.href, name: "a b.pdf"))
    }

    /// Its type is the name's, checked before anything downloads, with no file to reveal.
    @Test func aDownloadOfATypeTheAppDoesNotOpenIsRefusedFirst() throws {
        for name in ["run.command", "page.html", "mark.svg", "notes.txt", "tool.app", "setup.pkg"] {
            let failure = refusal(OpenFilePlan.resolve(
                try request("g1-abc", subject: .gitRevision, name: name), in: .folder(URL(filePath: "/nonexistent"))))
            #expect(failure == OpenFileFailure(name: name, reason: OpenFileTypes.refusal), "\(name)")
        }
    }

    /// A name that gives no type the system knows, with no extension or one no app
    /// declares, cannot be judged before its bytes are served: it downloads, and its copy
    /// is named by the type it is served as (`OpenFileTypes.copyName`).
    @Test func aNameThatGivesNoTypeIsDownloaded() throws {
        for name in ["untitled", "notes", "scan.v2", "a."] {
            let pinned = try request("g1-abc", subject: .gitRevision, name: name)
            #expect(OpenFilePlan.resolve(pinned, in: .folder(URL(filePath: "/nonexistent")))
                == .downloadThenOpen(pinned.href, name: name), "\(name)")
        }
    }
}

/// The name a downloaded copy is kept under, from the link's name and the type the server
/// answered with (`OpenFileTypes.copyName`).
@Suite struct OpenFileCopyNameTests {
    /// What `/raw` answers for a PDF with no extension: the type its leading bytes give.
    @Test func anExtensionlessPDFTakesTheExtensionOfItsServedType() {
        #expect(OpenFileTypes.copyName("untitled", servedAs: "application/pdf") == "untitled.pdf")
        #expect(OpenFileTypes.copyName("scan", servedAs: "image/png") == "scan.png")
        #expect(OpenFileTypes.allows(OpenFileTypes.type(named: OpenFileTypes.copyName("untitled", servedAs: "application/pdf"))))
    }

    /// A name whose type is the served one, or one conforming to it either way, as `/raw`
    /// serves a file by its name's extension, is kept as it is.
    @Test func aNameThatAgreesWithItsServedTypeIsKept() {
        for (name, served) in [
            ("a b.pdf", "application/pdf"), ("photo.JPG", "image/jpeg"), ("photo.jpeg", "image/jpeg"),
            ("scan.tif", "image/tiff"), ("song.m4a", "audio/mp4"), ("song.wav", "audio/x-wav"),
            ("clip.mov", "video/quicktime"), ("clip.mp4", "video/mp4"), ("clip.mp4", "audio/mp4"),
        ] {
            #expect(OpenFileTypes.copyName(name, servedAs: served) == name, "\(name) as \(served)")
        }
    }

    /// A name of another type, or of one no app declares, takes the served type's extension
    /// after its own, so Launch Services opens the copy as what it is.
    @Test func aNameThatDisagreesTakesTheServedExtensionAfterItsOwn() {
        #expect(OpenFileTypes.copyName("photo.png", servedAs: "image/jpeg") == "photo.png.jpeg")
        #expect(OpenFileTypes.copyName("scan.v2", servedAs: "application/pdf") == "scan.v2.pdf")
        #expect(OpenFileTypes.copyName("report.pdf", servedAs: "image/png") == "report.pdf.png")
    }

    /// A served type the system does not know, or that names nothing in particular,
    /// leaves the name as it is.
    @Test func anUnknownServedTypeKeepsTheName() {
        for served: String? in [
            nil, "", "application/octet-stream", "application/x-no-such-type", "audio/opus", "not a media type",
        ] {
            #expect(OpenFileTypes.copyName("untitled", servedAs: served) == "untitled", "\(String(describing: served))")
            #expect(OpenFileTypes.copyName("a b.pdf", servedAs: served) == "a b.pdf", "\(String(describing: served))")
        }
    }

    /// A served type the app does not open never names a copy: the name stays as it is,
    /// and the copy is then refused by it, as `OpenFileDownloads` checks every copy.
    @Test func aServedTypeTheAppDoesNotOpenNeverRenamesACopy() {
        for served in [
            "text/html", "image/svg+xml", "application/x-sh", "text/x-shellscript", "application/x-apple-diskimage",
            "application/vnd.apple.installer+xml", "application/java-archive", "application/zip", "text/plain",
            "application/x-mpegurl",
        ] {
            let kept = OpenFileTypes.copyName("untitled", servedAs: served)
            #expect(kept == "untitled", "\(served)")
            #expect(!OpenFileTypes.allows(OpenFileTypes.type(named: kept)), "\(served)")
            // A name the app opens stays the name it opens by.
            #expect(OpenFileTypes.copyName("photo.png", servedAs: served) == "photo.png", "\(served)")
        }
    }

    /// The extension is never cut: the name is, to keep within a file name's bytes.
    @Test func aLongNameIsCutToFitTheExtension() {
        let long = String(repeating: "a", count: Int(NAME_MAX))
        let named = OpenFileTypes.copyName(long, servedAs: "application/pdf")
        #expect(named == String(repeating: "a", count: Int(NAME_MAX) - 4) + ".pdf")
        // Cut by whole characters, never inside one.
        let snow = String(repeating: "雪", count: 85)  // 255 bytes
        let cut = OpenFileTypes.copyName(snow, servedAs: "application/pdf")
        #expect(cut == String(repeating: "雪", count: 83) + ".pdf")
        #expect(cut.utf8.count <= Int(NAME_MAX))
    }
}

/// Whether a file on disk opens in its default app or is saved to Downloads, apart from
/// Launch Services.
@Suite struct OpenFileHandoffTests {
    private let file = URL(filePath: "/tmp/sandbox/clip.mkv")

    @Test func aFileNoAppOpensIsSavedToDownloads() {
        #expect(OpenFileHandoff.decide(file, defaultApp: { _ in nil }) == .saveToDownloads(file))
    }

    @Test func aFileWithADefaultAppOpens() {
        let preview = URL(filePath: "/System/Applications/Preview.app", directoryHint: .isDirectory)
        var asked: [URL] = []
        #expect(OpenFileHandoff.decide(file, defaultApp: { asked.append($0); return preview }) == .open(file))
        #expect(asked == [file])
    }
}

/// A copy saved to Downloads, against a real folder standing in for it.
@Suite struct OpenFileSaveTests {
    private let pdf = Data("%PDF-1.4\n%\u{E2}\u{E3}\n".utf8)

    @Test func theNamesTriedAreNumberedBeforeTheExtension() {
        #expect(OpenFileSaves.name("report.pdf", attempt: 1) == "report.pdf")
        #expect(OpenFileSaves.name("report.pdf", attempt: 2) == "report 2.pdf")
        #expect(OpenFileSaves.name("report.pdf", attempt: 10) == "report 10.pdf")
        #expect(OpenFileSaves.name("scan.v2.pdf", attempt: 2) == "scan.v2 2.pdf")
        #expect(OpenFileSaves.name("untitled", attempt: 3) == "untitled 3")
        let long = String(repeating: "a", count: Int(NAME_MAX) - 4) + ".pdf"
        #expect(OpenFileSaves.name(long, attempt: 12) == String(repeating: "a", count: Int(NAME_MAX) - 7) + " 12.pdf")
    }

    @Test func aSaveCopiesTheFileAndLeavesItWhereItWas() throws {
        let folder = try temporaryDirectory()
        let downloads = try temporaryDirectory()
        defer {
            try? FileManager.default.removeItem(at: folder)
            try? FileManager.default.removeItem(at: downloads)
        }
        let file = folder.appending(path: "a b.pdf")
        try pdf.write(to: file)
        let copy = try OpenFileSaves.save(file, into: downloads)
        #expect(copy == downloads.appending(path: "a b.pdf"))
        #expect(FileManager.default.contents(atPath: copy.path) == pdf)
        #expect(FileManager.default.contents(atPath: file.path) == pdf)
    }

    /// A name already taken in Downloads is passed over, and what holds it is untouched.
    @Test func aSaveNeverReplacesAFile() throws {
        let folder = try temporaryDirectory()
        let downloads = try temporaryDirectory()
        defer {
            try? FileManager.default.removeItem(at: folder)
            try? FileManager.default.removeItem(at: downloads)
        }
        let file = folder.appending(path: "untitled.pdf")
        try pdf.write(to: file)
        for taken in ["untitled.pdf", "untitled 2.pdf"] {
            try Data(taken.utf8).write(to: downloads.appending(path: taken))
        }
        let copy = try OpenFileSaves.save(file, into: downloads)
        #expect(copy.lastPathComponent == "untitled 3.pdf")
        #expect(FileManager.default.contents(atPath: copy.path) == pdf)
        for taken in ["untitled.pdf", "untitled 2.pdf"] {
            #expect(FileManager.default.contents(atPath: downloads.appending(path: taken).path) == Data(taken.utf8))
        }
        let next = try OpenFileSaves.save(file, into: downloads)
        #expect(next.lastPathComponent == "untitled 4.pdf")
    }

    /// Once every name it may try is taken, a save fails and writes nothing.
    @Test func aSaveWithEveryNameTakenFails() throws {
        let folder = try temporaryDirectory()
        let downloads = try temporaryDirectory()
        defer {
            try? FileManager.default.removeItem(at: folder)
            try? FileManager.default.removeItem(at: downloads)
        }
        let file = folder.appending(path: "untitled.pdf")
        try pdf.write(to: file)
        for taken in ["untitled.pdf", "untitled 2.pdf"] {
            try Data(taken.utf8).write(to: downloads.appending(path: taken))
        }
        #expect(throws: OpenFileFailure(
            name: "untitled.pdf",
            reason: "no app on this Mac opens it, and Downloads already holds a file of every name it could be saved under"
        )) { try OpenFileSaves.save(file, into: downloads, attempts: 2) }
        #expect(try FileManager.default.contentsOfDirectory(atPath: downloads.path).sorted()
            == ["untitled 2.pdf", "untitled.pdf"])
    }

    /// A pinned revision's copy stays quarantined in Downloads, and its owner may write it.
    @Test func aSavedCopyKeepsItsQuarantineAndIsWritable() throws {
        let folder = try temporaryDirectory()
        let downloads = try temporaryDirectory()
        defer {
            try? FileManager.default.removeItem(at: folder)
            try? FileManager.default.removeItem(at: downloads)
        }
        let sealed = folder.appending(path: "untitled.pdf")
        try pdf.write(to: sealed)
        try OpenFileDownloads.seal(sealed)
        let copy = try OpenFileSaves.save(sealed, into: downloads)
        try expectQuarantinedAndWritable(copy)
        #expect(!FileManager.default.isWritableFile(atPath: sealed.path))  // the cached copy is as it was
    }

    /// The byte-by-byte copy, for another volume, keeps the same: it creates its file
    /// exclusively, with the source's bytes, quarantine, and mode.
    @Test func aCopyByBytesIsExclusiveAndKeepsAttributes() throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let sealed = folder.appending(path: "untitled.pdf")
        try pdf.write(to: sealed)
        try OpenFileDownloads.seal(sealed)
        let target = folder.appending(path: "copy.pdf")
        #expect(OpenFileSaves.copyBytes(sealed.path, to: target.path) == .placed)
        #expect(FileManager.default.contents(atPath: target.path) == pdf)
        let mode = try FileManager.default.attributesOfItem(atPath: target.path)[.posixPermissions] as? NSNumber
        #expect(mode?.intValue == 0o444)
        OpenFileSaves.ownerMayWrite(target.path)
        try expectQuarantinedAndWritable(target)
        // A name that is taken is left as it is.
        #expect(OpenFileSaves.copyBytes(sealed.path, to: target.path) == .taken)
        #expect(FileManager.default.contents(atPath: target.path) == pdf)
        #expect(OpenFileSaves.copyBytes(folder.appending(path: "gone.pdf").path, to: folder.appending(path: "x.pdf").path)
            == .failed(ENOENT))
        #expect(!FileManager.default.fileExists(atPath: folder.appending(path: "x.pdf").path))
    }

    /// A Downloads folder that cannot be written fails the save with the reason.
    @Test func aSaveThatCannotWriteSaysWhy() throws {
        let folder = try temporaryDirectory()
        let downloads = try temporaryDirectory()
        defer {
            try? FileManager.default.setAttributes([.posixPermissions: 0o755], ofItemAtPath: downloads.path)
            try? FileManager.default.removeItem(at: folder)
            try? FileManager.default.removeItem(at: downloads)
        }
        let file = folder.appending(path: "clip.mkv")
        try pdf.write(to: file)
        try FileManager.default.setAttributes([.posixPermissions: 0o555], ofItemAtPath: downloads.path)
        #expect(throws: OpenFileFailure(
            name: "clip.mkv", reason: "no app on this Mac opens it, and it could not be saved to Downloads (Permission denied)"
        )) { try OpenFileSaves.save(file, into: downloads) }
        #expect(try FileManager.default.contentsOfDirectory(atPath: downloads.path).isEmpty)
    }

    /// macOS's privacy system refuses a write to Downloads as `EPERM`: the alert says where
    /// to allow it, and nothing more.
    @Test func aPrivacyRefusalSaysWhereToAllowIt() {
        let failure = OpenFileSaves.failure("clip.mkv", EPERM)
        #expect(failure.message == "Could not open “clip.mkv”: no app on this Mac opens it, and Metabrowser is not "
            + "allowed to save to Downloads. Allow it in System Settings > Privacy & Security > Files & Folders.")
        #expect(failure.reveal == nil)
    }

    @Test func theNoticeSaysWhereTheFileWentAndWhy() {
        let saved = OpenFileSaved(copy: URL(filePath: "/tmp/sandbox/Downloads/clip 2.mkv"))
        #expect(saved.title == "Saved “clip 2.mkv” to Downloads")
        #expect(saved.message == "No app on this Mac opens this kind of file.")
    }

    private func expectQuarantinedAndWritable(_ file: URL) throws {
        let quarantine = try #require(try file.resourceValues(forKeys: [.quarantinePropertiesKey]).quarantineProperties)
        #expect(quarantine[kLSQuarantineAgentNameKey as String] as? String == "Metabrowser")
        #expect(quarantine[kLSQuarantineTypeKey as String] as? String == kLSQuarantineTypeWebDownload as String)
        let mode = try FileManager.default.attributesOfItem(atPath: file.path)[.posixPermissions] as? NSNumber
        #expect(mode?.intValue == 0o644)
        #expect(FileManager.default.isWritableFile(atPath: file.path))
    }
}

/// Which types a page's Open link opens in their default app.
@Suite struct OpenFileTypeTests {
    @Test func documentsAndMediaOpen() {
        for name in ["a.pdf", "a.PDF", "a.png", "a.jpeg", "a.heic", "a.gif", "a.tiff", "a.mp4", "a.mov", "a.mp3", "a.m4a", "a.wav"] {
            #expect(OpenFileTypes.allows(OpenFileTypes.type(named: name)), "\(name)")
        }
    }

    /// What runs or mounts something, an SVG, which runs scripts, and anything with no type.
    @Test func everythingElseIsRefused() {
        for name in [
            "a.command", "a.sh", "a.app", "a.pkg", "a.dmg", "a.webloc", "a.inetloc", "a.fileloc", "a.scpt",
            "a.terminal", "a.jar", "a.html", "a.txt", "a.svg", "a.m3u", "a", ".pdf", "a.",
        ] {
            #expect(!OpenFileTypes.allows(OpenFileTypes.type(named: name)), "\(name)")
        }
        #expect(!OpenFileTypes.allows(nil))
    }

    @Test func aFilesTypeIsLaunchServicesOwn() throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let file = folder.appending(path: "report.pdf")
        try Data("%PDF-1.4\n".utf8).write(to: file)
        #expect(OpenFileTypes.type(of: file) == .pdf)
        #expect(OpenFileTypes.type(of: folder.appending(path: "gone.png")) == .png)
    }
}

/// The copies an Open link downloads, apart from WebKit.
@Suite struct OpenedCopiesTests {
    @Test func theyLiveInTheAppsCachesFolder() {
        let caches = URL(filePath: "/tmp/sandbox/Library/Caches", directoryHint: .isDirectory)
        #expect(OpenFileDownloads.directory(bundleIdentifier: "io.example.app", caches: caches).path
            == "/tmp/sandbox/Library/Caches/io.example.app/Opened")
    }

    @Test func aCopyIsQuarantinedAndReadOnly() throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let copy = folder.appending(path: "report.pdf")
        try Data("%PDF-1.4\n".utf8).write(to: copy)
        try OpenFileDownloads.seal(copy)
        let quarantine = try #require(try copy.resourceValues(forKeys: [.quarantinePropertiesKey]).quarantineProperties)
        #expect(quarantine[kLSQuarantineAgentNameKey as String] as? String == "Metabrowser")
        #expect(quarantine[kLSQuarantineTypeKey as String] as? String == kLSQuarantineTypeWebDownload as String)
        let mode = try FileManager.default.attributesOfItem(atPath: copy.path)[.posixPermissions] as? NSNumber
        #expect(mode?.intValue == 0o444)
        #expect(!FileManager.default.isWritableFile(atPath: copy.path))
    }

    /// A sweep removes each copy's folder made more than `kept` ago, read-only copy and
    /// all, and keeps the newer ones.
    @Test func aSweepRemovesOnlyOldCopies() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let now = Date()
        var folders: [URL] = []
        for age in [OpenFileDownloads.kept + 60, OpenFileDownloads.kept - 60] {
            let folder = directory.appending(path: UUID().uuidString, directoryHint: .isDirectory)
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
            let copy = folder.appending(path: "report.pdf")
            try Data("%PDF-1.4\n".utf8).write(to: copy)
            try OpenFileDownloads.seal(copy)
            try FileManager.default.setAttributes([.creationDate: now.addingTimeInterval(-age)], ofItemAtPath: folder.path)
            folders.append(folder)
        }
        OpenFileDownloads.sweep(directory, now: now)
        #expect(!FileManager.default.fileExists(atPath: folders[0].path))
        #expect(FileManager.default.fileExists(atPath: folders[1].appending(path: "report.pdf").path))
        OpenFileDownloads.sweep(directory.appending(path: "missing"), now: now)  // nothing to sweep
    }
}

/// The descriptor's script, apart from WebKit.
@Suite struct HostDescriptorTests {
    @Test func anActionIsAPlainName() {
        #expect(HostDescriptor.isActionName(OpenFileRequests.action))
        for name in ["", "Open", "open file", "open_file", "\"x", "o\\"] {
            #expect(!HostDescriptor.isActionName(name), "\(name)")
        }
    }

    @Test func theScriptNamesEachActionAndFreezesThem() {
        let source = HostDescriptor.source(actions: ["open-file", "reveal"])
        #expect(source.contains(#"Object.freeze(["open-file", "reveal"])"#))
        #expect(source.contains("writable: false"))
        #expect(source.contains("configurable: false"))
    }
}
