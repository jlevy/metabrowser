import AppKit
import ShellCore
import WebKit

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
    private var navigationBar: NavigationTitleBar { titleAccessory.navigation }
    private var keyMonitor: Any?
    private var hintTask: Task<Void, Never>?
    private var showingPageHints = false
    private var historyMenu: NSMenu?
    private(set) var isShowingSheet = false
    private var lastNavigationState: FolderNavigationState?
    private var lastHistoryItem: WKBackForwardListItem?
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
        wireNavigation()
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
        pageNavigationChanged()
    }

    /// Shows `newPage` in place of the page the window shows now, which is left with no
    /// window: the caller decides whether it stays open in the background or closes
    /// (`FolderWindows.switchWindow`). The window itself stays: its frame, Space, and full
    /// screen.
    func show(_ newPage: FolderPage) {
        guard newPage !== page else { return }
        historyMenu?.cancelTracking()
        navigationBar.resetTransientUI()
        clearNavigationHints()
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
        pageNavigationChanged()
    }

    func windowDidResignKey(_ notification: Notification) {
        clearNavigationHints()
        pageNavigationChanged()
    }

    func windowWillBeginSheet(_ notification: Notification) {
        isShowingSheet = true
        pageNavigationChanged()
    }

    func windowDidEndSheet(_ notification: Notification) {
        isShowingSheet = false
        pageNavigationChanged()
    }

    func windowDidResize(_ notification: Notification) {
        navigationBar.refit()
    }

    func windowWillClose(_ notification: Notification) {
        // A task waiting on this window may keep it alive past its closing.
        if let window { Self.lastPlaced.close(window) }
        if let keyMonitor { NSEvent.removeMonitor(keyMonitor) }
        clearNavigationHints()
        historyMenu?.cancelTracking()
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

extension BrowserWindowController {
    private func wireNavigation() {
        let bar = navigationBar
        bar.validatedURL = { [weak self] in self?.page.navigationState.url }
        for arrow in [bar.back, bar.forward] {
            arrow.target = self
            arrow.action = #selector(advance(_:))
            arrow.openHistory = { [weak self, weak arrow] in
                guard let self, let arrow else { return }
                showHistory(arrow.direction)
            }
        }
        bar.copy.target = self
        bar.copy.action = #selector(copyAddress(_:))
        keyMonitor = NSEvent.addLocalMonitorForEvents(
            matching: [.keyDown, .flagsChanged, .leftMouseDown, .rightMouseDown, .otherMouseDown, .scrollWheel]
        ) { [weak self] event in
            let handled = MainActor.assumeIsolated { self?.handleNavigationKey(event) ?? false }
            return handled ? nil : event
        }
    }

    func pageNavigationChanged() {
        let state = page.navigationState
        let item = page.webView.backForwardList.currentItem
        let interactive = page.historyAvailable
        if !interactive || state != lastNavigationState || lastHistoryItem !== item {
            historyMenu?.cancelTracking()
        }
        if !interactive { clearNavigationHints() }
        lastNavigationState = state
        lastHistoryItem = item
        navigationBar.update(state, interactive: interactive)
    }

    @objc private func advance(_ sender: NavigationArrow) {
        clearNavigationHints()
        page.moveInHistory(sender.direction)
    }

    @objc private func copyAddress(_ sender: NSButton) { copyCurrentURL() }

    func copyCurrentURL() {
        guard page.historyAvailable, let url = page.navigationState.url else { return }
        let board = NSPasteboard.general
        board.clearContents()
        if board.setString(url.absoluteString, forType: .string) { navigationBar.showCopied() }
    }

    private func handleNavigationKey(_ event: NSEvent) -> Bool {
        guard let window, window.isKeyWindow, event.window == nil || event.window === window else { return false }
        guard page.historyAvailable, historyMenu == nil else {
            clearNavigationHints()
            return false
        }
        if page.webContentHasFocus {
            if hintTask != nil { clearNavigationHints() }
            // AppKit has not yet moved focus for these events. Check where it landed
            // without clearing a reveal that the page still owns.
            if event.type == .leftMouseDown || (event.type == .keyDown && event.keyCode == 48) {
                DispatchQueue.main.async { [weak self] in
                    guard let self, showingPageHints, !page.webContentHasFocus else { return }
                    clearNavigationHints()
                }
            }
            return false
        }
        if showingPageHints { clearNavigationHints() }
        guard navigationBar.ownsFocus else {
            clearNavigationHints()
            return false
        }
        let modifiers: NSEvent.ModifierFlags = [.shift, .command, .option, .control, .function]
        let held = event.modifierFlags.intersection(modifiers)
        if event.type == .flagsChanged, [56, 60].contains(event.keyCode), held == .shift {
            clearNavigationHints()
            hintTask = Task { [weak self] in
                try? await Task.sleep(for: .milliseconds(200))
                guard !Task.isCancelled, let self, page.historyAvailable, navigationBar.ownsFocus else { return }
                navigationBar.showHints(true)
            }
            return false
        }
        clearNavigationHints()
        guard event.type == .keyDown, held.isEmpty, !event.isARepeat else { return false }
        let direction: HistoryDirection
        switch event.characters {
        case "[": direction = .back
        case "]": direction = .forward
        default: return false
        }
        guard navigationBar.arrow(direction).isEnabled else { return false }
        page.moveInHistory(direction)
        return true
    }

    func showPageNavigationHints(_ visible: Bool) {
        hintTask?.cancel()
        hintTask = nil
        showingPageHints = visible
        navigationBar.showHints(visible)
    }

    private func clearNavigationHints() { showPageNavigationHints(false) }

    func showHistory(_ direction: HistoryDirection, fromKeyboard: Bool = false) {
        guard historyMenu == nil, page.historyAvailable, let url = page.navigationState.url,
              let current = page.webView.backForwardList.currentItem
        else { return }
        let items = page.historyItems(direction)
        guard !items.isEmpty else { return }
        clearNavigationHints()
        let arrow = navigationBar.arrow(direction)
        let menu = NSMenu(title: direction == .back ? "Back History" : "Forward History")
        menu.autoenablesItems = false
        let entries = items.map { item in
            let label = page.historyLabel(for: item)
            let fallback = Self.historyFallback(item)
            return (item: item, title: label?.title ?? fallback.title,
                    icon: label?.icon ?? fallback.icon, context: label?.context)
        }
        let byTitle = Dictionary(grouping: entries) { $0.title }
        for (index, entry) in entries.enumerated() {
            var title = entry.title
            if let group = byTitle[entry.title], group.count > 1 {
                if let context = entry.context { title += " · \(context)" }
                if group.filter({ $0.context == entry.context }).count > 1 {
                    let side = direction == .back ? "back" : "ahead"
                    title += " · \(index + 1) \(side)"
                }
            }
            let visibleTitle = title.count > 120 ? String(title.prefix(119)) + "…" : title
            let menuItem = NSMenuItem(title: visibleTitle, action: #selector(selectHistory(_:)), keyEquivalent: "")
            menuItem.target = self
            menuItem.image = Self.historyIcon(entry.icon)
            menuItem.toolTip = title + "\n" + entry.item.url.absoluteString
            menuItem.setAccessibilityLabel(title)
            menuItem.representedObject = HistorySelection(
                page: page, view: page.webView, current: current, url: url, item: entry.item, direction: direction)
            menu.addItem(menuItem)
        }
        let originalPage = page
        historyMenu = menu
        defer { historyMenu = nil }
        let selected = menu.popUp(
            positioning: nil, at: NSPoint(x: arrow.bounds.minX, y: arrow.bounds.minY), in: arrow)
        if fromKeyboard, !selected, originalPage === page, window?.isKeyWindow == true {
            window?.makeFirstResponder(arrow)
        }
    }

    @objc private func selectHistory(_ sender: NSMenuItem) {
        guard let selection = sender.representedObject as? HistorySelection, selection.page === page,
              let view = selection.view, page.navigationState.url?.absoluteString == selection.url.absoluteString
        else { return }
        page.traverseHistory(to: selection.item, direction: selection.direction, from: selection.current, in: view)
    }

    private static func historyFallback(_ item: WKBackForwardListItem) -> (title: String, icon: String?) {
        let parts = item.url.pathComponents.dropFirst()
        if let kind = parts.first, let value = parts.dropFirst().first, !value.isEmpty {
            switch kind {
            case "pull": return ("PR #\(value)", "gitPullRequest")
            case "stack": return ("Stack #\(value)", "layers")
            case "commit": return (String(value.prefix(7)), "gitCommit")
            case "view": return (item.url.lastPathComponent, "file")
            default: break
            }
        }
        let last = item.url.lastPathComponent
        let title = item.title.flatMap { $0.isEmpty ? nil : $0 }
        return (title ?? (last.isEmpty || last == "/" ? "Project" : last), "list")
    }

    private static func historyIcon(_ name: String?) -> NSImage? {
        let icon: NSImage? = switch name {
        case "folder": RootMark.folder.image
        case "folderDot": RootMark.plainFolder.image
        case "git", "folderGit2": RootMark.gitCheckout.image
        case "mirror", "folderCloud": RootMark.mirror.image
        case "gitPullRequest", "pull":
            NSImage(systemSymbolName: "arrow.triangle.branch", accessibilityDescription: nil)
        case "gitPullRequestDraft":
            NSImage(systemSymbolName: "pencil.circle", accessibilityDescription: nil)
        case "gitPullRequestClosed":
            NSImage(systemSymbolName: "xmark.circle", accessibilityDescription: nil)
        case "gitMerge":
            NSImage(systemSymbolName: "arrow.triangle.merge", accessibilityDescription: nil)
        case "layers", "stack":
            NSImage(systemSymbolName: "square.3.layers.3d", accessibilityDescription: nil)
        case "gitCommit", "commit":
            NSImage(systemSymbolName: "circle.circle", accessibilityDescription: nil)
        case "list":
            NSImage(systemSymbolName: "list.bullet", accessibilityDescription: nil)
        case "activity":
            NSImage(systemSymbolName: "waveform.path", accessibilityDescription: nil)
        case "alignLeft":
            NSImage(systemSymbolName: "text.alignleft", accessibilityDescription: nil)
        case "copy":
            NSImage(systemSymbolName: "document.on.document", accessibilityDescription: nil)
        case "doc", "fileText":
            NSImage(systemSymbolName: "doc.text", accessibilityDescription: nil)
        case "grid":
            NSImage(systemSymbolName: "square.grid.2x2", accessibilityDescription: nil)
        case "monitor":
            NSImage(systemSymbolName: "display", accessibilityDescription: nil)
        case "fileCode":
            NSImage(systemSymbolName: "document.badge.ellipsis", accessibilityDescription: nil)
        default: nil
        }
        return icon
            ?? NSImage(systemSymbolName: "document", accessibilityDescription: nil)
    }
}

private struct HistorySelection {
    weak var page: FolderPage?
    weak var view: WKWebView?
    let current: WKBackForwardListItem
    let url: URL
    let item: WKBackForwardListItem
    let direction: HistoryDirection
}
