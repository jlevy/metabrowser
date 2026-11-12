import AppKit
import ShellCore
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
    /// Reveal the page, replacing the status view, once this window's load commits.
    private var revealOnCommit = false
    /// The page to load next: one asked for (a file opened here, a restored tab's page),
    /// else the one shown before the server restarted or the tab gave up its page.
    private var next: NextPage
    /// The folder's server while it is ready.
    private var endpoint: ServerEndpoint?
    /// Whether the tab gave up its page's web view (`TabDiscardPolicy`). It loads the page
    /// again when it is shown.
    private(set) var isDiscarded = false
    /// Reloads after the web content process dies: two within 30 s, then the status view.
    private var contentRecoveries = RecoveryBudget(limit: 2, within: .seconds(30))
    private static var cascadePoint = NSPoint.zero

    /// Pass `configuration` only from `createWebViewWith`, which requires the web view
    /// it returns to be built from the configuration WebKit hands it. `page` is the page to
    /// load once the server is ready, and a `discarded` window loads it only when shown.
    init(
        session: FolderSession, configuration: WKWebViewConfiguration? = nil, page: PageAddress? = nil,
        discarded: Bool = false
    ) {
        self.session = session
        webView = Self.makeWebView(configuration ?? WebConfiguration.make(pagePrints: Self.pagePrints))
        next = NextPage(requested: page)
        isDiscarded = discarded

        let path = (session.root.path(percentEncoded: false) as NSString).abbreviatingWithTildeInPath
        let statusView = NSHostingView(rootView: StatusView(
            folderName: session.folderName, folderPath: path, status: status,
            retry: { [weak session] in session?.retry() },
            revealLogs: { [weak session] in session?.revealLog() },
            showSettings: { (NSApp.delegate as? AppDelegate)?.showSettings(nil) }))
        container = WebContainerView(webView: webView, statusView: statusView)

        let window = NSWindow(
            contentRect: NSRect(x: 0, y: 0, width: 1200, height: 820),
            styleMask: [.titled, .closable, .miniaturizable, .resizable],
            backing: .buffered, defer: false)
        window.contentView = container
        window.minSize = NSSize(width: 480, height: 320)
        window.titleVisibility = .hidden  // TitleAccessoryController draws the title
        window.addTitlebarAccessoryViewController(titleAccessory)
        window.tabbingIdentifier = Self.tabbingIdentifier
        window.isReleasedWhenClosed = false
        window.center()
        Self.cascadePoint = window.cascadeTopLeft(from: Self.cascadePoint)
        super.init(window: window)
        window.delegate = self

        wire(webView)
        textFinder.findBarContainer = container
        textFinder.isIncrementalSearchingEnabled = true
        showTitle(session.title)
        // A window WebKit creates for `target=_blank` shows its page at once.
        container.showsStatus = configuration == nil
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    /// Safari's Develop menu can inspect the page in debug builds, or in any build after
    /// `defaults write io.github.jlevy.metabrowser WebInspectorEnabled -bool true`.
    private static var isInspectable: Bool {
        #if DEBUG
            true
        #else
            UserDefaults.standard.bool(forKey: inspectorKey)
        #endif
    }

    private static var savedZoom: Double {
        let zoom = UserDefaults.standard.double(forKey: zoomKey)
        return zoom > 0 ? zoom : 1
    }

    private static func makeWebView(_ configuration: WKWebViewConfiguration) -> DropAwareWebView {
        let webView = DropAwareWebView(frame: .zero, configuration: configuration)
        webView.isInspectable = isInspectable
        webView.allowsBackForwardNavigationGestures = true
        webView.allowsMagnification = true
        webView.pageZoom = savedZoom
        return webView
    }

    private func wire(_ webView: DropAwareWebView) {
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.onFileDrop = { urls in
            guard let app = NSApp.delegate as? AppDelegate else { return false }
            urls.forEach(app.request)
            return true
        }
        textFinder.client = webView  // WKWebView adopts NSTextFinderClient
    }

    // MARK: - Server state

    func showStarting() {
        rememberPage()
        endpoint = nil
        status.phase = .starting
        container.showsStatus = true
    }

    func showFailure(_ failure: ServerFailure) {
        rememberPage()
        endpoint = nil
        status.phase = .failed(failure)
        container.showsStatus = true
    }

    /// A restored folder in a protected location, whose server starts when this tab is
    /// selected.
    func showWaitingForSelection() {
        status.phase = .waitingForSelection
        container.showsStatus = true
    }

    /// A folder whose start waits for a metab the app accepts: none was found, or the one
    /// found changed and is being checked again.
    func showWaitingForRuntime() {
        rememberPage()
        endpoint = nil
        status.phase = .waitingForRuntime
        container.showsStatus = true
    }

    /// Loads the page this window is to show, on the new origin, or the server's entry
    /// page. A discarded tab only remembers the server until it is shown.
    func attach(_ endpoint: ServerEndpoint, authorization: WebAuthorization) {
        policy.origin = endpoint.origin
        self.endpoint = endpoint
        if isDiscarded { status.phase = .reloading }
        Task {
            await install(authorization, for: endpoint)
            guard self.endpoint == endpoint, !isDiscarded else { return }
            loadNextPage(from: endpoint)
        }
    }

    /// For a window opened from a link: the page is loaded by WebKit or by `load`.
    func adoptServer(_ endpoint: ServerEndpoint?) {
        policy.origin = endpoint?.origin
        self.endpoint = endpoint
    }

    /// Shows `page` now if the server is ready, or once it is.
    func show(_ page: PageAddress) {
        next.request(page)
        isDiscarded = false
        if let endpoint { loadNextPage(from: endpoint) }
    }

    /// The page to save for the next launch.
    var currentPage: PageAddress? {
        next.saved(showing: currentServerURL.flatMap(PageAddress.init))
    }

    /// Gives up the page's web view, which ends its WebContent process, and keeps the
    /// page to load again from the folder's server when the tab is shown.
    func discardPage() {
        guard !isDiscarded else { return }
        rememberPage()
        isDiscarded = true
        revealOnCommit = false
        let discarded = webView
        discarded.stopLoading()
        discarded.navigationDelegate = nil
        discarded.uiDelegate = nil
        discarded.onFileDrop = nil
        webView = Self.makeWebView(WebConfiguration.make(pagePrints: Self.pagePrints))
        wire(webView)
        container.replaceWebView(webView)
        if endpoint != nil { status.phase = .reloading }
        container.showsStatus = true
    }

    /// Loads the page again after `discardPage`: now if the server is ready, or when it is.
    private func revivePage() {
        guard isDiscarded else { return }
        isDiscarded = false
        if let endpoint { loadNextPage(from: endpoint) }
    }

    private func loadNextPage(from endpoint: ServerEndpoint) {
        let target = next.take().flatMap { $0.url(on: endpoint.origin) } ?? endpoint.entryURL
        load(target)
    }

    func load(_ url: URL) {
        revealOnCommit = true
        webView.load(URLRequest(url: url))
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
        if let page = currentServerURL.flatMap(PageAddress.init) { next.remember(shown: page) }
    }

    /// Names the window for everything that reads its title, and draws the visible one.
    /// The page's own `<title>` is not used: it is "Metabrowser" in every window.
    func showTitle(_ title: WindowTitle) {
        guard let window else { return }
        window.title = title.plain
        window.subtitle = title.subtitle
        window.representedURL = title.hasProxyIcon ? session?.root : nil
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
        textFinder.client = nil
        textFinder.findBarContainer = nil
        webView.stopLoading()
        webView.navigationDelegate = nil
        webView.uiDelegate = nil
        session?.windowClosed(self)
    }

    // MARK: - Menu actions (nil-targeted items reach the key window's controller)

    @objc func navigateBack(_ sender: Any?) { webView.goBack() }
    @objc func navigateForward(_ sender: Any?) { webView.goForward() }
    @objc func reloadPage(_ sender: Any?) { webView.reload() }
    @objc func actualSize(_ sender: Any?) { setZoom(1) }
    @objc func zoomIn(_ sender: Any?) { setZoom(webView.pageZoom * 1.1) }
    @objc func zoomOut(_ sender: Any?) { setZoom(webView.pageZoom / 1.1) }

    private func setZoom(_ zoom: Double) {
        webView.pageZoom = min(3, max(0.5, zoom))
        UserDefaults.standard.set(webView.pageZoom, forKey: Self.zoomKey)
    }

    @objc func printPage(_ sender: Any?) {
        guard let window else { return }
        let operation = webView.printOperation(with: NSPrintInfo.shared)
        operation.view?.frame = webView.bounds
        operation.runModal(for: window, delegate: nil, didRun: nil, contextInfo: nil)
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

    @objc func restartServer(_ sender: Any?) { session?.retry() }
    @objc func revealServerLog(_ sender: Any?) { session?.revealLog() }

    @objc func openInDefaultBrowser(_ sender: Any?) {
        if let url = currentServerURL { NSWorkspace.shared.open(url) }
    }

    func validateMenuItem(_ item: NSMenuItem) -> Bool {
        let showingPage = !container.showsStatus
        switch item.action {
        case #selector(navigateBack(_:)): return showingPage && webView.canGoBack
        case #selector(navigateForward(_:)): return showingPage && webView.canGoForward
        case #selector(reloadPage(_:)), #selector(printPage(_:)), #selector(actualSize(_:)),
             #selector(zoomIn(_:)), #selector(zoomOut(_:)):
            return showingPage
        case #selector(performFindAction(_:)):
            guard showingPage, let action = NSTextFinder.Action(rawValue: item.tag) else { return false }
            return textFinder.validateAction(action)
        case #selector(openInDefaultBrowser(_:)): return currentServerURL != nil
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
        let attachment = disposition?.lowercased().hasPrefix("attachment") ?? false
        decisionHandler(response.canShowMIMEType && !attachment ? .allow : .download)
    }

    func webView(_ webView: WKWebView, didCommit navigation: WKNavigation!) {
        session?.pageChanged()
        guard revealOnCommit else { return }
        revealOnCommit = false
        container.showsStatus = false
        window?.makeFirstResponder(webView)
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: any Error) {
        guard revealOnCommit, (error as NSError).code != NSURLErrorCancelled else { return }
        revealOnCommit = false
        status.phase = .failed(ServerFailure(
            summary: "The page did not load: \(error.localizedDescription)", recentOutput: []))
        container.showsStatus = true
    }

    /// WebContent crashed or was killed under memory pressure; never leave a blank window.
    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        guard contentRecoveries.allow() else {
            AppLog.app.error("web content process died repeatedly; showing the status view")
            status.phase = .failed(ServerFailure(
                summary: "The page stopped responding repeatedly. Retry restarts the folder's server.",
                recentOutput: []))
            container.showsStatus = true
            return
        }
        webView.reload()
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
            return session?.openChildWindow(configuration: configuration, besides: self)
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
        panel.beginSheetModal(for: window) { result in
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

    private func present(_ alert: NSAlert, completion: @escaping @MainActor (NSApplication.ModalResponse) -> Void) {
        guard let window else { return completion(alert.runModal()) }
        alert.beginSheetModal(for: window, completionHandler: completion)
    }
}
