import Foundation
import Testing
import WebKit
@testable import ShellCore

/// Downloads through a real `WKDownload` from a local server, with the save panel
/// replaced by a fixed answer.
@Suite struct DownloadTests {
    private let original = Data("the original file\n".utf8)
    private let replacement = Data("the new download\n".utf8)

    /// A coordinator that saves to `destination` and records each failure it reports.
    private func coordinator(saving destination: URL, failures: Recorder<DownloadFailure>) -> DownloadCoordinator {
        DownloadCoordinator(
            chooseDestination: { _, _, answer in answer(destination) },
            reportFailure: { _, failure in failures.append(failure) })
    }

    private func start(_ url: URL, with downloads: DownloadCoordinator, in webView: WKWebView) async -> WKDownload {
        let download = await webView.startDownload(using: URLRequest(url: url))
        download.delegate = downloads
        return download
    }

    private func contents(_ url: URL) -> Data? { FileManager.default.contents(atPath: url.path) }

    /// The defect this guards: confirming Replace used to delete the original before the
    /// transfer began, so a transfer that then failed left only its partial bytes.
    @Test func aReplacementThatFailsMidwayKeepsTheOriginal() async throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let destination = folder.appending(path: "report.bin")
        try original.write(to: destination)
        let server = try LocalHTTPServer(body: replacement, declaredLength: 10_000)
        defer { server.stop() }
        let url = await server.start()
        let failures = Recorder<DownloadFailure>()
        let downloads = coordinator(saving: destination, failures: failures)
        let webView = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())

        _ = await start(url, with: downloads, in: webView)
        await server.waitUntilSent()
        #expect(await eventually { downloads.replacementsInProgress.count == 1 })
        let staged = try #require(downloads.replacementsInProgress.first)
        #expect(staged.destination == destination)
        #expect(contents(destination) == original)  // still there while the transfer runs
        server.release()  // the connection drops after part of the file

        #expect(await eventually { failures.count == 1 })
        #expect(contents(destination) == original)
        #expect(failures.all.first?.keptExisting == true)
        #expect(failures.all.first?.destination == destination)
        #expect(downloads.replacementsInProgress.isEmpty)
        #expect(!FileManager.default.fileExists(atPath: staged.directory.path))
        withExtendedLifetime(webView) {}
    }

    @Test func aCancelledReplacementKeepsTheOriginal() async throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let destination = folder.appending(path: "report.bin")
        try original.write(to: destination)
        let server = try LocalHTTPServer(body: replacement, declaredLength: 10_000)
        defer {
            server.release()
            server.stop()
        }
        let url = await server.start()
        let failures = Recorder<DownloadFailure>()
        let downloads = coordinator(saving: destination, failures: failures)
        let webView = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())

        let download = await start(url, with: downloads, in: webView)
        #expect(await eventually { downloads.replacementsInProgress.count == 1 })
        let staged = try #require(downloads.replacementsInProgress.first)
        await downloads.cancel(download)

        #expect(downloads.replacementsInProgress.isEmpty)
        #expect(contents(destination) == original)
        #expect(!FileManager.default.fileExists(atPath: staged.directory.path))
        #expect(failures.count == 0)
        withExtendedLifetime(webView) {}
    }

    @Test func aFinishedReplacementTakesTheOriginalsPlace() async throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let destination = folder.appending(path: "report.bin")
        try original.write(to: destination)
        let server = try LocalHTTPServer(body: replacement)
        defer { server.stop() }
        let url = await server.start()
        let failures = Recorder<DownloadFailure>()
        let downloads = coordinator(saving: destination, failures: failures)
        let webView = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())

        _ = await start(url, with: downloads, in: webView)
        #expect(await eventually { contents(destination) == replacement })
        #expect(await eventually { downloads.replacementsInProgress.isEmpty })
        #expect(failures.count == 0)
        #expect(try FileManager.default.contentsOfDirectory(atPath: folder.path) == ["report.bin"])
        withExtendedLifetime(webView) {}
    }

    @Test func aNewFileIsWrittenInPlace() async throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let destination = folder.appending(path: "report.bin")
        let server = try LocalHTTPServer(body: replacement)
        defer { server.stop() }
        let url = await server.start()
        let failures = Recorder<DownloadFailure>()
        let downloads = coordinator(saving: destination, failures: failures)
        let webView = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())

        _ = await start(url, with: downloads, in: webView)
        #expect(await eventually { contents(destination) == replacement })
        #expect(downloads.replacementsInProgress.isEmpty)
        #expect(failures.count == 0)
        withExtendedLifetime(webView) {}
    }

    @Test func aDeclinedSavePanelDownloadsNothing() async throws {
        let server = try LocalHTTPServer(body: replacement)
        defer { server.stop() }
        let url = await server.start()
        let failures = Recorder<DownloadFailure>()
        let downloads = DownloadCoordinator(
            chooseDestination: { _, _, answer in answer(nil) },
            reportFailure: { _, failure in failures.append(failure) })
        let webView = WKWebView(frame: .zero, configuration: WKWebViewConfiguration())
        _ = await start(url, with: downloads, in: webView)
        try await Task.sleep(for: .milliseconds(300))  // WebKit reports the decline as a cancellation
        #expect(failures.count == 0)  // which needs no alert
        #expect(downloads.replacementsInProgress.isEmpty)
        withExtendedLifetime(webView) {}
    }
}

