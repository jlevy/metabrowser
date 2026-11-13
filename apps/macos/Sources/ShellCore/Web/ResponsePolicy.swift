import Foundation

/// Whether a main-frame response is shown in the window or saved as a download.
public nonisolated enum ResponsePolicy: Equatable, Sendable {
    case show
    case download

    /// A response WebKit cannot show, or one the server marks `Content-Disposition:
    /// attachment` (Metabrowser's raw-file downloads), is a download. Only the
    /// disposition type counts: RFC 6266 makes it the case-insensitive token before the
    /// first `;`, so a parameter that mentions "attachment" changes nothing.
    public static func decide(canShowMIMEType: Bool, contentDisposition: String?) -> ResponsePolicy {
        let type = contentDisposition?.split(separator: ";", maxSplits: 1, omittingEmptySubsequences: false).first
            .map { $0.trimmingCharacters(in: .whitespaces).lowercased() }
        return canShowMIMEType && type != "attachment" ? .show : .download
    }
}
