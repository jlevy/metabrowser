import AppKit
import ShellCore

/// One folder window: the window and its chrome (the title, the mark, and placement),
/// showing one folder's page at a time (`FolderPage`). The page belongs to its
/// folder's session; the window only hosts it, so it can show another page in its place
/// without becoming another window.
final class BrowserWindowController: NSWindowController, NSWindowDelegate, NSMenuItemValidation {
    /// The page the window shows.
    private(set) var page: FolderPage
    /// Holds the page's view, filling the window. The page is not the window's content view
    /// controller, since setting one resizes the window to fit its view.
    private let pageHost = NSView()
    private let titleAccessory = TitleAccessoryController()
    private let markAccessory = TitleBarMarkController()
    /// Every open folder window's controller, which nothing else holds: a page refers to
    /// its window weakly, and AppKit holds the window, not its controller. Each stays here
    /// from its creation until its window closes.
    private static var open: [ObjectIdentifier: BrowserWindowController] = [:]
    /// The window placed last, which the next one steps down and right from, while it
    /// is open (`NewWindowFrame`, `LastPlacedWindow`).
    private static var lastPlaced = LastPlacedWindow<NSWindow>()
    /// Narrow enough to tile two windows side by side on a laptop screen, and wide
    /// enough for the status view.
    private static let minimumSize = NSSize(width: 480, height: 320)

    init(page: FolderPage) {
        self.page = page
        let window = NSWindow(
            contentRect: NSRect(origin: .zero, size: Self.minimumSize),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered, defer: false)
        window.contentView = pageHost
        window.minSize = Self.minimumSize
        window.titleVisibility = .hidden  // TitleAccessoryController draws the title
        window.addTitlebarAccessoryViewController(titleAccessory)
        window.addTitlebarAccessoryViewController(markAccessory)
        // A window of its own, always: Merge All Windows, the tab bar, and System Settings'
        // "Prefer tabs when opening documents" leave it alone (`refuseTabs`).
        window.tabbingMode = .disallowed
        window.isReleasedWhenClosed = false
        Self.place(window)
        super.init(window: window)
        window.delegate = self
        Self.open[ObjectIdentifier(self)] = self
        titleAccessory.chooser = { [weak self] in
            guard let self else { return nil }
            return (NSApp.delegate as? AppDelegate)?.folderChooserMenu(for: self)
        }
        host(page)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    /// Turns off AppKit's automatic window tabbing for the whole app, which the app does
    /// before it builds its menus: AppKit then adds no Show Tab Bar, Show All Tabs, Merge
    /// All Windows, or Move Tab to New Window, and puts no new window in another's tabs
    /// when System Settings prefers tabs. Every folder opens in a window of its own, and
    /// each folder window disallows tabbing itself too (`init`).
    static func refuseTabs() {
        NSWindow.allowsAutomaticWindowTabbing = false
    }

    /// Sizes a new window for the screen it opens on, the one with the key window (or
    /// else the menu bar), and places it a step down and right from the window placed
    /// before it, all of it on that screen (`NewWindowFrame`). A restored window then
    /// takes its saved frame.
    private static func place(_ window: NSWindow) {
        guard let screen = NSScreen.main ?? NSScreen.screens.first else { return }
        let visible = screen.visibleFrame
        let size = NewWindowFrame.size(visible: visible, minimum: minimumSize)
        let frame = NewWindowFrame.next(size: size, visible: visible, after: lastPlaced.window?.frame)
        window.setFrame(frame, display: false)
        lastPlaced.place(window)
    }

    /// Puts `page`'s view in the window, filling it, and names the window for its folder.
    private func host(_ page: FolderPage) {
        page.host = self
        let view = page.view
        view.frame = pageHost.bounds
        view.autoresizingMask = [.width, .height]
        pageHost.addSubview(view)
        if let session = page.session { showTitle(session.title, windowTitle: session.windowTitle) }
    }

    /// Shows `newPage` in place of the page the window shows now, which is left with no
    /// window: the caller decides whether it stays open in the background or closes
    /// (`FolderWindows.switchWindow`). The window itself stays: its frame, Space, and full
    /// screen.
    func show(_ newPage: FolderPage) {
        guard newPage !== page else { return }
        let old = page
        old.view.removeFromSuperview()
        old.host = nil
        page = newPage
        host(newPage)
        window?.makeFirstResponder(newPage.webView)
    }

    /// Names the window for everything that reads its title, and draws the visible one.
    /// `windowTitle` is `window.title`: the folder's short name, or its full name while
    /// another open folder shares the short name (`WindowTitle.windowTitles`). The page's
    /// own `<title>` is not used: it names the page in a browser's tab.
    func showTitle(_ title: WindowTitle, windowTitle: String) {
        guard let window else { return }
        let session = page.session
        window.title = windowTitle
        window.subtitle = title.subtitle
        // Only a folder on this Mac has a path menu: a repository's root is a URL, whose path
        // names no folder here, whatever identity its port answered.
        window.representedURL = title.hasPathMenu && session?.isLocal == true ? session?.root : nil
        titleAccessory.show(title, representing: window.representedURL)
        let named = "window title \(window.title), subtitle \(window.subtitle)"
        AppLog.app.debug("\(named, privacy: .public)")
    }

    // MARK: - Window events

    /// A window brought forward becomes key.
    func windowDidBecomeKey(_ notification: Notification) {
        page.shown()
    }

    func windowWillClose(_ notification: Notification) {
        // A task waiting on this window may keep it alive past its closing.
        if let window { Self.lastPlaced.close(window) }
        page.host = nil
        page.close()
        Self.open[ObjectIdentifier(self)] = nil
    }

    // MARK: - Menu actions

    /// File > Close Folder: closes the folder this window shows, in every window, and
    /// shows another open folder in its place (`FolderWindows.closeFolder`).
    @objc func closeFolder(_ sender: Any?) {
        guard let session = page.session else { return }
        (NSApp.delegate as? AppDelegate)?.closeFolder(session)
    }

    /// View > Switch Folder…: the panel that switches this window's folder by name.
    @objc func switchFolder(_ sender: Any?) {
        (NSApp.delegate as? AppDelegate)?.showSwitchFolder(over: self)
    }

    /// The page's menu actions (Back, Reload, Find, Print, Zoom, and the rest) are the
    /// page's. Nil-targeted items reach the page along the responder chain while the focus
    /// is in it, since the page follows its view there. While the window itself is first
    /// responder, as before the page first loads, the chain is the window and this
    /// controller, which hands them to the page here.
    override func supplementalTarget(forAction action: Selector, sender: Any?) -> Any? {
        page.responds(to: action) ? page : super.supplementalTarget(forAction: action, sender: sender)
    }

    /// The window's own items. Close Folder and Switch Folder… are off while a page's sheet
    /// (an alert, a confirm, the print panel) is open on the window, which keeps its page
    /// until the sheet ends (`FolderSwitch.refused`); the page validates its own items.
    func validateMenuItem(_ item: NSMenuItem) -> Bool {
        switch item.action {
        case #selector(closeFolder(_:)), #selector(switchFolder(_:)): window?.attachedSheet == nil
        default: true
        }
    }
}
