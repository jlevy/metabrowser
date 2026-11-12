import AppKit
import WebKit

/// A window's content: the web view, the status view that covers it until the page
/// commits, and the slot for the find bar.
///
/// `WKWebView` is not inside an `NSScrollView`, so `NSTextFinder` needs this container
/// to hold its bar (the pattern from the macOS WebView shell guideline).
final class WebContainerView: NSView, NSTextFinderBarContainer {
    private(set) var webView: WKWebView
    private let statusView: NSView

    init(webView: WKWebView, statusView: NSView) {
        self.webView = webView
        self.statusView = statusView
        super.init(frame: .zero)
        addSubview(webView)
        addSubview(statusView)
        webView.isHidden = true
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    var showsStatus = true {
        didSet {
            webView.isHidden = showsStatus
            statusView.isHidden = !showsStatus
            needsLayout = true
        }
    }

    /// Swaps in the view of a tab that gave up its page, hidden like the old one would be.
    func replaceWebView(_ replacement: WKWebView) {
        webView.removeFromSuperview()
        webView = replacement
        addSubview(replacement, positioned: .below, relativeTo: statusView)
        replacement.isHidden = showsStatus
        needsLayout = true
    }

    var findBarView: NSView? {
        didSet {
            oldValue?.removeFromSuperview()
            needsLayout = true
        }
    }

    // Insert the bar here, not in findBarView's setter: when the bar was already in the
    // view tree, NSTextFinder never set isFindBarVisible (measured on macOS 26.5).
    var isFindBarVisible = false {
        didSet {
            if isFindBarVisible, let findBarView, findBarView.superview == nil {
                addSubview(findBarView)
            } else if !isFindBarVisible {
                findBarView?.removeFromSuperview()
            }
            needsLayout = true
        }
    }

    func findBarViewDidChangeHeight() { needsLayout = true }
    func contentView() -> NSView? { webView }

    override func layout() {
        super.layout()
        statusView.frame = bounds
        var webFrame = bounds
        if isFindBarVisible, let bar = findBarView {
            let height = bar.frame.height
            bar.frame = NSRect(x: 0, y: bounds.maxY - height, width: bounds.width, height: height)
            webFrame.size.height -= height
        }
        webView.frame = webFrame
    }
}

/// Hands folders dropped on the page to the app, which opens each in its own window.
/// Anything else falls through to WebKit's ordinary drag and drop.
final class DropAwareWebView: WKWebView {
    var onFolderDrop: (([URL]) -> Bool)?

    private func folderURLs(_ info: any NSDraggingInfo) -> [URL] {
        let urls = info.draggingPasteboard.readObjects(
            forClasses: [NSURL.self], options: [.urlReadingFileURLsOnly: true]) as? [URL] ?? []
        let folders = urls.filter { (try? $0.resourceValues(forKeys: [.isDirectoryKey]).isDirectory) == true }
        return folders.count == urls.count ? folders : []
    }

    override func draggingUpdated(_ sender: any NSDraggingInfo) -> NSDragOperation {
        let operation = super.draggingUpdated(sender)
        if operation.isEmpty, onFolderDrop != nil, !folderURLs(sender).isEmpty { return .copy }
        return operation
    }

    override func performDragOperation(_ sender: any NSDraggingInfo) -> Bool {
        let folders = folderURLs(sender)
        if !folders.isEmpty, let onFolderDrop, onFolderDrop(folders) { return true }
        return super.performDragOperation(sender)
    }
}
