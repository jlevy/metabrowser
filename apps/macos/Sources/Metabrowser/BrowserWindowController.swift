import AppKit
import ShellCore
import ShellViews
import SwiftUI
import WebKit

/// One window onto a folder's server. The page talks to the server directly; this
/// class only decides which navigations stay in the window and supplies what a
/// browser would (new windows, downloads, dialogs, find, zoom, printing).
final class BrowserWindowController: NSWindowController, NSWindowDelegate, NSMenuItemValidation {
    static let zoomKey = "pageZoom"
    static let inspectorKey = "WebInspectorEnabled"
    /// Shared by every folder window, so macOS merges folders into one window's tabs.
    static let tabbingIdentifier = "io.github.jlevy.metabrowser.folder"

    /// Replaced by a fresh view, which has no web process until it loads, when the tab
    /// gives up its page (`discardPage`).
    private(set) var webView: DropAwareWebView
    private weak var session: FolderSession?
    private var policy = NavigationPolicy()
    private let container: WebContainerView
    private let status = WindowStatus()
    private let textFinder = NSTextFinder()
    private let titleAccessory = TitleAccessoryController()
    private let markAccessory = TitleBarMarkController()
    /// The navigation `load` submitted, whose commit reveals the page in place of the
    /// status view, until server state supersedes it (`PageReveal`).
    private var reveal = PageReveal<WKNavigation>()
    /// The page to load next: one asked for (a file opened here, a restored tab's page),
    /// else the one shown before the server restarted or the tab gave up its page; and
    /// the loads waiting to load it, of which only the newest may (`PageLoads`).
    private var pages: PageLoads
    /// The folder's server while it is ready.
    private var endpoint: ServerEndpoint?
    /// Whether the tab gave up its page's web view (`TabDiscardPolicy`). It loads the page
    /// again when it is shown.
    private(set) var isDiscarded = false
    /// Reloads after the web content process dies, then the status view.
    private var contentRecoveries = RecoveryBudget.webContent
    /// Which view the window shows, and what its GitHub view was opened for
    /// (`GitHubViewState`).
    private var gitHub = GitHubViewState()
    /// The GitHub view, from the toggle's first use until the tab gives up its pages.
    private var gitHubPane: GitHubPane?
    /// The GitHub view's address, which the bar above it shows, as it changes, including
    /// github.com's own in-page navigations, which commit no new page.
    private var gitHubLocation: NSKeyValueObservation?
    /// Reloads after the GitHub view's web content process dies.
    private var gitHubRecoveries = RecoveryBudget.webContent
    /// The sheets the page opened, which Command-R cancels before it reloads.
    private var pageSheets = PageSheets<NSWindow>()
    /// The print panel, while a print the window started runs.
    private var printSheet: NSWindow?
    /// The window placed last, which the next one steps down and right from, while it
    /// is open (`NewWindowFrame`, `LastPlacedWindow`).
    private static var lastPlaced = LastPlacedWindow<NSWindow>()
    /// Narrow enough to tile two windows side by side on a laptop screen, and wide
    /// enough for the status view.
    private static let minimumSize = NSSize(width: 480, height: 320)

