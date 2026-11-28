import AppKit
import ShellCore
import ShellViews
import SwiftUI
import WebKit

/// One page onto a folder's server: its web view, and what a browser would supply around
/// it (new windows, downloads, dialogs, find, zoom, printing). The page talks to the
/// server directly; this class only decides which navigations stay in the page.
///
/// A window shows one page at a time (`BrowserWindowController`), and the page belongs to
/// its folder's session, not to the window, which only hosts it, so a window can show
/// another page in its place without becoming another window. `host` is the window
/// showing the page, if one is.
final class FolderPage: NSViewController, NSMenuItemValidation {
    static let zoomKey = "pageZoom"
    static let inspectorKey = "WebInspectorEnabled"

    /// Replaced by a fresh view, which has no web process until it loads, when the page
    /// gives up its web view (`discardPage`).
    private(set) var webView: DropAwareWebView
    private(set) weak var session: FolderSession?
    /// The window showing the page, while one is. Its controller sets it when it hosts the
    /// page, and clears it when the window closes or shows another page in its place
    /// (`BrowserWindowController.show`). A page that leaves its window closes its web
    /// popover, which points into it.
    weak var host: BrowserWindowController? {
        didSet { if host !== oldValue { webPopover?.close() } }
    }
    private var policy = NavigationPolicy()
    private var navigationObservations: [NSKeyValueObservation] = []
    private var hasCommittedDocument = false
    private var navigationLabels: [ObjectIdentifier: NavigationHistoryRequests.Label] = [:]
    private var lastNavigationState: FolderNavigationState?
    private let container: WebContainerView
    private let status = WindowStatus()
    private var linkProgress: NSView?
    /// Find on the page: WebKit's own find, run from the window's find bar (`PageFind`).
    private let find = PageFind()
    private lazy var findBar = makeFindBar()
    /// The newest find's number, so an older one's answer, arriving late, is dropped.
    private var findGeneration = 0
    /// The navigation `load` submitted, whose commit reveals the page in place of the
    /// status view, until server state supersedes it (`PageReveal`).
    private var reveal = PageReveal<WKNavigation>()
    /// The page to load next: one asked for (a file opened here, a restored window's page),
    /// else the one shown before the server restarted or the page gave up its web view;
    /// and the loads waiting to load it, of which only the newest may (`PageLoads`).
    private var loads: PageLoads
    /// The folder's server while it is ready.
    private var endpoint: ServerEndpoint?
    /// Whether the page gave up its web view (`PageDiscardPolicy`). It loads again when it
    /// is shown.
    private(set) var isDiscarded = false
    /// Reloads after the web content process dies, then the status view.
    private var contentRecoveries = RecoveryBudget.webContent
    /// The web pane's popover, as View on GitHub opens, from a marked link's first use until
    /// the page closes.
    private var webPopover: WebPopover?
    /// The sheets the page opened, which Command-R cancels before it reloads.
    private var pageSheets = PageSheets<NSWindow>()
    /// The print panel, while a print the page started runs.
    private var printSheet: NSWindow?

