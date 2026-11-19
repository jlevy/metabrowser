import Foundation
import WebKit

/// Find on the page (the Find menu, mb-jkbp), through WebKit's public `WKWebView.find`.
///
/// The window used to give AppKit's `NSTextFinder` its web view as the client. `WKWebView`
/// does not adopt `NSTextFinderClient`: it answers `NSTextFinder`'s asynchronous find only
/// with its platform find UI turned off, which is private, and in a probe of the app's
/// setup on macOS 26.5 (2026-11-18) the bar found nothing on a Metabrowser page, while
/// `find` found and selected the same word. So the window keeps its own search string and
/// asks `find` for each step.
///
/// It searches as a browser's find does: the whole page, the navigation pane included,
/// case-insensitively, from the selection, wrapping at either end. A new search string
/// starts at the start of the current match, so typing on extends the match where it is;
/// Next and Previous move on from it.
@MainActor public final class PageFind {
    public enum Step: Sendable { case next, previous }

    /// The search string, which Next and Previous look for.
    public private(set) var query = ""

    public init() {}

    /// Search for `text` from the start of the current match, as typing in the find field
    /// does. Nil when `text` is empty, which searches for nothing.
    public func search(_ text: String, in webView: WKWebView) async -> Bool? {
        query = text
        guard !text.isEmpty else { return nil }
        _ = try? await webView.evaluateJavaScript(Self.collapseSelectionToStart)
        return await find(text, backwards: false, in: webView)
    }

    /// Find the search string's next or previous match. Nil without a search string.
    public func step(_ step: Step, in webView: WKWebView) async -> Bool? {
        guard !query.isEmpty else { return nil }
        return await find(query, backwards: step == .previous, in: webView)
    }

    /// Make `text` the search string without searching, as Use Selection for Find does.
    public func use(_ text: String) {
        query = text
    }

    /// The page's selected text, or nil when nothing is selected.
    public func selection(in webView: WKWebView) async -> String? {
        let text = try? await webView.evaluateJavaScript("getSelection().toString()") as? String
        guard let text, !text.isEmpty else { return nil }
        return text
    }

    private func find(_ text: String, backwards: Bool, in webView: WKWebView) async -> Bool {
        let configuration = WKFindConfiguration()
        configuration.backwards = backwards
        configuration.caseSensitive = false
        configuration.wraps = true
        return await withCheckedContinuation { continuation in
            webView.find(text, configuration: configuration) { continuation.resume(returning: $0.matchFound) }
        }
    }

    /// `find` searches on from the selection's end, so a longer search string would skip
    /// the match it extends; from its start, it finds that match again.
    static let collapseSelectionToStart =
        "(() => { const selection = getSelection(); if (selection.rangeCount) selection.collapseToStart(); return true })()"
}