    /// Pass `configuration` only from `createWebViewWith`, which requires the web view
    /// it returns to be built from the configuration WebKit hands it. `page` is the page to
    /// load once the server is ready, and a `discarded` window loads it only when shown.
    init(
        session: FolderSession, configuration: WKWebViewConfiguration? = nil, page: PageAddress? = nil,
        discarded: Bool = false
    ) {
        self.session = session
        webView = Self.makeWebView(configuration ?? Self.pageConfiguration())
        pages = PageLoads(requested: page)
        isDiscarded = discarded

        let statusView = NSHostingView(rootView: StatusView(
            folderName: session.folderName, folderPath: session.location, status: status,
            retry: { [weak session] in session?.retry() },
            revealLogs: { [weak session] in session?.revealLog() },
            showSettings: { (NSApp.delegate as? AppDelegate)?.showSettings(nil) }))
        container = WebContainerView(webView: webView, statusView: statusView)

        let window = NSWindow(
            contentRect: NSRect(origin: .zero, size: Self.minimumSize),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered, defer: false)
        window.contentView = container
        window.minSize = Self.minimumSize
        window.titleVisibility = .hidden  // TitleAccessoryController draws the title
        window.addTitlebarAccessoryViewController(titleAccessory)
        window.addTitlebarAccessoryViewController(markAccessory)
        window.tabbingIdentifier = Self.tabbingIdentifier
        window.isReleasedWhenClosed = false
        Self.place(window)
        super.init(window: window)
        window.delegate = self

        wire(webView)
        textFinder.client = webView  // WKWebView adopts NSTextFinderClient
        textFinder.findBarContainer = container
        textFinder.isIncrementalSearchingEnabled = true
        showTitle(session.title, windowTitle: session.windowTitle)
        // A window WebKit creates for `target=_blank` shows its page at once.
        container.showsStatus = configuration == nil
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    /// Sizes a new window for the screen it opens on, the one with the key window (or
    /// else the menu bar), and places it a step down and right from the window placed
    /// before it, all of it on that screen (`NewWindowFrame`). A restored window then
    /// takes its saved frame, and a new tab the frame of the window it joins.
    private static func place(_ window: NSWindow) {
        guard let screen = NSScreen.main ?? NSScreen.screens.first else { return }
        let visible = screen.visibleFrame
        let size = NewWindowFrame.size(visible: visible, minimum: minimumSize)
        let frame = NewWindowFrame.next(size: size, visible: visible, after: lastPlaced.window?.frame)
        window.setFrame(frame, display: false)
        lastPlaced.place(window)
    }

    /// Safari's Develop menu can inspect the page in debug builds, or in any build after
    /// `defaults write <bundle identifier> WebInspectorEnabled -bool true`.
    private static var isInspectable: Bool {
        #if DEBUG
            true
        #else
            UserDefaults.standard.bool(forKey: inspectorKey)
        #endif
    }

    private static func makeWebView(_ configuration: WKWebViewConfiguration) -> DropAwareWebView {
        let webView = DropAwareWebView(frame: .zero, configuration: configuration)
        webView.isInspectable = isInspectable
        webView.allowsBackForwardNavigationGestures = true
        webView.allowsMagnification = true
        webView.pageZoom = PageZoom.restored(UserDefaults.standard.double(forKey: zoomKey))
        return webView
    }

    /// A page's configuration: the folder's own, with the page's Print button and the view
    /// header's GitHub toggle answered by the window that shows it.
    private static func pageConfiguration() -> WKWebViewConfiguration {
        WebConfiguration.make(pagePrints: pagePrints, gitHubViews: gitHubViews)
    }

    private func wire(_ webView: DropAwareWebView) {
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.onFileDrop = { urls in
            guard let app = NSApp.delegate as? AppDelegate else { return false }
            urls.forEach(app.request)
            return true
        }
    }

    private func unwire(_ webView: DropAwareWebView) {
        webView.stopLoading()
        webView.navigationDelegate = nil
        webView.uiDelegate = nil
        webView.onFileDrop = nil
    }

    // MARK: - The GitHub view

    /// Every window's view header toggles (`GitHubViewRequests`): each shows the GitHub
    /// view in the window whose page asked.
    static let gitHubViews = GitHubViewRequests { webView, frame, href in
        (webView.window?.windowController as? BrowserWindowController)?.toggleAskedForGitHub(href, from: frame)
    }

    private func toggleAskedForGitHub(_ href: String, from frame: WKFrameInfo) {
        guard GitHubViewRequests.allows(frame, under: policy), let page = GitHubView.togglePage(href) else {
            AppLog.app.info("a GitHub toggle was not answered: not this server's own page, or not a page on github.com")
            return
        }
        showGitHub(page)
    }

    /// Shows the GitHub view in the page's place, at `page`, or as it was left when it was
    /// opened for `page` before (`GitHubViewState`).
    private func showGitHub(_ page: URL) {
        let pane = gitHubPane ?? makeGitHubPane()
        if let load = gitHub.showGitHub(for: page) {
            pane.webView.load(URLRequest(url: load))
        }
        container.showsPane = true
        textFinder.client = pane.webView
        window?.makeFirstResponder(pane.webView)
    }

    /// Shows the window's page again, as it was left; the GitHub view stays beside it.
    private func showMetabrowser() {
        guard gitHub.showsGitHub else { return }
        gitHub.showMetabrowser()
        container.showsPane = false
        textFinder.client = webView
        if !container.showsStatus { window?.makeFirstResponder(webView) }
    }

    private func makeGitHubPane() -> GitHubPane {
        let view = Self.makeWebView(WebConfiguration.makeGitHub())
        wire(view)
        let pane = GitHubPane(webView: view) { [weak self] in self?.showMetabrowser() }
        gitHubLocation = view.observe(\.url) { [weak self] _, _ in
            MainActor.assumeIsolated { self?.gitHubPane?.showLocation() }
        }
        container.setPane(pane, searching: view)
        gitHubPane = pane
        return pane
    }

    /// Lets the GitHub view go, with its web content process: the tab gave up its pages, or
    /// the window closes. The window shows its page.
    private func dropGitHubView() {
        let shown = gitHub.showsGitHub
        gitHub.discard()
        guard let pane = gitHubPane else { return }
        gitHubLocation = nil
        unwire(pane.webView)
        container.setPane(nil, searching: nil)
        gitHubPane = nil
        if shown { textFinder.client = webView }
    }

    /// After Metabrowser > Clear GitHub Data…: the GitHub view loads its page again, signed out.
    func reloadGitHubView() {
        gitHubPane?.webView.reload()
    }

    private var shownWebView: WKWebView {
        if gitHub.showsGitHub, let pane = gitHubPane { return pane.webView }
        return webView
    }

    private func isGitHubView(_ view: WKWebView) -> Bool {
        gitHubPane.map { $0.webView === view } ?? false
    }

    /// View > Show GitHub View, Option-Command-G, or Show Metabrowser View while the GitHub
    /// view shows. From the page, it asks the page for its toggle's link, in the app's own
    /// content world, and shows nothing, with a beep, on a page with no toggle or one of
    /// an opaque origin, such as a `/raw` file.
    @objc func toggleGitHubView(_ sender: Any?) {
        if gitHub.showsGitHub { return showMetabrowser() }
        guard currentServerURL != nil else { return NSSound.beep() }
        let query = "window.origin === \"null\" ? \"\" : \(GitHubViewRequests.query)"
        webView.evaluateJavaScript(query, in: nil, in: GitHubViewRequests.world) { [weak self] result in
            guard let self, !gitHub.showsGitHub else { return }
            guard case .success(let value) = result, let href = value as? String, let page = GitHubView.togglePage(href)
            else { return NSSound.beep() }
            showGitHub(page)
        }
    }

    // MARK: - Server state

    func showStarting() {
        pages.cancelAll()
        rememberPage()
        supersedeLoad()
        endpoint = nil
        status.phase = .starting
        container.showsStatus = true
    }

    func showFailure(_ failure: ServerFailure) {
        pages.cancelAll()
        rememberPage()
        supersedeLoad()
        endpoint = nil
        status.phase = .failed(failure)
        container.showsStatus = true
    }

    /// A restored folder in a protected location, whose server starts when this tab is
    /// selected.
    func showWaitingForSelection() {
        supersedeLoad()
        status.phase = .waitingForSelection
        container.showsStatus = true
    }

    /// A folder whose start waits for a metab the app accepts: none was found, or the one
    /// found changed and is being checked again.
    func showWaitingForRuntime() {
        rememberPage()
        supersedeLoad()
        endpoint = nil
        status.phase = .waitingForRuntime
        container.showsStatus = true
    }

    /// Server state now covers the page. A load still on its way is remembered as the
    /// page to show next and stopped, and none of its callbacks, even one WebKit has
    /// already sent, can change the status (`PageReveal`).
    private func supersedeLoad() {
        guard reveal.supersede() else { return }
        rememberPage()
        webView.stopLoading()
    }

    /// Loads the page this window is to show, on the new origin, or the server's entry
    /// page. A discarded tab only remembers the server until it is shown.
    func attach(_ endpoint: ServerEndpoint, authorization: WebAuthorization) {
        let ticket = pages.begin()  // which supersedes every load still waiting
        policy.origin = endpoint.origin
        self.endpoint = endpoint
        if isDiscarded { status.phase = .reloading }
        Task {
            await install(authorization, for: endpoint)
            guard self.endpoint == endpoint, !isDiscarded else { return }
            load(pages.take(for: ticket), from: endpoint)
        }
    }

    /// For a window opened from a link: the page is loaded by WebKit or by `load`.
    func adoptServer(_ endpoint: ServerEndpoint?) {
        policy.origin = endpoint?.origin
        self.endpoint = endpoint
    }

    /// Shows `page` now if the server is ready and still answers, or once it is ready, in
    /// the Metabrowser view: a file or a link sent to the app opens there.
    func show(_ page: PageAddress) {
        showMetabrowser()
        pages.request(page)
        isDiscarded = false
        if let endpoint { loadNextPageOnceAnswered(from: endpoint) }
    }

    /// Loads the entry page of the server it attaches to next, rather than the page it shows
    /// now: a repository's server starting again on a new link announces that link's page.
    /// A load already waiting, such as a discarded tab's revived as the link brought it
    /// forward, is superseded, since the old server can go on serving while the restart
    /// waits at the launch gate (`ServerSupervisor.restart`).
    func showEntryPage() {
        showMetabrowser()
        pages.cancelAll()
        pages.requestEntry()
        isDiscarded = false
    }

    /// Whether the start waits for another repository's, which can be a first clone.
    func showWaitingAtGate(_ waiting: Bool) {
        status.waitsForAnotherStart = waiting
    }

    /// The page to save for the next launch.
    var currentPage: PageAddress? {
        pages.saved(showing: currentServerURL.flatMap(PageAddress.init))
    }

    /// Gives up the page's web view, which ends its WebContent process, and keeps the
    /// page to load again from the folder's server when the tab is shown.
    func discardPage() {
        guard !isDiscarded else { return }
        pages.cancelAll()
        rememberPage()
        isDiscarded = true
        reveal.supersede()  // the discarded view is stopped below
        dropGitHubView()
        unwire(webView)
        webView = Self.makeWebView(Self.pageConfiguration())
        wire(webView)
        textFinder.client = webView
        container.replaceWebView(webView)
        if endpoint != nil { status.phase = .reloading }
        container.showsStatus = true
    }

    /// Loads the page again after `discardPage`: now if the server is ready and still
    /// answers, or when it is ready.
    private func revivePage() {
        guard isDiscarded else { return }
        isDiscarded = false
        if let endpoint { loadNextPageOnceAnswered(from: endpoint) }
    }

    /// Loads from a server that was ready before this window asked, once it proves it
    /// still answers: a live pid is not a working server. One that does not answer fails,
    /// and every window of the folder says so. Only the newest waiting load loads
    /// (`PageLoads`), so overlapping requests end on the newest page.
    private func loadNextPageOnceAnswered(from endpoint: ServerEndpoint) {
        let ticket = pages.begin()
        Task {
            guard let session, case .healthy = await session.checkHealth(), self.endpoint == endpoint,
                  !isDiscarded
            else { return }
            load(pages.take(for: ticket), from: endpoint)
        }
    }

    /// Loads the page a ticket's turn gives, or nothing for a superseded ticket.
    private func load(_ turn: PageLoads.Load, from endpoint: ServerEndpoint) {
        guard case .page(let page) = turn else { return }
        load(page.flatMap { $0.url(on: endpoint.origin) } ?? endpoint.entryURL)
    }

    func load(_ url: URL) {
        reveal.submitted(webView.load(URLRequest(url: url)))
    }

    private func install(_ authorization: WebAuthorization, for endpoint: ServerEndpoint) async {
        guard case .cookie(let name, let value) = authorization,
              let host = endpoint.origin.host(percentEncoded: false),
              let cookie = HTTPCookie(properties: [
                  .domain: host, .path: "/", .name: name, .value: value,
                  HTTPCookiePropertyKey("HttpOnly"): "TRUE",
                  .sameSitePolicy: HTTPCookieStringPolicy.sameSiteStrict,
              ])
        else { return }
        await webView.configuration.websiteDataStore.httpCookieStore.setCookie(cookie)
    }

    private var currentServerURL: URL? {
        guard let url = webView.url, policy.isAppOrigin(url) else { return nil }
        return url
    }

    private func rememberPage() {
        if let page = currentServerURL.flatMap(PageAddress.init) { pages.remember(shown: page) }
    }

    /// Names the window for everything that reads its title, and draws the visible one.
    /// `windowTitle` is `window.title`: the folder's short name, or its full name while
    /// another open folder shares the short name (`WindowTitle.windowTitles`). The page's
    /// own `<title>` is not used: it names the page in a browser's tab.
    func showTitle(_ title: WindowTitle, windowTitle: String) {
        guard let window else { return }
        window.title = windowTitle
        window.subtitle = title.subtitle
        // Only a folder on this Mac has a path menu: a repository's root is a URL, whose path
        // names no folder here, whatever identity its port answered.
        window.representedURL = title.hasPathMenu && session?.isLocal == true ? session?.root : nil
        window.tab.title = title.tabTitle
        window.tab.toolTip = title.tabToolTip
        titleAccessory.show(title, representing: window.representedURL)
        let named = "window title \(window.title), tab \(window.tab.title ?? ""), subtitle \(window.subtitle)"
        AppLog.app.debug("\(named, privacy: .public)")
    }

    /// Selecting a tab makes its window key.
    func windowDidBecomeKey(_ notification: Notification) {
        revivePage()
        session?.windowShown(self)
    }

    func windowWillClose(_ notification: Notification) {
        // A task waiting on this window may keep it alive past its closing.
        if let window { Self.lastPlaced.close(window) }
        pages.cancelAll()
        dropGitHubView()
        textFinder.client = nil
        textFinder.findBarContainer = nil
        webView.stopLoading()
        webView.navigationDelegate = nil
        webView.uiDelegate = nil
        session?.windowClosed(self)
    }

    // MARK: - Menu actions (nil-targeted items reach the key window's controller)

    // Back, Forward, Reload, zoom, Print, and Find act on the view the window shows: its
    // page, or its GitHub view.
    @objc func navigateBack(_ sender: Any?) { shownWebView.goBack() }
    @objc func navigateForward(_ sender: Any?) { shownWebView.goForward() }

    /// Command-R, in every state the window can be in (`PageReload`).
    @objc func reloadPage(_ sender: Any?) {
        cancelPageSheets()
        switch PageReload.route(in: windowState) {
        case .reloadPage: shownWebView.reload()
        case .loadPage:
            if gitHub.showsGitHub, let page = gitHub.openedFor {
                gitHubPane?.webView.load(URLRequest(url: page))
            } else if let endpoint {
                loadPageAgain(from: endpoint)
            }
        case .startServer: Task { await session?.startForReload() }
        case .restartServer: session?.retry(from: self)
        case .startAsSelected: session?.windowShown(self)
        }
    }

    /// Loads the window's page again from the ready server, in place of a load still on its
    /// way: the page that load was loading, else the one asked for or shown last, else the
    /// entry page (`PageReload.loadPage`).
    private func loadPageAgain(from endpoint: ServerEndpoint) {
        // Before the stop: the page a load on its way was loading is `webView.url` only
        // until the load stops (`PageRevealWebKitTests`). A window WebKit opened, before
        // its first commit, has no load of the window's to stop, and still needs this.
        rememberPage()
        supersedeLoad()
        isDiscarded = false
        loadNextPageOnceAnswered(from: endpoint)
    }

    /// Answers the sheets the page opened as their Cancel does, one at a time, while one is
    /// attached: an `alert`, `confirm`, or `prompt`, the open panel of a file input, or the
    /// print panel (`PageSheets`). The app's own sheets stay, and the reload runs behind
    /// them: the runtime-upgrade offer, a download's save panel, and a failed download's
    /// alert. Each pass forgets the sheet it ends, so the loop ends even if AppKit detaches
    /// it later.
    private func cancelPageSheets() {
        guard let window else { return }
        for _ in 0..<pageSheets.count {
            guard let sheet = window.attachedSheet, pageSheets.cancels(sheet) else { return }
            pageSheets.closed(sheet)
            if let panel = sheet as? NSOpenPanel {
                panel.cancel(nil)  // an open panel ends its own sheet
            } else {
                window.endSheet(sheet, returnCode: .cancel)
            }
        }
    }

    /// The window as its menu items see it (`PageMenu`, `PageReload`). While the GitHub
    /// view shows, its page is the one on screen, and it needs no server.
    private var windowState: FolderWindowState {
        if gitHub.showsGitHub, let view = gitHubPane?.webView {
            return FolderWindowState(
                phase: status.phase, showsPage: true, hasPage: view.backForwardList.currentItem != nil,
                serverReady: true, canGoBack: view.canGoBack, canGoForward: view.canGoForward)
        }
        return FolderWindowState(
            phase: status.phase, showsPage: !container.showsStatus,
            hasPage: webView.backForwardList.currentItem != nil, serverReady: endpoint != nil,
            canGoBack: webView.canGoBack, canGoForward: webView.canGoForward)
    }

    @objc func actualSize(_ sender: Any?) { setZoom(1) }
    @objc func zoomIn(_ sender: Any?) { setZoom(PageZoom.zoomedIn(shownWebView.pageZoom)) }
    @objc func zoomOut(_ sender: Any?) { setZoom(PageZoom.zoomedOut(shownWebView.pageZoom)) }

    private func setZoom(_ zoom: Double) {
        shownWebView.pageZoom = zoom
        UserDefaults.standard.set(shownWebView.pageZoom, forKey: Self.zoomKey)
    }

    /// File > Print, and the page's own Print button (`PagePrintRequests`).
    ///
    /// The operation runs modally for the window. Run synchronously with `run()` instead,
    /// the same operation printed blank pages until it was stopped at 865 MB (the WebKit
    /// gate's checks, macOS 26.5.2), while modally it printed the document alone.
    @objc func printPage(_ sender: Any?) {
        guard let window else { return }
        let operation = shownWebView.printOperation(with: NSPrintInfo.shared)
        operation.view?.frame = shownWebView.bounds
        let before = window.attachedSheet
        operation.runModal(
            for: window, delegate: self, didRun: #selector(printOperationDidRun(_:success:contextInfo:)),
            contextInfo: nil)
        // The print panel is a sheet the page's print opened, once AppKit has attached it;
        // one queued behind another sheet is not recorded, so Command-R leaves it.
        if let sheet = window.attachedSheet, sheet !== before {
            printSheet = sheet
            pageSheets.opened(sheet)
        }
    }

    @objc private func printOperationDidRun(
        _ operation: NSPrintOperation, success: Bool, contextInfo: UnsafeMutableRawPointer?
    ) {
        if let printSheet { pageSheets.closed(printSheet) }
        printSheet = nil
    }

    /// Every window's page Print buttons (`PagePrintRequests`): each prints through File >
    /// Print's path, in the window whose page asked.
    static let pagePrints = PagePrintRequests { webView, frame in
        (webView.window?.windowController as? BrowserWindowController)?.pageAskedToPrint(frame)
    }

    private func pageAskedToPrint(_ frame: WKFrameInfo) {
        let sheetOpen = window?.attachedSheet != nil
        guard PagePrintRequests.allows(frame, under: policy, sheetOpen: sheetOpen) else {
            AppLog.app.info("a page's print was not answered: not from this server's own origin, or a sheet is open")
            return
        }
        printPage(nil)
    }

    /// Menu items carry the `NSTextFinder.Action` in their tag.
    @objc func performFindAction(_ sender: Any?) {
        guard let tag = (sender as? NSMenuItem)?.tag, let action = NSTextFinder.Action(rawValue: tag) else { return }
        textFinder.performAction(action)
    }

    @objc func restartServer(_ sender: Any?) { session?.retry(from: self) }
    @objc func revealServerLog(_ sender: Any?) { session?.revealLog() }

    /// File > Open in Default Browser: the page the window shows, on the folder's server
    /// or, in the GitHub view, on github.com.
    @objc func openInDefaultBrowser(_ sender: Any?) {
        if let url = shownPageURL { NSWorkspace.shared.open(url) }
    }

    private var shownPageURL: URL? {
        guard gitHub.showsGitHub else { return currentServerURL }
        guard let url = gitHubPane?.webView.url, GitHubViewPolicy.staysInView(url) else { return nil }
        return url
    }

    func validateMenuItem(_ item: NSMenuItem) -> Bool {
        let window = windowState
        switch item.action {
        case #selector(navigateBack(_:)): return PageMenu.isEnabled(.back, in: window)
        case #selector(navigateForward(_:)): return PageMenu.isEnabled(.forward, in: window)
        case #selector(reloadPage(_:)): return PageMenu.isEnabled(.reload, in: window)
        case #selector(printPage(_:)): return PageMenu.isEnabled(.print, in: window)
        case #selector(actualSize(_:)): return PageMenu.isEnabled(.actualSize, in: window)
        case #selector(zoomIn(_:)): return PageMenu.isEnabled(.zoomIn, in: window)
        case #selector(zoomOut(_:)): return PageMenu.isEnabled(.zoomOut, in: window)
        case #selector(performFindAction(_:)):
            guard PageMenu.isEnabled(.find, in: window), let action = NSTextFinder.Action(rawValue: item.tag)
            else { return false }
            return textFinder.validateAction(action)
        case #selector(openInDefaultBrowser(_:)): return shownPageURL != nil
        case #selector(toggleGitHubView(_:)):
            item.title = gitHub.toggleTitle
            return gitHub.showsGitHub || (!container.showsStatus && currentServerURL != nil)
        default: return true
        }
    }
}

// MARK: - Navigation policy, new windows, downloads, and dialogs

extension BrowserWindowController: WKNavigationDelegate, WKUIDelegate {
    func webView(
        _ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
        decisionHandler: @escaping @MainActor (WKNavigationActionPolicy) -> Void
    ) {
        let linkClick = action.navigationType == .linkActivated
        let isMainFrame = action.targetFrame?.isMainFrame ?? true
        let wantsNewWindow = linkClick && action.modifierFlags.contains(.command)
        let decision =
            isGitHubView(webView)
            ? GitHubViewPolicy.decide(
                action.request.url, isMainFrame: isMainFrame,
                byUser: [.linkActivated, .formSubmitted, .formResubmitted].contains(action.navigationType),
                shouldDownload: action.shouldPerformDownload, wantsNewWindow: wantsNewWindow)
            : policy.decide(
                action.request.url, isMainFrame: isMainFrame, isLinkClick: linkClick,
                shouldDownload: action.shouldPerformDownload, wantsNewWindow: wantsNewWindow)
        switch decision {
        case .allow: decisionHandler(.allow)
        case .download: decisionHandler(.download)
        case .openExternally(let url):
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
        case .openInNewWindow(let url):
            session?.openWindow(at: url, besides: self)
            decisionHandler(.cancel)
        case .cancel: decisionHandler(.cancel)
        }
    }

