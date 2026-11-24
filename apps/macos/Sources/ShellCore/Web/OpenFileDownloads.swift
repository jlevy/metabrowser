import CoreServices
import Foundation
import WebKit

/// The read-only copies a page's Open link downloads, for a file with no folder on disk: a
/// pinned revision's, or a mirror's (`OpenFilePlan.downloadThenOpen`).
///
/// The page's own web view downloads the link (`WKWebView.startDownload`), so the request
/// carries the page's cookies, as the server's authorization requires. Each copy goes to a
/// folder of its own under `directory`, `<unique>/<name>`, so two copies of one name never
/// meet and none replaces a file. The name is the link's, with the extension of the type
/// the server answered with where the link's name gives none or another
/// (`OpenFileTypes.copyName`), so a PDF named `untitled` is kept as `untitled.pdf`. A
/// finished copy is marked as downloaded from the web (`seal`), is made read-only, since
/// editing it would change nothing the page shows, and is checked against `OpenFileTypes`
/// by the type Launch Services gives it, by that name, before the caller opens it. A
/// failed copy leaves nothing behind.
///
/// It is the delegate only of the downloads it starts, so a link with a plain `download`
/// attribute, which `DownloadCoordinator` answers with a save panel, never reaches it. One
/// serves every window, because `WKDownload.delegate` is weak and a download can outlive
/// the window that started it.
public final class OpenFileDownloads: NSObject, WKDownloadDelegate {
    /// How long a copy is kept: a day, so a copy is still there while it is read in its
    /// app, and the folder holds no more than a day of them. `sweep` removes older ones.
    public nonisolated static let kept: TimeInterval = 24 * 60 * 60

    /// `Caches/<bundle identifier>/Opened/` in `caches`, the user's caches folder.
    public nonisolated static func directory(
        bundleIdentifier: String,
        caches: URL = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask)[0]
    ) -> URL {
        caches.appending(path: bundleIdentifier, directoryHint: .isDirectory)
            .appending(path: "Opened", directoryHint: .isDirectory)
    }

    /// Gets the finished copy, or why there is none.
    public typealias Finished = (Result<URL, OpenFileFailure>) -> Void

    private struct Pending {
        let name: String
        /// The copy's own folder, which a failure removes.
        let folder: URL
        let finished: Finished
        /// Where WebKit writes, once the response has come.
        var destination: URL?
        /// Why the response was declined, which the failure that follows reports.
        var declined: String?
    }

    public let directory: URL
    private var pending: [ObjectIdentifier: Pending] = [:]

    public init(directory: URL) {
        self.directory = directory
    }

    /// Downloads `href` in `webView` to a copy of `name`, named by the type it is served
    /// as (`OpenFileTypes.copyName`), and calls `finished` once.
    public func start(_ href: URL, named name: String, in webView: WKWebView, finished: @escaping Finished) {
        let folder = directory.appending(path: UUID().uuidString, directoryHint: .isDirectory)
        do {
            try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        } catch {
            return finished(.failure(OpenFileFailure(
                name: name, reason: "there is no place to keep a copy (\(error.localizedDescription))")))
        }
        // The delegate is set in the completion handler, as `DownloadTests` explains:
        // WebKit asks for a destination as soon as the response arrives.
        webView.startDownload(using: URLRequest(url: href)) { [weak self] download in
            guard let self else { return }
            download.delegate = self
            pending[ObjectIdentifier(download)] = Pending(name: name, folder: folder, finished: finished)
        }
    }

    public func download(
        _ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String,
        completionHandler: @escaping @MainActor (URL?) -> Void
    ) {
        let key = ObjectIdentifier(download)
        guard var entry = pending[key] else { return completionHandler(nil) }
        if let status = (response as? HTTPURLResponse)?.statusCode, !(200..<300).contains(status) {
            // Declined: the failure that follows reports it.
            entry.declined = "the folder’s server answered \(HTTPURLResponse.localizedString(forStatusCode: status)) (\(status))"
            pending[key] = entry
            return completionHandler(nil)
        }
        let name = OpenFileTypes.copyName(entry.name, servedAs: response.mimeType)
        let destination = entry.folder.appending(path: name, directoryHint: .notDirectory)
        entry.destination = destination
        pending[key] = entry
        completionHandler(destination)
    }

    public func downloadDidFinish(_ download: WKDownload) {
        guard let entry = pending.removeValue(forKey: ObjectIdentifier(download)), let copy = entry.destination
        else { return }
        let failure: OpenFileFailure
        do {
            try Self.seal(copy)
            guard OpenFileTypes.allows(OpenFileTypes.type(of: copy)) else {
                throw OpenFileFailure(name: entry.name, reason: OpenFileTypes.refusal)
            }
            return entry.finished(.success(copy))
        } catch let refused as OpenFileFailure {
            failure = refused
        } catch {
            failure = OpenFileFailure(
                name: entry.name, reason: "its copy could not be made read-only (\(error.localizedDescription))")
        }
        try? FileManager.default.removeItem(at: entry.folder)
        entry.finished(.failure(failure))
    }

    /// A declined response ends here too, as a cancellation, and reports why it was
    /// declined.
    public func download(_ download: WKDownload, didFailWithError error: any Error, resumeData: Data?) {
        guard let entry = pending.removeValue(forKey: ObjectIdentifier(download)) else { return }
        try? FileManager.default.removeItem(at: entry.folder)
        let reason = entry.declined ?? "its download failed (\(error.localizedDescription))"
        entry.finished(.failure(OpenFileFailure(name: entry.name, reason: reason)))
    }

    /// Marks `copy` as a web download by Metabrowser, as Gatekeeper reads quarantine, and
    /// makes it read-only (0444), in that order: a file its owner cannot write takes no
    /// new extended attribute. The app sets no `LSFileQuarantineEnabled`, which would
    /// quarantine everything its servers write (Info.plist), so it marks each copy itself.
    public nonisolated static func seal(_ copy: URL) throws {
        var values = URLResourceValues()
        values.quarantineProperties = [
            kLSQuarantineAgentNameKey as String: "Metabrowser",
            kLSQuarantineTypeKey as String: kLSQuarantineTypeWebDownload as String,
        ]
        var marked = copy
        try marked.setResourceValues(values)
        try FileManager.default.setAttributes([.posixPermissions: 0o444], ofItemAtPath: copy.path(percentEncoded: false))
    }

    /// Removes each copy's folder in `directory` made more than `kept` before `now`, and
    /// leaves the rest. A folder that cannot be read or removed is left for a later sweep.
    public nonisolated static func sweep(_ directory: URL, keeping kept: TimeInterval = kept, now: Date = Date()) {
        let fileManager = FileManager.default
        guard let folders = try? fileManager.contentsOfDirectory(
            at: directory, includingPropertiesForKeys: [.creationDateKey, .isDirectoryKey])
        else { return }
        for folder in folders {
            guard let values = try? folder.resourceValues(forKeys: [.creationDateKey, .isDirectoryKey]),
                  values.isDirectory == true, let made = values.creationDate, now.timeIntervalSince(made) > kept
            else { continue }
            try? fileManager.removeItem(at: folder)
        }
    }
}
