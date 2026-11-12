import Darwin
import Foundation
import Testing
@testable import ShellCore

@Suite struct NavigationPolicyTests {
    private let policy = NavigationPolicy(origin: URL(string: "http://127.0.0.1:8412")!)
    private func url(_ text: String) -> URL { URL(string: text)! }

    @Test func sameOriginStaysInTheWindow() {
        #expect(policy.decide(url("http://127.0.0.1:8412/view/docs/"), isMainFrame: true, isLinkClick: true) == .allow)
        #expect(policy.decide(url("HTTP://127.0.0.1:8412/api/x"), isMainFrame: true, isLinkClick: false) == .allow)
    }

    @Test func aClickedLinkToAnotherOriginGoesToTheDefaultBrowser() {
        for other in [
            "http://127.0.0.1:8411/view/", "http://localhost:8412/view/", "https://127.0.0.1:8412/",
            "https://github.com/jlevy/metabrowser", "mailto:someone@example.com",
        ] {
            #expect(policy.decide(url(other), isMainFrame: true, isLinkClick: true) == .openExternally(url(other)))
        }
    }

    @Test func scriptsRedirectsAndHistoryCannotOpenTheBrowser() {
        // window.location, a redirect, a form, or Back to a server that restarted on a new
        // port: none was a click on a link, so each is cancelled.
        for other in ["https://example.com/", "http://127.0.0.1:8399/view/old.md"] {
            #expect(policy.decide(url(other), isMainFrame: true, isLinkClick: false) == .cancel)
        }
    }

    @Test func fileAndUnknownSchemesAreCancelled() {
        #expect(policy.decide(url("file:///etc/passwd"), isMainFrame: true, isLinkClick: true) == .cancel)
        #expect(policy.decide(url("vscode://file/x"), isMainFrame: true, isLinkClick: true) == .cancel)
        #expect(policy.decide(nil, isMainFrame: true, isLinkClick: true) == .cancel)
    }

    @Test func subframesBlankAndDownloadsAreLeftToWebKit() {
        #expect(policy.decide(url("https://example.com/embed"), isMainFrame: false, isLinkClick: false) == .allow)
        #expect(policy.decide(url("about:blank"), isMainFrame: true, isLinkClick: false) == .allow)
        #expect(policy.decide(
            url("http://127.0.0.1:8412/raw/a.zip"), isMainFrame: true, isLinkClick: true, shouldDownload: true)
            == .download)
    }

    @Test func commandClickOpensAnotherWindowOfTheFolder() {
        let target = url("http://127.0.0.1:8412/view/a.md")
        #expect(policy.decide(target, isMainFrame: true, isLinkClick: true, wantsNewWindow: true)
            == .openInNewWindow(target))
        let outside = url("https://example.com")
        #expect(policy.decide(outside, isMainFrame: true, isLinkClick: true, wantsNewWindow: true)
            == .openExternally(outside))
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
        #expect(early.decide(url("http://127.0.0.1:8412/view/"), isMainFrame: true, isLinkClick: false) == .cancel)
    }

    @Test func rebaseMovesAPageToTheRestartedServer() {
        let moved = NavigationPolicy.rebase(
            url("http://127.0.0.1:8412/view/docs/a%20b.md?mode=raw#top"), onto: url("http://127.0.0.1:8415"))
        #expect(moved?.absoluteString == "http://127.0.0.1:8415/view/docs/a%20b.md?mode=raw#top")
    }

    @Test func contentRecoveryIsBudgeted() {
        var budget = RecoveryBudget(limit: 2, within: .seconds(30))
        let start = ContinuousClock.now
        let allowed = [0, 1, 2, 31].map { budget.allow(at: start.advanced(by: .seconds($0))) }
        #expect(allowed == [true, true, false, true])
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

    @Test func aFoldersLogIsInTheGivenFolder() {
        let folder = URL(filePath: "/Volumes/Home/Library/Logs/Metabrowser", directoryHint: .isDirectory)
        let log = ServerLog.url(for: URL(filePath: "/tmp/notes"), in: folder)
        #expect(log.deletingLastPathComponent().path(percentEncoded: false) == folder.path(percentEncoded: false))
        #expect(log.lastPathComponent == ServerLog.fileName(for: URL(filePath: "/tmp/notes")))
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
        try ServerLog.append("started pid 7", to: log, now: Date(timeIntervalSince1970: 0))
        #expect(try String(contentsOf: log, encoding: .utf8) == "[metabrowser-app 1970-01-01T00:00:00Z] started pid 7\n")
    }
}