    func webView(
        _ webView: WKWebView, decidePolicyFor response: WKNavigationResponse,
        decisionHandler: @escaping @MainActor (WKNavigationResponsePolicy) -> Void
    ) {
        let disposition = (response.response as? HTTPURLResponse)?.value(forHTTPHeaderField: "Content-Disposition")
        switch ResponsePolicy.decide(canShowMIMEType: response.canShowMIMEType, contentDisposition: disposition) {
        case .show: decisionHandler(.allow)
        case .download: decisionHandler(.download)
        }
    }

    func webView(_ webView: WKWebView, didCommit navigation: WKNavigation!) {
        if isGitHubView(webView) {
            gitHubPane?.showLocation()  // in place of a failure the bar showed
            return
        }
        session?.pageChanged()
        guard reveal.reveals(onCommit: navigation) else { return }
        container.showsStatus = false
        if !gitHub.showsGitHub { window?.makeFirstResponder(webView) }
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: any Error) {
        let cancelled = (error as NSError).code == NSURLErrorCancelled
        if isGitHubView(webView) {
            // A load the policy stopped, or one superseded by the next, is no failure.
            if (error as NSError).domain == NSURLErrorDomain, !cancelled { gitHubPane?.showFailure(error) }
            return
        }
        guard reveal.reports(failureOf: navigation, cancelled: cancelled) else { return }
        status.phase = .failed(ServerFailure(
            summary: "The page did not load: \(error.localizedDescription)", recentOutput: []))
        container.showsStatus = true
    }

