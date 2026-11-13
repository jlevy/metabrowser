import Foundation
import WebKit

/// Why a download did not produce the file the user chose.
public nonisolated struct DownloadFailure: Equatable, Sendable {
    /// Where the user chose to save, if the download got that far.
    public var destination: URL?
    /// Whether a file already at `destination` was left as it was.
    public var keptExisting: Bool
    public var reason: String

    public init(destination: URL?, keptExisting: Bool, reason: String) {
        self.destination = destination
        self.keptExisting = keptExisting
        self.reason = reason
    }

    /// One sentence or two for an alert.
    public var message: String {
        let name = destination.map { "“\($0.lastPathComponent)”" } ?? "the file"
        let kept = keptExisting ? " The existing \(name) was not changed." : ""
        let because = reason.hasSuffix(".") ? String(reason.dropLast()) : reason
        return "Could not download \(name): \(because).\(kept)"
    }
}

/// Where downloads go, and replacing an existing file only once the new one is complete.
///
/// A destination that already exists gets a `StagedDownload`: `WKDownload` writes to the
/// staging file, `downloadDidFinish` renames it over the destination, and a failure
/// removes it, so a failed, cancelled, or interrupted replacement never costs the
/// original. One coordinator serves every window, because `WKDownload.delegate` is weak
/// and a download can outlive the window that started it.
public final class DownloadCoordinator: NSObject, WKDownloadDelegate {
    /// Asks where to save the download, given WebKit's suggested file name, and answers
    /// with the chosen URL or nil. The app shows a save panel.
    public typealias ChooseDestination = (
        _ download: WKDownload, _ suggestedFilename: String, _ answer: @escaping (URL?) -> Void
    ) -> Void
    /// Tells the user a download did not produce its file.
    public typealias ReportFailure = (_ download: WKDownload, _ failure: DownloadFailure) -> Void

    private struct Pending {
        let destination: URL
        let replacement: StagedDownload?
    }

    private let chooseDestination: ChooseDestination
    private let reportFailure: ReportFailure
    private var pending: [ObjectIdentifier: Pending] = [:]

    public init(chooseDestination: @escaping ChooseDestination, reportFailure: @escaping ReportFailure) {
        self.chooseDestination = chooseDestination
        self.reportFailure = reportFailure
    }

    /// The replacements still being downloaded, each with its staging file.
    public var replacementsInProgress: [StagedDownload] { pending.values.compactMap(\.replacement) }

    public func download(
        _ download: WKDownload, decideDestinationUsing response: URLResponse, suggestedFilename: String,
        completionHandler: @escaping @MainActor (URL?) -> Void
    ) {
        chooseDestination(download, suggestedFilename) { [weak self] destination in
            guard let self, let destination else { return completionHandler(nil) }
            let replacement: StagedDownload?
            do {
                replacement = try StagedDownload.prepare(for: destination)
            } catch {
                self.reportFailure(
                    download,
                    DownloadFailure(
                        destination: destination, keptExisting: true,
                        reason: "no place to download it beside the existing file (\(error.localizedDescription))"))
                return completionHandler(nil)
            }
            self.pending[ObjectIdentifier(download)] = Pending(destination: destination, replacement: replacement)
            completionHandler(replacement?.staging ?? destination)
        }
    }

    public func downloadDidFinish(_ download: WKDownload) {
        guard let finished = pending.removeValue(forKey: ObjectIdentifier(download)),
              let replacement = finished.replacement
        else { return }
        do {
            try replacement.commit()
        } catch {
            reportFailure(
                download,
                DownloadFailure(
                    destination: finished.destination, keptExisting: true,
                    reason: "it could not replace the existing file (\(error.localizedDescription))"))
        }
    }

    /// A declined save panel also ends here, as a cancellation, which is not reported.
    public func download(_ download: WKDownload, didFailWithError error: any Error, resumeData: Data?) {
        let failed = pending.removeValue(forKey: ObjectIdentifier(download))
        failed?.replacement?.discard()
        let error = error as NSError
        guard !(error.domain == NSURLErrorDomain && error.code == NSURLErrorCancelled) else { return }
        reportFailure(
            download,
            DownloadFailure(
                destination: failed?.destination, keptExisting: failed?.replacement != nil,
                reason: error.localizedDescription))
    }

    /// Stops `download` and removes what it staged. `WKDownload.cancel` itself calls no
    /// delegate method, so a cancel that bypassed this would leave the staging file.
    public func cancel(_ download: WKDownload) async {
        _ = await download.cancel()
        pending.removeValue(forKey: ObjectIdentifier(download))?.replacement?.discard()
    }
}