@Suite struct StagedDownloadTests {
    @Test func aFreeDestinationNeedsNoStaging() throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        #expect(try StagedDownload.prepare(for: folder.appending(path: "new.bin")) == nil)
    }

    @Test func aDanglingSymlinkIsReplacedLikeAFile() throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let destination = folder.appending(path: "link.bin")
        try FileManager.default.createSymbolicLink(atPath: destination.path, withDestinationPath: "/nonexistent/target")
        let staged = try #require(try StagedDownload.prepare(for: destination))
        try Data("new".utf8).write(to: staged.staging)
        try staged.commit()
        #expect(FileManager.default.contents(atPath: destination.path) == Data("new".utf8))
    }

    @Test func stagingIsOnTheDestinationsVolumeAndApartFromIt() throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let destination = folder.appending(path: "report.bin")
        try Data("old".utf8).write(to: destination)
        let staged = try #require(try StagedDownload.prepare(for: destination))
        defer { staged.discard() }
        #expect(staged.staging.lastPathComponent == "report.bin")
        #expect(staged.staging.deletingLastPathComponent() == staged.directory)
        #expect(staged.directory.standardizedFileURL != folder.standardizedFileURL)
        let volume: (URL) throws -> AnyHashable? = { try $0.resourceValues(forKeys: [.volumeIdentifierKey]).volumeIdentifier as? AnyHashable }
        #expect(try volume(staged.directory) == volume(folder))
    }

    /// A destination that cannot be replaced (here a folder with something in it) stays
    /// as it was, and the staged bytes go away.
    @Test func aFailedCommitKeepsTheDestination() throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let destination = folder.appending(path: "taken", directoryHint: .isDirectory)
        try FileManager.default.createDirectory(at: destination, withIntermediateDirectories: true)
        try Data("keep".utf8).write(to: destination.appending(path: "inside.txt"))
        let staged = try #require(try StagedDownload.prepare(for: destination))
        try Data("new".utf8).write(to: staged.staging)
        #expect(throws: POSIXError.self) { try staged.commit() }
        #expect(FileManager.default.contents(atPath: destination.appending(path: "inside.txt").path) == Data("keep".utf8))
        #expect(!FileManager.default.fileExists(atPath: staged.directory.path))
    }

    @Test func discardRemovesThePartialDownload() throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let destination = folder.appending(path: "report.bin")
        try Data("old".utf8).write(to: destination)
        let staged = try #require(try StagedDownload.prepare(for: destination))
        try Data("part".utf8).write(to: staged.staging)
        staged.discard()
        #expect(!FileManager.default.fileExists(atPath: staged.directory.path))
        #expect(FileManager.default.contents(atPath: destination.path) == Data("old".utf8))
    }
}