    /// WebContent crashed or was killed under memory pressure; never leave a blank window.
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        if isGitHubView(webView) {
            if gitHubRecoveries.allow() { webView.reload() }
            return
        }
        guard contentRecoveries.allow() else {
            AppLog.app.error("web content process died repeatedly; showing the status view")
            supersedeLoad()
            status.phase = .failed(ServerFailure(
                summary: "The page stopped responding repeatedly. Retry restarts the folder's server.",
                recentOutput: []))
            container.showsStatus = true
            return
        }
        reveal.reloaded(webView.reload())
    }

    /// `target=_blank` and `window.open`. The returned view must be built from
    /// `configuration`; WebKit then loads the request into it.
    func webView(
        _ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
        for action: WKNavigationAction, windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        if isGitHubView(webView) {
            switch GitHubViewPolicy.decideNewWindow(action.request.url) {
            case .allow: webView.load(action.request)  // a GitHub page opens here, in place
            case .openExternally(let url): NSWorkspace.shared.open(url)
            default: break
            }
            return nil
        }
        switch policy.decideNewWindow(action.request.url) {
        case .openInNewWindow:
            WebConfiguration.restrict(configuration)
            return session?.openChildWindow(configuration: configuration, besides: self)
        case .openExternally(let url):
            NSWorkspace.shared.open(url)
            return nil
        default:
            return nil
        }
    }

