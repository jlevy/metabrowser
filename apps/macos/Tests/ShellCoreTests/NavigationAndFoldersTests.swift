import Darwin
import Foundation
import Testing
@testable import ShellCore

@Suite struct NavigationPolicyTests {
    private let policy = NavigationPolicy(origin: URL(string: "http://127.0.0.1:8412")!)
    private func url(_ text: String) -> URL { URL(string: text)! }

    @Test func sameOriginStaysInTheWindow() {
        #expect(policy.decide(url("http://127.0.0.1:8412/view/docs/"), isMainFrame: true) == .allow)
        #expect(policy.decide(url("HTTP://127.0.0.1:8412/api/x"), isMainFrame: true) == .allow)
    }

    @Test func anotherPortOrHostIsAnotherOrigin() {
        for other in ["http://127.0.0.1:8411/view/", "http://localhost:8412/view/", "https://127.0.0.1:8412/"] {
            #expect(policy.decide(url(other), isMainFrame: true) == .openExternally(url(other)))
        }
    }

    @Test func webAndMailLinksGoToTheDefaultBrowser() {
        let link = url("https://github.com/jlevy/metabrowser")
        #expect(policy.decide(link, isMainFrame: true) == .openExternally(link))
        let mail = url("mailto:someone@example.com")
        #expect(policy.decide(mail, isMainFrame: true) == .openExternally(mail))
    }

    @Test func fileAndUnknownSchemesAreCancelled() {
        #expect(policy.decide(url("file:///etc/passwd"), isMainFrame: true) == .cancel)
        #expect(policy.decide(url("vscode://file/x"), isMainFrame: true) == .cancel)
        #expect(policy.decide(nil, isMainFrame: true) == .cancel)
    }

    @Test func subframesBlankAndDownloadsAreLeftToWebKit() {
        #expect(policy.decide(url("https://example.com/embed"), isMainFrame: false) == .allow)
        #expect(policy.decide(url("about:blank"), isMainFrame: true) == .allow)
        #expect(policy.decide(url("http://127.0.0.1:8412/raw/a.zip"), isMainFrame: true, shouldDownload: true)
            == .download)
    }

    @Test func commandClickOpensAnotherWindowOfTheFolder() {
        let target = url("http://127.0.0.1:8412/view/a.md")
        #expect(policy.decide(target, isMainFrame: true, wantsNewWindow: true) == .openInNewWindow(target))
        let outside = url("https://example.com")
        #expect(policy.decide(outside, isMainFrame: true, wantsNewWindow: true) == .openExternally(outside))
    }

    @Test func newWindowRequests() {
        let inside = url("http://127.0.0.1:8412/view/b.md")
        #expect(policy.decideNewWindow(inside) == .openInNewWindow(inside))
        let outside = url("https://example.com")
        #expect(policy.decideNewWindow(outside) == .openExternally(outside))
        #expect(policy.decideNewWindow(url("javascript:alert(1)")) == .cancel)
        #expect(policy.decideNewWindow(nil) == .cancel)
    }

    @Test func nothingIsTheAppOriginBeforeTheServerIsReady() {
        let early = NavigationPolicy()
        #expect(early.decide(url("http://127.0.0.1:8412/view/"), isMainFrame: true)
            == .openExternally(url("http://127.0.0.1:8412/view/")))
    }

    @Test func rebaseMovesAPageToTheRestartedServer() {
        let moved = NavigationPolicy.rebase(
            url("http://127.0.0.1:8412/view/docs/a%20b.md?mode=raw#top"), onto: url("http://127.0.0.1:8415"))
        #expect(moved?.absoluteString == "http://127.0.0.1:8415/view/docs/a%20b.md?mode=raw#top")
    }
}

@Suite struct RecentFoldersTests {
    @Test func newestFirstWithoutDuplicatesAndBounded() {
        var folders = RecentFolders(limit: 3)
        for path in ["/a", "/b", "/c", "/a", "/d"] { folders.add(path) }
        #expect(folders.paths == ["/d", "/a", "/c"])
        folders.remove("/a")
        #expect(folders.paths == ["/d", "/c"])
        folders.clear()
        #expect(folders.paths.isEmpty)
    }

    @Test func initialListKeepsItsOrder() {
        #expect(RecentFolders(paths: ["/x", "/y", "/x"]).paths == ["/x", "/y"])
    }

    @Test func menuShowsOnlyFoldersThatExist() {
        let folders = RecentFolders(paths: ["/gone", "/here"])
        #expect(folders.existing { $0 == "/here" } == ["/here"])
        #expect(folders.paths == ["/gone", "/here"])
    }
}

@Suite struct ServerLogTests {
    @Test func fileNameIsReadableAndDistinctPerPath() {
        let first = ServerLog.fileName(for: URL(filePath: "/tmp/one/My Notes!"))
        let second = ServerLog.fileName(for: URL(filePath: "/tmp/two/My Notes!"))
        #expect(first.hasPrefix("My-Notes-"))
        #expect(first.hasSuffix(".log"))
        #expect(first != second)
        #expect(first == ServerLog.fileName(for: URL(filePath: "/tmp/one/My Notes!")))
        #expect(ServerLog.fileName(for: URL(filePath: "/")).hasPrefix("root-"))
    }

    @Test func directoryIsUnderLibraryLogs() {
        #expect(ServerLog.directory(home: URL(filePath: "/Volumes/Home")).path(percentEncoded: false)
            == "/Volumes/Home/Library/Logs/Metabrowser/")
    }

    @Test func prepareCreatesPrivateFilesAndTightensLooseOnes() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let log = directory.appending(path: "Logs/Metabrowser/x.log")
        try ServerLog.prepare(log)
        func mode(_ url: URL) throws -> Int? {
            try FileManager.default.attributesOfItem(atPath: url.path)[.posixPermissions] as? Int
        }
        #expect(try mode(log) == 0o600)
        #expect(try mode(log.deletingLastPathComponent()) == 0o700)
        chmod(log.path, 0o644)
        try ServerLog.prepare(log)
        #expect(try mode(log) == 0o600)
    }

    @Test func prepareRotatesALargeLog() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let log = directory.appending(path: "x.log")
        try ServerLog.prepare(log)
        try Data(repeating: 0x61, count: 64).write(to: log)
        try ServerLog.prepare(log, rotateAbove: 32)
        #expect(try Data(contentsOf: log).isEmpty)
        #expect(try Data(contentsOf: directory.appending(path: "x.log.1")).count == 64)
    }

    @Test func appendWritesOneStampedLine() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let log = directory.appending(path: "x.log")
        try ServerLog.prepare(log)
        ServerLog.append("started pid 7", to: log, now: Date(timeIntervalSince1970: 0))
        #expect(try String(contentsOf: log, encoding: .utf8) == "[metabrowser-app 1970-01-01T00:00:00Z] started pid 7\n")
    }
}
