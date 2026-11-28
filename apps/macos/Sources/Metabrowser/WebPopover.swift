import AppKit
import ShellCore

/// A web pane (`WebPane`) in a native popover over a folder's page, anchored to the page's
/// marked link, as View on GitHub opens github.com (mb-4wqh, mb-730z).
///
/// The popover is transient: Escape, Command-W, or a click outside it closes it, and the
/// pane keeps its web view for a while after (`WebPaneState.keptAfterClosing`). Its folder
/// page (`FolderPage`) closes it when the page leaves its window, and lets the pane's web
/// view go at once when the page gives up its own web view or closes.
///
/// The `NSPopover` is made each time the popover opens and let go when it closes, since it
/// holds its content, the pane, for as long as it lives.
final class WebPopover: NSObject, NSPopoverDelegate, WebPaneHost {
    let pane: WebPane
    /// While the popover is open, and from then until it has closed.
    private var popover: NSPopover?
    var onVisibilityChange: (() -> Void)?

    init(isInspectable: Bool) {
        pane = WebPane(isInspectable: isInspectable)
        super.init()
        pane.host = self
    }

    /// Opens the popover at `anchor` in `view`, the page's web view, on `page`, or as it was
    /// left when it was last opened on it. It takes most of the window, at least
    /// `WebPopoverLayout.minimumSize` where the screen allows, and opens below the link.
    func show(_ page: WebSite.Page, at anchor: NSRect, of view: NSView) {
        pane.open(page)
        let size = WebPopoverLayout.contentSize(
            window: view.window?.contentLayoutRect.size ?? view.bounds.size,
            screen: view.window?.screen?.visibleFrame.size)
        pane.preferredContentSize = size
        let popover = popover ?? makePopover()
        popover.contentSize = size
        popover.show(relativeTo: anchor, of: view, preferredEdge: view.isFlipped ? .maxY : .minY)
        pane.focus()
        onVisibilityChange?()
    }

    var isShown: Bool { popover?.isShown == true }

    func close() { popover?.close() }

    /// After Metabrowser > Clear Website Data… (`WebPane.reload(after:)`).
    func reload(after clearing: WebDataClearing) { pane.reload(after: clearing) }

    /// Lets the pane's web view go at once: the page gave up its web view, or it closes.
    func discard() {
        popover?.close()
        letPopoverGo()
        pane.discard()
    }

    private func makePopover() -> NSPopover {
        let popover = NSPopover()
        popover.contentViewController = pane
        popover.behavior = .transient
        popover.delegate = self
        self.popover = popover
        return popover
    }

    /// Lets the popover go, and with it its hold on the pane, so a window that closes frees
    /// both.
    private func letPopoverGo() {
        popover?.delegate = nil
        popover?.contentViewController = nil
        popover = nil
    }

    // MARK: - NSPopoverDelegate

    func popoverWillShow(_ notification: Notification) { pane.hostWillShow() }

    func popoverDidClose(_ notification: Notification) {
        guard let closed = notification.object as? NSPopover, closed === popover, !closed.isShown else { return }
        letPopoverGo()
        pane.hostDidHide()
        onVisibilityChange?()
    }

    // MARK: - WebPaneHost

    func closePane(_ sender: Any?) { popover?.performClose(sender) }

    func holdPaneOpen(_ held: Bool) { popover?.behavior = held ? .applicationDefined : .transient }
}
