import Foundation

/// Which items dropped on a folder window the app opens itself, as File > Open would,
/// rather than handing them to the page.
///
/// WebKit's own answer to a dropped file is to navigate to its `file://` URL, which the
/// navigation policy cancels, so a dropped file did nothing. The drop is the user's
/// gesture, so the app opens it: a folder as its own root, and a file at its page in the
/// folder that holds it (`OpenTarget`). A page never opens a file by itself this way.
public nonisolated enum FileDrop {
    /// `fileURLs` when every one of the drag's `items` is a file or folder, else none.
    public static func opens(_ fileURLs: [URL], items: Int) -> [URL] {
        guard !fileURLs.isEmpty, fileURLs.count == items, fileURLs.allSatisfy(\.isFileURL) else { return [] }
        return fileURLs
    }
}