    /// Pass `configuration` only from `createWebViewWith`, which requires the web view
    /// it returns to be built from the configuration WebKit hands it. `page` is the page to
    /// load once the server is ready, and a `discarded` page loads it only when shown.
    init(
        session: FolderSession, configuration: WKWebViewConfiguration? = nil, page address: PageAddress? = nil,
        discarded: Bool = false
    ) {
        self.session = session
        webView = Self.makeWebView(configuration ?? Self.pageConfiguration())
        loads = PageLoads(requested: address)
        isDiscarded = discarded

        let statusView = NSHostingView(rootView: StatusView(
            folderName: session.folderName, folderPath: session.location, status: status,
            retry: { [weak session] in session?.retry() },
            revealServerLog: { [weak session] in session?.revealLog() },
            showSettings: { (NSApp.delegate as? AppDelegate)?.showRuntimeSettings() }))
        container = WebContainerView(webView: webView, statusView: statusView)
        super.init(nibName: nil, bundle: nil)

        wire(webView)
        // A page WebKit creates for `target=_blank` shows at once.
        container.showsStatus = configuration == nil
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    override func loadView() { view = container }

    /// The window showing the page, while one is.
    private var window: NSWindow? { host?.window }

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

    /// A page's configuration: the folder's own, with the page's Print button, its links
    /// marked to open in a web pane, and its links marked to open a file in its default app
    /// answered by the page that asked.
    private static func pageConfiguration() -> WKWebViewConfiguration {
        WebConfiguration.make(
            pagePrints: pagePrints, webViews: webViews, openFiles: openFiles, navigationHistory: navigationRequests)
    }

    private func wire(_ webView: DropAwareWebView) {
        webView.navigationDelegate = self
        webView.uiDelegate = self
        navigationObservations = [
            webView.observe(\.url) { [weak self] view, _ in
                MainActor.assumeIsolated { self?.navigationChanged(in: view) }
            },
            webView.observe(\.canGoBack) { [weak self] view, _ in
                MainActor.assumeIsolated { self?.navigationChanged(in: view) }
            },
            webView.observe(\.canGoForward) { [weak self] view, _ in
                MainActor.assumeIsolated { self?.navigationChanged(in: view) }
            },
        ]
        webView.onFileDrop = { urls in
            guard let app = NSApp.delegate as? AppDelegate else { return false }
            urls.forEach { app.request($0, as: .opened) }
            return true
        }
    }

    // MARK: - Server state

    func showStarting() {
        loads.cancelAll()
        rememberPage()
        supersedeLoad()
        endpoint = nil
        status.phase = .starting
        container.showsStatus = true
        navigationChanged(in: webView)
    }

    func showFailure(_ failure: ServerFailure) {
        loads.cancelAll()
        rememberPage()
        supersedeLoad()
        endpoint = nil
        status.phase = .failed(failure)
        container.showsStatus = true
        navigationChanged(in: webView)
    }

    /// A restored folder in a protected location, whose server starts when this page is
    /// shown.
    func showWaitingForSelection() {
        supersedeLoad()
        status.phase = .waitingForSelection
        container.showsStatus = true
        navigationChanged(in: webView)
    }

    /// A folder whose start waits for a metab the app accepts: none was found, or the one
    /// found changed and is being checked again.
    func showWaitingForRuntime() {
        rememberPage()
        supersedeLoad()
        endpoint = nil
        status.phase = .waitingForRuntime
        container.showsStatus = true
        navigationChanged(in: webView)
    }

    /// Server state now covers the page. A load still on its way is remembered as the
    /// page to show next and stopped, and none of its callbacks, even one WebKit has
    /// already sent, can change the status (`PageReveal`).
    private func supersedeLoad() {
        guard reveal.supersede() else { return }
        rememberPage()
        webView.stopLoading()
    }

    /// Loads the page this page is to show, on the new origin, or the server's entry
    /// page. A discarded page only remembers the server until it is shown.
    func attach(_ endpoint: ServerEndpoint, authorization: WebAuthorization) {
        if policy.origin != nil, !policy.isAppOrigin(endpoint.origin) {
            rememberPage()
            loads.cancelAll()
            supersedeLoad()
            container.showsStatus = true
            replaceWebView()
        }
        let ticket = loads.begin()  // which supersedes every load still waiting
        policy.origin = endpoint.origin
        self.endpoint = endpoint
        navigationChanged(in: webView)
        if isDiscarded { status.phase = .reloading }
        Task {
            await install(authorization, for: endpoint)
            guard self.endpoint == endpoint, !isDiscarded else { return }
            load(loads.take(for: ticket), from: endpoint)
        }
    }

    /// For a page opened from a link: the page is loaded by WebKit or by `load`.
    func adoptServer(_ endpoint: ServerEndpoint?) {
        policy.origin = endpoint?.origin
        self.endpoint = endpoint
        navigationChanged(in: webView)
    }

    /// Shows `address` now if the server is ready and still answers, or once it is ready.
    func show(_ address: PageAddress) {
        webPopover?.close()
        loads.request(address)
        isDiscarded = false
        if let endpoint { loadNextPageOnceAnswered(from: endpoint) }
    }

    /// Whether the start waits for another repository's, which can be a first clone.
    func showWaitingAtGate(_ waiting: Bool) {
        status.waitsForAnotherStart = waiting
    }

    /// What a repository's start says it is doing, such as how far its clone has got.
    func showStartProgress(_ progress: StartProgress?) {
        status.progress = progress
    }

    /// An explicit link into a ready server leaves its current page visible while the
    /// server resolves the new link.
    func showOpeningLink(_ showing: Bool) {
        linkProgress?.removeFromSuperview()
        linkProgress = nil
        guard showing else { return }
        let badge = NSHostingView(rootView: HStack(spacing: 8) {
            ProgressView().controlSize(.small).accessibilityHidden(true)
            Text("Opening GitHub link…").font(.callout).foregroundStyle(.secondary)
        }
        .padding(8)
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 8)))
        badge.translatesAutoresizingMaskIntoConstraints = false
        container.addSubview(badge)
        NSLayoutConstraint.activate([
            badge.centerXAnchor.constraint(equalTo: container.centerXAnchor),
            badge.topAnchor.constraint(equalTo: container.topAnchor, constant: 12),
        ])
        linkProgress = badge
    }

    /// The page to save for the next launch.
    var currentPage: PageAddress? {
        loads.saved(showing: currentServerURL.flatMap(PageAddress.init))
    }

    /// Gives up the page's web view, which ends its WebContent process, and keeps the
    /// page to load again from the folder's server when it is shown.
    func discardPage() {
        guard !isDiscarded else { return }
        loads.cancelAll()
        rememberPage()
        isDiscarded = true
        reveal.supersede()  // the discarded view is stopped below
        replaceWebView()
        if endpoint != nil { status.phase = .reloading }
        container.showsStatus = true
        navigationChanged(in: webView)
    }

    private func replaceWebView() {
        let discarded = webView
        navigationObservations = []
        hasCommittedDocument = false
        navigationLabels.removeAll()
        lastNavigationState = nil
        discarded.stopLoading()
        discarded.navigationDelegate = nil
        discarded.uiDelegate = nil
        discarded.onFileDrop = nil
        webPopover?.discard()
        webView = Self.makeWebView(Self.pageConfiguration())
        wire(webView)
        container.replaceWebView(webView)
    }

    /// Loads the page again after `discardPage`: now if the server is ready and still
    /// answers, or when it is ready.
    private func revivePage() {
        guard isDiscarded else { return }
        isDiscarded = false
        if let endpoint { loadNextPageOnceAnswered(from: endpoint) }
    }

    /// Loads from a server that was ready before this page asked, once it proves it still
    /// answers: a live pid is not a working server. One that does not answer fails, and
    /// every page of the folder says so. Only the newest waiting load loads (`PageLoads`),
    /// so overlapping requests end on the newest page.
    private func loadNextPageOnceAnswered(from endpoint: ServerEndpoint) {
        let ticket = loads.begin()
        Task {
            guard let session, case .healthy = await session.checkHealth(), self.endpoint == endpoint,
                  !isDiscarded
            else { return }
            load(loads.take(for: ticket), from: endpoint)
        }
    }

    /// Loads the page a ticket's turn gives, or nothing for a superseded ticket.
    private func load(_ turn: PageLoads.Load, from endpoint: ServerEndpoint) {
        guard case .page(let address) = turn else { return }
        load(address.flatMap { $0.url(on: endpoint.origin) } ?? endpoint.entryURL)
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
        if let address = currentServerURL.flatMap(PageAddress.init) { loads.remember(shown: address) }
    }

    // MARK: - Shown and closed

    /// The window showing the page became key, as when the user brings it forward, or the
    /// window began to show it (`FolderWindows.switchWindow`): a discarded page loads again,
    /// and the folder counts it as shown.
    func shown() {
        revivePage()
        session?.pageShown(self)
    }

    /// The page is gone for good: its window closed, or its folder did (Close Folder).
    /// Nothing it started may load or call back after this.
    func close() {
        loads.cancelAll()
        webPopover?.discard()
        webPopover = nil
        container.isFindBarVisible = false
        navigationObservations = []
        webView.stopLoading()
        webView.navigationDelegate = nil
        webView.uiDelegate = nil
        session?.pageClosed(self)
    }

    // MARK: - Menu actions (nil-targeted: BrowserWindowController.supplementalTarget says how they arrive)

    @objc func navigateBack(_ sender: Any?) { moveInHistory(.back) }
    @objc func navigateForward(_ sender: Any?) { moveInHistory(.forward) }
    @objc func showBackHistory(_ sender: Any?) { host?.showHistory(.back, fromKeyboard: true) }
    @objc func showForwardHistory(_ sender: Any?) { host?.showHistory(.forward, fromKeyboard: true) }
    @objc func copyCurrentURL(_ sender: Any?) { host?.copyCurrentURL() }

    /// Command-R, in every state the page can be in (`PageReload`).
    @objc func reloadPage(_ sender: Any?) {
        cancelPageSheets()
        switch PageReload.route(in: pageState) {
        case .reloadPage: webView.reload()
        case .loadPage: if let endpoint { loadPageAgain(from: endpoint) }
        case .startServer: Task { await session?.startForReload() }
        case .restartServer: session?.retry(from: self)
        case .startAsSelected: session?.pageShown(self)
        }
    }

    /// Loads the page again from the ready server, in place of a load still on its way: the
    /// page that load was loading, else the one asked for or shown last, else the entry
    /// page (`PageReload.loadPage`).
    private func loadPageAgain(from endpoint: ServerEndpoint) {
        // Before the stop: the page a load on its way was loading is `webView.url` only
        // until the load stops (`PageRevealWebKitTests`). A page WebKit opened, before its
        // first commit, has no load of the page's to stop, and still needs this.
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

    /// The page as its menu items see it (`PageMenu`, `PageReload`).
    private var pageState: FolderWindowState {
        FolderWindowState(
            phase: status.phase, showsPage: !container.showsStatus,
            hasPage: webView.backForwardList.currentItem != nil, serverReady: endpoint != nil,
            canGoBack: webView.canGoBack, canGoForward: webView.canGoForward)
    }

    @objc func actualSize(_ sender: Any?) { setZoom(1) }
    @objc func zoomIn(_ sender: Any?) { setZoom(PageZoom.zoomedIn(webView.pageZoom)) }
    @objc func zoomOut(_ sender: Any?) { setZoom(PageZoom.zoomedOut(webView.pageZoom)) }

    private func setZoom(_ zoom: Double) {
        webView.pageZoom = zoom
        UserDefaults.standard.set(webView.pageZoom, forKey: Self.zoomKey)
    }

    /// File > Print, and the page's own Print button (`PagePrintRequests`).
    ///
    /// The operation runs modally for the window. Run synchronously with `run()` instead,
    /// the same operation printed blank pages until it was stopped at 865 MB (the WebKit
    /// gate's checks, macOS 26.5.2), while modally it printed the document alone.
    @objc func printPage(_ sender: Any?) {
        guard let window else { return }
        let operation = webView.printOperation(with: NSPrintInfo.shared)
        operation.view?.frame = webView.bounds
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

    /// Every page's Print buttons (`PagePrintRequests`): each prints through File > Print's
    /// path, in the page that asked, while a window shows it.
    static let pagePrints = PagePrintRequests { webView, frame in
        guard let page = (webView.window?.windowController as? BrowserWindowController)?.page,
              page.webView === webView
        else { return }
        page.pageAskedToPrint(frame)
    }

    private func pageAskedToPrint(_ frame: WKFrameInfo) {
        let sheetOpen = window?.attachedSheet != nil
        guard PagePrintRequests.allows(frame, under: policy, sheetOpen: sheetOpen) else {
            AppLog.app.info("a page's print was not answered: not from this server's own origin, or a sheet is open")
            return
        }
        printPage(nil)
    }

    /// Every page's links marked to open in a web pane (`WebViewRequests`), as View on
    /// GitHub's is: each opens the popover of the page that asked, while a window shows it.
    static let webViews = WebViewRequests { webView, frame, request in
        guard let page = (webView.window?.windowController as? BrowserWindowController)?.page,
              page.webView === webView
        else { return }
        page.pageAskedToShowWeb(request, from: frame)
    }

    /// Opens the web pane's popover below the page's marked link, on the link's page, for a
    /// click in the main frame of the server's own page.
    private func pageAskedToShowWeb(_ request: WebViewRequests.Request, from frame: WKFrameInfo) {
        guard WebViewRequests.allows(frame, under: policy) else {
            AppLog.app.info("a web pane link's click was not answered: not from this server's own page")
            return
        }
        let popover = webPopover ?? WebPopover(isInspectable: Self.isInspectable)
        webPopover = popover
        popover.onVisibilityChange = { [weak self] in self?.host?.pageNavigationChanged() }
        let anchor = WebPopoverLayout.anchor(
            request.link, viewportWidth: request.viewportWidth, in: webView.bounds, flipped: webView.isFlipped)
        popover.show(request.page, at: anchor, of: webView)
    }

    /// Every page's Open links (`OpenFileRequests`), as the `pdf` plugin draws: each opens
    /// its file in its default app for the page that asked, while a window shows it.
    static let openFiles = OpenFileRequests { webView, frame, request in
        guard let page = (webView.window?.windowController as? BrowserWindowController)?.page,
              page.webView === webView
        else { return }
        page.pageAskedToOpen(request, from: frame)
    }

    /// Every page's downloaded copies, for an Open link to a file with no folder on disk
    /// (`OpenFileDownloads`), in `Caches/<bundle identifier>/Opened/`.
    static let openedCopies = OpenFileDownloads(
        directory: OpenFileDownloads.directory(bundleIdentifier: appIdentity.bundleIdentifier))

    /// Removes the copies an Open link downloaded more than `OpenFileDownloads.kept` ago,
    /// off the main thread. The app calls it once, as it launches.
    static func sweepOpenedCopies() {
        let directory = OpenFileDownloads.directory(bundleIdentifier: appIdentity.bundleIdentifier)
        Task.detached(priority: .utility) { OpenFileDownloads.sweep(directory) }
    }

    /// Opens the file an Open link names, for a click in the main frame of the server's own
    /// page, as `OpenFilePlan` decides from what the folder serves.
    private func pageAskedToOpen(_ request: OpenFileRequests.Request, from frame: WKFrameInfo) {
        guard OpenFileRequests.allows(frame, request, under: policy) else {
            AppLog.app.info("an Open link's click was not answered: not from this server's own page, or not to it")
            return
        }
        guard let root = session?.served else { return }
        switch OpenFilePlan.resolve(request, in: root) {
        case .openFile(let file):
            Self.open(file, named: request.name, reportingIn: window)
        case .downloadThenOpen(let href, let name):
            Self.openedCopies.start(href, named: name, in: webView) { [weak webView] result in
                let window = webView?.window
                switch result {
                case .success(let copy): Self.open(copy, named: name, reportingIn: window)
                case .failure(let failure): Self.report(failure, in: window)
                }
            }
        case .refuse(let failure):
            Self.report(failure, in: window)
        }
    }

    /// Hands `file` to Launch Services, which opens it in the app macOS assigns to its type,
    /// or, when no app is assigned to it, saves a copy in Downloads (`OpenFileHandoff`).
    private static func open(_ file: URL, named name: String, reportingIn window: NSWindow?) {
        switch OpenFileHandoff.decide(file, defaultApp: { NSWorkspace.shared.urlForApplication(toOpen: $0) }) {
        case .open(let file):
            Task { [weak window] in
                do {
                    _ = try await NSWorkspace.shared.open(file, configuration: NSWorkspace.OpenConfiguration())
                } catch {
                    report(OpenFileFailure(name: name, reason: "no app opened it (\(error.localizedDescription))"), in: window)
                }
            }
        case .saveToDownloads(let file):
            saveToDownloads(file, reportingIn: window)
        }
    }

    /// Saves a copy of `file` in Downloads (`OpenFileSaves`) and says where it went. The
    /// copy is made off the main thread: a file on another volume is copied byte by byte,
    /// and the first write to Downloads waits for the user to answer macOS's privacy prompt.
    private static func saveToDownloads(_ file: URL, reportingIn window: NSWindow?) {
        let downloads = OpenFileSaves.downloads
        Task { [weak window] in
            let saved = await Task.detached(priority: .userInitiated) {
                Result { () throws(OpenFileFailure) -> URL in try OpenFileSaves.save(file, into: downloads) }
            }.value
            switch saved {
            case .success(let copy): tell(OpenFileSaved(copy: copy), in: window)
            case .failure(let failure): report(failure, in: window)
            }
        }
    }

    /// An alert that names the copy saved in Downloads and why the file did not open, as a
    /// sheet on `window`, or an alert of its own once the page has no window, with Show in
    /// Finder.
    private static func tell(_ saved: OpenFileSaved, in window: NSWindow?) {
        AppLog.app.info("open saved to Downloads: \(saved.copy.lastPathComponent, privacy: .public)")
        let alert = NSAlert()
        alert.messageText = saved.title
        alert.informativeText = saved.message
        alert.addButton(withTitle: "OK")
        alert.addButton(withTitle: "Show in Finder")
        let answer: (NSApplication.ModalResponse) -> Void = { response in
            guard response == .alertSecondButtonReturn else { return }
            NSWorkspace.shared.activateFileViewerSelecting([saved.copy])
        }
        if let window {
            alert.beginSheetModal(for: window, completionHandler: answer)
        } else {
            answer(alert.runModal())
        }
    }

    /// An alert that names the file and why it did not open, as a sheet on `window`, or an
    /// alert of its own once the page has no window, as a failed download's is. A file on
    /// disk of a type the app does not open is offered to Finder.
    private static func report(_ failure: OpenFileFailure, in window: NSWindow?) {
        AppLog.app.error("open failed: \(failure.message, privacy: .public)")
        let alert = NSAlert()
        alert.messageText = "Open failed"
        alert.informativeText = failure.message
        alert.addButton(withTitle: "OK")
        if failure.reveal != nil { alert.addButton(withTitle: "Reveal in Finder") }
        let answer: (NSApplication.ModalResponse) -> Void = { response in
            guard response == .alertSecondButtonReturn, let file = failure.reveal else { return }
            NSWorkspace.shared.activateFileViewerSelecting([file])
        }
        if let window {
            alert.beginSheetModal(for: window, completionHandler: answer)
        } else {
            answer(alert.runModal())
        }
    }

    /// After Metabrowser > Clear Website Data…: the popover's page loads again, signed out,
    /// if what was cleared includes its site's data.
    func reloadWebPopover(after clearing: WebDataClearing) {
        webPopover?.reload(after: clearing)
    }

    /// Menu items carry the `NSTextFinder.Action` in their tag, though `PageFind`, not
    /// `NSTextFinder`, answers them (mb-jkbp).
    @objc func performFindAction(_ sender: Any?) {
        guard let tag = (sender as? NSMenuItem)?.tag, let action = NSTextFinder.Action(rawValue: tag) else { return }
        switch action {
        case .showFindInterface:
            showFindBar()
        case .nextMatch, .previousMatch:
            // With no search string yet, the shared one other apps' Find set, as in Safari.
            if find.query.isEmpty, let shared = NSPasteboard(name: .find).string(forType: .string), !shared.isEmpty {
                find.use(shared)
                findBar.field.stringValue = shared
            }
            guard !find.query.isEmpty else { return showFindBar() }
            runFind { find, webView in await find.step(action == .nextMatch ? .next : .previous, in: webView) }
        case .setSearchString:
            let webView = self.webView
            Task { [weak self] in
                guard let self, let text = await find.selection(in: webView) else { return }
                find.use(text)
                findBar.field.stringValue = text
                shareSearchString(text)
            }
        case .hideFindInterface:
            hideFindBar()
        default:
            return
        }
    }

    private func makeFindBar() -> FindBar {
        let bar = FindBar()
        bar.onSearch = { [weak self] text in
            self?.shareSearchString(text)
            self?.runFind { find, webView in await find.search(text, in: webView) }
        }
        bar.onStep = { [weak self] step in
            self?.runFind { find, webView in await find.step(step, in: webView) }
        }
        bar.onClose = { [weak self] in self?.hideFindBar() }
        return bar
    }

    private func showFindBar() {
        container.findBarView = findBar
        container.isFindBarVisible = true
        if findBar.field.stringValue.isEmpty, let shared = NSPasteboard(name: .find).string(forType: .string) {
            findBar.field.stringValue = shared
            find.use(shared)
        }
        window?.makeFirstResponder(findBar.field)
        findBar.field.selectText(nil)
    }

    private func hideFindBar() {
        guard container.isFindBarVisible else { return }
        container.isFindBarVisible = false
        findBar.show(found: nil)
        window?.makeFirstResponder(webView)
    }

    /// The search string other apps' Find reads, as macOS shares it.
    private func shareSearchString(_ text: String) {
        guard !text.isEmpty else { return }
        let pasteboard = NSPasteboard(name: .find)
        pasteboard.clearContents()
        pasteboard.setString(text, forType: .string)
    }

    /// Run one find against the page shown now and show its answer, unless a newer find
    /// started meanwhile.
    private func runFind(_ body: @escaping @MainActor (PageFind, WKWebView) async -> Bool?) {
        findGeneration += 1
        let generation = findGeneration
        let webView = self.webView
        Task { [weak self] in
            guard let self else { return }
            let found = await body(find, webView)
            if generation == findGeneration { findBar.show(found: found) }
        }
    }

    @objc func restartServer(_ sender: Any?) { session?.retry(from: self) }
    @objc func revealServerLog(_ sender: Any?) { session?.revealLog() }

    @objc func openInDefaultBrowser(_ sender: Any?) {
        if let url = navigationState.url, historyAvailable { NSWorkspace.shared.open(url) }
    }

    func validateMenuItem(_ item: NSMenuItem) -> Bool {
        let state = pageState
        switch item.action {
        case #selector(navigateBack(_:)), #selector(showBackHistory(_:)):
            return historyAvailable && navigationState.back
        case #selector(navigateForward(_:)), #selector(showForwardHistory(_:)):
            return historyAvailable && navigationState.forward
        case #selector(reloadPage(_:)): return PageMenu.isEnabled(.reload, in: state)
        case #selector(printPage(_:)): return PageMenu.isEnabled(.print, in: state)
        case #selector(actualSize(_:)): return PageMenu.isEnabled(.actualSize, in: state)
        case #selector(zoomIn(_:)): return PageMenu.isEnabled(.zoomIn, in: state)
        case #selector(zoomOut(_:)): return PageMenu.isEnabled(.zoomOut, in: state)
        case #selector(performFindAction(_:)):
            guard PageMenu.isEnabled(.find, in: state), let action = NSTextFinder.Action(rawValue: item.tag)
            else { return false }
            return action != .hideFindInterface || container.isFindBarVisible
        case #selector(openInDefaultBrowser(_:)), #selector(copyCurrentURL(_:)):
            return historyAvailable && navigationState.url != nil
        default: return true
        }
    }
}

// MARK: - Navigation policy, new windows, downloads, and dialogs

extension FolderPage: WKNavigationDelegate, WKUIDelegate {
    func webView(
        _ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
        decisionHandler: @escaping @MainActor (WKNavigationActionPolicy) -> Void
    ) {
        let linkClick = action.navigationType == .linkActivated
        let decision = policy.decide(
            action.request.url, isMainFrame: action.targetFrame?.isMainFrame ?? true, isLinkClick: linkClick,
            shouldDownload: action.shouldPerformDownload,
            wantsNewWindow: linkClick && action.modifierFlags.contains(.command))
        switch decision {
        case .allow: decisionHandler(.allow)
        case .download: decisionHandler(.download)
        case .openExternally(let url):
            NSWorkspace.shared.open(url)
            decisionHandler(.cancel)
        case .openInNewWindow(let url):
            session?.openWindow(at: url)
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
        guard self.webView === webView else { return }
        hasCommittedDocument = true
        session?.pageChanged()
        if reveal.reveals(onCommit: navigation) {
            container.showsStatus = false
            window?.makeFirstResponder(webView)
        }
        navigationChanged(in: webView, publish: true)
    }

    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        navigationChanged(in: webView, publish: true)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: any Error) {
        let cancelled = (error as NSError).code == NSURLErrorCancelled
        guard reveal.reports(failureOf: navigation, cancelled: cancelled) else { return }
        status.phase = .failed(ServerFailure(
            summary: "The page did not load: \(error.localizedDescription)", recentOutput: []))
        container.showsStatus = true
        navigationChanged(in: webView)
    }

    /// WebContent crashed or was killed under memory pressure; never leave a blank page.
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        hasCommittedDocument = false
        navigationChanged(in: webView)
        guard contentRecoveries.allow() else {
            AppLog.app.error("web content process died repeatedly; showing the status view")
            supersedeLoad()
            status.phase = .failed(ServerFailure(
                summary: "The page stopped responding repeatedly. Retry restarts the folder's server.",
                recentOutput: []))
            container.showsStatus = true
            navigationChanged(in: webView)
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
        switch policy.decideNewWindow(action.request.url) {
        case .openInNewWindow:
            WebConfiguration.restrict(configuration)
            return session?.openChildWindow(configuration: configuration)
        case .openExternally(let url):
            NSWorkspace.shared.open(url)
            return nil
        default:
            return nil
        }
    }

    func webViewDidClose(_ webView: WKWebView) {
        window?.close()  // the page called window.close()
    }

    func webView(_ webView: WKWebView, navigationAction: WKNavigationAction, didBecome download: WKDownload) {
        download.delegate = Self.downloads
    }

    func webView(_ webView: WKWebView, navigationResponse: WKNavigationResponse, didBecome download: WKDownload) {
        download.delegate = Self.downloads
    }

    /// Every page's downloads: a save panel opened in Downloads, as a sheet on the window
    /// that started the download. Choosing the destination is user intent, so saving raises
    /// no Downloads-folder privacy prompt. A file the panel confirmed replacing stays until
    /// the new one is complete (`DownloadCoordinator`). A download that a page no window
    /// shows starts, as a folder's page in the background can by script, saves nothing:
    /// nobody is there to choose where. A failed download's alert still reaches the user,
    /// who chose to save it, as an alert of its own once its page has no window.
    static let downloads = DownloadCoordinator(
        chooseDestination: { download, suggestedFilename, answer in
            guard let window = download.webView?.window else {
                AppLog.app.info("not saving \(suggestedFilename, privacy: .public): a page no window shows started it")
                return answer(nil)
            }
            let panel = NSSavePanel()
            panel.nameFieldStringValue = suggestedFilename
            panel.directoryURL = FileManager.default.urls(for: .downloadsDirectory, in: .userDomainMask).first
            panel.beginSheetModal(for: window) { answer($0 == .OK ? panel.url : nil) }
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
        presentPageAlert(alert) { _ in completionHandler() }
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
        presentPageAlert(alert) { completionHandler($0 == .alertFirstButtonReturn) }
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
        presentPageAlert(alert) { completionHandler($0 == .alertFirstButtonReturn ? field.stringValue : nil) }
    }

    /// The page's `alert`, `confirm`, or `prompt`, as a sheet the page opened (`PageSheets`).
    /// A page no window shows, a folder's page in the background, gets WebKit's own answer
    /// at once, OK for `alert` and Cancel for `confirm` and `prompt`, rather than an alert
    /// modal to the whole app from a page nobody can see.
    private func presentPageAlert(_ alert: NSAlert, completion: @escaping @MainActor (NSApplication.ModalResponse) -> Void) {
        guard let window else {
            AppLog.app.info(
                "a page of \(self.session?.folderName ?? "", privacy: .public) that no window shows opened a dialog; answered as WebKit does without one")
            return completion(.cancel)
        }
        let sheet = alert.window
        pageSheets.opened(sheet)
        alert.beginSheetModal(for: window) { [weak self] response in
            self?.pageSheets.closed(sheet)
            completion(response)
        }
    }
}

struct FolderNavigationState: Equatable {
    let url: URL?
    let back: Bool
    let forward: Bool
}

typealias HistoryDirection = NavigationHistoryRequests.Direction

extension FolderPage {
    static let navigationRequests = NavigationHistoryRequests { view, frame, request in
        guard let page = (view.window?.windowController as? BrowserWindowController)?.page,
              page.webView === view
        else { return }
        page.handleNavigationRequest(request, from: frame)
    }

    var webContentHasFocus: Bool {
        guard let responder = window?.firstResponder as? NSView else { return false }
        return responder === webView || responder.isDescendant(of: webView)
    }

    var historyAvailable: Bool {
        window?.isKeyWindow == true && window?.attachedSheet == nil && host?.isShowingSheet != true
            && webPopover?.isShown != true
    }

    private var committedURL: URL? {
        guard endpoint != nil, !container.showsStatus, hasCommittedDocument,
              let current = webView.backForwardList.currentItem,
              let url = webView.url, current.url.absoluteString == url.absoluteString,
              policy.isAppOrigin(url), url.user() == nil, url.password() == nil
        else { return nil }
        return url
    }

    var navigationState: FolderNavigationState {
        let url = committedURL
        return FolderNavigationState(
            url: url, back: url != nil && !historyItems(.back).isEmpty,
            forward: url != nil && !historyItems(.forward).isEmpty)
    }

    func historyItems(_ direction: HistoryDirection) -> [WKBackForwardListItem] {
        guard committedURL != nil else { return [] }
        let list = webView.backForwardList
        let items = direction == .back ? Array(list.backList.reversed()) : list.forwardList
        return Array(items.prefix { policy.isAppOrigin($0.url) })
    }

    func historyLabel(for item: WKBackForwardListItem) -> NavigationHistoryRequests.Label? {
        navigationLabels[ObjectIdentifier(item)].flatMap { $0.url == item.url.absoluteString ? $0 : nil }
    }

    func moveInHistory(_ direction: HistoryDirection) {
        guard let target = historyItems(direction).first else { return }
        traverseHistory(to: target, direction: direction, from: webView.backForwardList.currentItem, in: webView)
    }

    func traverseHistory(
        to target: WKBackForwardListItem, direction: HistoryDirection, from current: WKBackForwardListItem?,
        in view: WKWebView
    ) {
        guard historyAvailable, let item = historyTarget(target, direction: direction, from: current, in: view)
        else { return }
        view.go(to: item)
    }

    /// Revalidates a captured entry against the page and history that still own it.
    func historyTarget(
        _ target: WKBackForwardListItem, direction: HistoryDirection, from current: WKBackForwardListItem?,
        in view: WKWebView
    ) -> WKBackForwardListItem? {
        guard host?.page === self, view === webView, current === view.backForwardList.currentItem else { return nil }
        return historyItems(direction).first { $0 === target }
    }

    private func navigationChanged(in view: WKWebView, publish: Bool = false) {
        guard view === webView else { return }
        let state = navigationState
        if state != lastNavigationState || publish {
            lastNavigationState = state
            host?.pageNavigationChanged()
            if let url = state.url,
               let urlData = try? JSONEncoder().encode(url.absoluteString),
               let address = String(data: urlData, encoding: .utf8) {
                // The evaluation may arrive after another document takes over the web view.
                view.evaluateJavaScript("""
                    if (window.origin !== 'null' && location.href === \(address)) {
                        window.MetabrowserNativeNavigation?.setState({back: \(state.back), forward: \(state.forward)});
                    }
                    """, completionHandler: nil)
            }
        }
        let list = view.backForwardList
        var items = list.backList + list.forwardList
        if let current = list.currentItem { items.append(current) }
        let retained = Set(items.map(ObjectIdentifier.init))
        navigationLabels = navigationLabels.filter { retained.contains($0.key) }
    }

    private func handleNavigationRequest(_ request: NavigationHistoryRequests.Request, from frame: WKFrameInfo) {
        guard NavigationHistoryRequests.allows(frame, under: policy),
              let url = committedURL?.absoluteString
        else { return }
        switch request {
        case .state(let address):
            guard address == url else { return }
            navigationChanged(in: webView, publish: true)
        case .history(let direction, let address):
            guard address == url, webContentHasFocus else { return }
            moveInHistory(direction)
        case .reveal(let visible, let address):
            guard address == url, historyAvailable, webContentHasFocus else { return }
            host?.showPageNavigationHints(visible)
        case .label(let label):
            guard label.url == url, let current = webView.backForwardList.currentItem else { return }
            navigationLabels[ObjectIdentifier(current)] = label
        }
    }
}
