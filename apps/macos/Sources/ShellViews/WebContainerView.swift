import AppKit
import ShellCore
import WebKit

/// A window's content: the web view, the status view that covers it until the page
/// commits, and the slot for the find bar.
///
/// `WKWebView` is not inside an `NSScrollView`, so `NSTextFinder` needs this container
/// to hold its bar (the pattern from the macOS WebView shell guideline).
public final class WebContainerView: NSView, NSTextFinderBarContainer {
    public private(set) var webView: WKWebView
    private let statusView: NSView

    public init(webView: WKWebView, statusView: NSView) {
        self.webView = webView
        self.statusView = statusView
        super.init(frame: .zero)
        addSubview(webView)
        addSubview(statusView)
        webView.isHidden = true
    }

    @available(*, unavailable)
    public required init?(coder: NSCoder) { fatalError("unused") }

    public var showsStatus = true {
        didSet {
            webView.isHidden = showsStatus
            statusView.isHidden = !showsStatus
            needsLayout = true
        }
    }

    /// Swaps in the view of a tab that gave up its page, hidden like the old one would be.
    public func replaceWebView(_ replacement: WKWebView) {
        webView.removeFromSuperview()
        webView = replacement
        addSubview(replacement, positioned: .below, relativeTo: statusView)
        replacement.isHidden = showsStatus
        needsLayout = true
    }

    public var findBarView: NSView? {
        didSet {
            oldValue?.removeFromSuperview()
            needsLayout = true
        }
    }

    // Insert the bar here, not in findBarView's setter: when the bar was already in the
    // view tree, NSTextFinder never set isFindBarVisible (measured on macOS 26.5).
    public var isFindBarVisible = false {
        didSet {
            if isFindBarVisible, let findBarView, findBarView.superview == nil {
                addSubview(findBarView)
            } else if !isFindBarVisible {
                findBarView?.removeFromSuperview()
            }
            needsLayout = true
        }
    }

    public func findBarViewDidChangeHeight() { needsLayout = true }
    public func contentView() -> NSView? { webView }

    public override func layout() {
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

/// Hands files and folders dropped on the page to the app (`FileDrop`), which opens a
/// folder in its own window or tab and a file at its page. Anything else falls through
/// to WebKit's ordinary drag and drop.
public final class DropAwareWebView: WKWebView {
    public var onFileDrop: (([URL]) -> Bool)?

    private func fileURLs(_ info: any NSDraggingInfo) -> [URL] {
        let pasteboard = info.draggingPasteboard
        let urls = pasteboard.readObjects(forClasses: [NSURL.self], options: [.urlReadingFileURLsOnly: true]) as? [URL]
        return FileDrop.opens(urls ?? [], items: pasteboard.pasteboardItems?.count ?? 0)
    }

    public override func draggingUpdated(_ sender: any NSDraggingInfo) -> NSDragOperation {
        let operation = super.draggingUpdated(sender)
        guard onFileDrop != nil, !fileURLs(sender).isEmpty else { return operation }
        return .copy
    }

    public override func performDragOperation(_ sender: any NSDraggingInfo) -> Bool {
        let files = fileURLs(sender)
        if !files.isEmpty, let onFileDrop, onFileDrop(files) { return true }
        return super.performDragOperation(sender)
    }
}