    func webViewDidClose(_ webView: WKWebView) {
        guard !isGitHubView(webView) else { return }  // github.com never closes the window
        window?.close()  // the page called window.close()
    }

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
        download.delegate = Self.downloads
    }

    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
        download.delegate = Self.downloads
    }

    /// Every window's downloads: a save panel opened in Downloads, as a sheet on the window
    /// that started the download. Choosing the destination is user intent, so saving raises
    /// no Downloads-folder privacy prompt. A file the panel confirmed replacing stays until
    /// the new one is complete (`DownloadCoordinator`).
    static let downloads = DownloadCoordinator(
        chooseDestination: { download, suggestedFilename, answer in
            let panel = NSSavePanel()
            panel.nameFieldStringValue = suggestedFilename
            panel.directoryURL = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask).first
            let chosen: (NSApplication.ModalResponse) -> Void = { answer($0 == .OK ? panel.url : nil) }
            if let window = download.webView?.window {
                panel.beginSheetModal(for: window, completionHandler: chosen)
            } else {
                panel.begin(completionHandler: chosen)
            }
        },
        reportFailure: { download, failure in
            AppLog.app.error("download failed: \(failure.message, privacy: .public)")
            let alert = NSAlert()
            alert.messageText = "Download failed"
            alert.informativeText = failure.message
            if let window = download.webView?.window {
                alert.beginSheetModal(for: window)
            } else {
                alert.runModal()
            }
        })

    func webView(
        _ webView: WKWebView, runOpenPanelWith parameters: WKOpenPanelParameters,
        initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping @MainActor ([URL]?) -> Void
    ) {
        guard let window else { return completionHandler(nil) }
        let panel = NSOpenPanel()
        panel.allowsMultipleSelection = parameters.allowsMultipleSelection
        panel.canChooseDirectories = parameters.allowsDirectories
        pageSheets.opened(panel)
        panel.beginSheetModal(for: window) { [weak self] result in
            self?.pageSheets.closed(panel)
            completionHandler(result == .OK ? panel.urls : nil)
        }
    }

    // Without these, WebKit answers alert() with OK and confirm() and prompt() with Cancel.

    func webView(
        _ webView: WKWebView, runJavaScriptAlertPanelWithMessage message: String,
        initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping @MainActor () -> Void
    ) {
        let alert = NSAlert()
        alert.messageText = message
        present(alert) { _ in completionHandler() }
    }

    // The explicit selector keeps this reachable on every SDK. Earlier Xcode 26 SDKs
    // declare the completion handler `@Sendable` rather than main-actor, so Swift does not
    // take this method as the protocol's witness there, and without `@objc` WebKit would
    // find no `confirm()` handler and answer Cancel.
    @objc(webView:runJavaScriptConfirmPanelWithMessage:initiatedByFrame:completionHandler:)
    func webView(
        _ webView: WKWebView, runJavaScriptConfirmPanelWithMessage message: String,
        initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping @MainActor (Bool) -> Void
    ) {
        let alert = NSAlert()
        alert.messageText = message
        alert.addButton(withTitle: "OK")
        alert.addButton(withTitle: "Cancel")
        present(alert) { completionHandler($0 == .alertFirstButtonReturn) }
    }

    func webView(
        _ webView: WKWebView, runJavaScriptTextInputPanelWithPrompt prompt: String, defaultText: String?,
        initiatedByFrame frame: WKFrameInfo, completionHandler: @escaping @MainActor (String?) -> Void
    ) {
        let alert = NSAlert()
        alert.messageText = prompt
        alert.addButton(withTitle: "OK")
        alert.addButton(withTitle: "Cancel")
        let field = NSTextField(string: defaultText ?? "")
        field.frame = NSRect(x: 0, y: 0, width: 280, height: 24)
        alert.accessoryView = field
        present(alert) { completionHandler($0 == .alertFirstButtonReturn ? field.stringValue : nil) }
    }

    /// The page's `alert`, `confirm`, or `prompt`, as a sheet the page opened (`PageSheets`).
    private func present(_ alert: NSAlert, completion: @escaping @MainActor (NSApplication.ModalResponse) -> Void) {
        guard let window else { return completion(alert.runModal()) }
        let sheet = alert.window
        pageSheets.opened(sheet)
        alert.beginSheetModal(for: window) { [weak self] response in
            self?.pageSheets.closed(sheet)
            completion(response)
        }
    }
}
