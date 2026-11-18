import AppKit
import ShellCore
import WebKit

/// View on GitHub in a folder window (`GitHubView`): a native popover, anchored to the
/// page's View on GitHub button, with a web view of the item's page on github.com below a
/// one-line header of Back, Forward, the page's location, Copy Link, and Open in Browser.
///
/// The web view keeps what github.com stores in the one store every window's popover shares
/// (`GitHubDataStore`), so signing in once holds in every tab and window and after a
/// relaunch. Navigation follows `GitHubViewPolicy`: GitHub's own pages stay, and anything
/// else opens in the default browser. A file dropped on it goes to github.com, and its zoom
/// is its own (`WebConfiguration.makeGitHubWebView`).
///
/// The popover is transient: Escape, Command-W, or a click outside it closes it. Its web
/// view stays for `GitHubPopoverState.keptAfterClosing`, so opening it again for the same
/// item soon after shows it at once, as it was left, and is then let go with its WebContent
/// process; the window lets it go at once when the tab gives up its pages or closes.
///
/// While the popover has the keyboard, the main menu's actions reach this controller, in the
/// popover's responder chain, before the window behind it: Back, Forward, Reload Page,
/// zoom, and Open in Default Browser act on the popover, and Print and Find are off rather
/// than acting on the hidden page.
final class GitHubPopover: NSViewController, NSPopoverDelegate, NSMenuItemValidation {
    /// The header's height: one row of small controls, as in a toolbar's accessory bar.
    static let headerHeight: CGFloat = 30

    private let isInspectable: Bool
    private(set) var webView: WKWebView?
    private let popover = NSPopover()
    private var state = GitHubPopoverState()
    /// Reloads after the web content process dies, as a folder's page does.
    private var recoveries = RecoveryBudget.webContent
    private var observations: [NSKeyValueObservation] = []
    /// Lets the web view go once the popover has stayed closed for `keptAfterClosing`.
    private var release: Task<Void, Never>?
    private let page = NSView()
    private let back = GitHubPopover.button(symbol: "chevron.backward", label: "Back")
    private let forward = GitHubPopover.button(symbol: "chevron.forward", label: "Forward")
    private let location = NSTextField(labelWithString: "")
    private let copyLink = GitHubPopover.button(title: "Copy Link")
    private let openInBrowser = GitHubPopover.button(title: "Open in Browser")

    init(isInspectable: Bool) {
        self.isInspectable = isInspectable
        super.init(nibName: nil, bundle: nil)
        popover.contentViewController = self
        popover.behavior = .transient
        popover.delegate = self
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }

    override func loadView() {
        for (button, action) in [
            (back, #selector(navigateBack(_:))), (forward, #selector(navigateForward(_:))),
            (copyLink, #selector(copyLink(_:))), (openInBrowser, #selector(openInDefaultBrowser(_:))),
        ] {
            button.target = self
            button.action = action
        }
        location.font = .systemFont(ofSize: NSFont.smallSystemFontSize)
        location.textColor = .secondaryLabelColor
        location.lineBreakMode = .byTruncatingMiddle
        location.maximumNumberOfLines = 1
        location.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        location.setContentHuggingPriority(.defaultLow, for: .horizontal)

        let header = NSStackView(views: [back, forward, location, copyLink, openInBrowser])
        header.orientation = .horizontal
        header.spacing = 4
        header.edgeInsets = NSEdgeInsets(top: 0, left: 8, bottom: 0, right: 8)
        header.setCustomSpacing(8, after: forward)
        header.setCustomSpacing(8, after: location)
        let line = NSBox()
        line.boxType = .separator
        let root = NSView()
        for view in [header, line, page] as [NSView] {
            view.translatesAutoresizingMaskIntoConstraints = false
            root.addSubview(view)
        }
        NSLayoutConstraint.activate([
            header.topAnchor.constraint(equalTo: root.topAnchor),
            header.leadingAnchor.constraint(equalTo: root.leadingAnchor),
            header.trailingAnchor.constraint(equalTo: root.trailingAnchor),
            header.heightAnchor.constraint(equalToConstant: Self.headerHeight),
            line.topAnchor.constraint(equalTo: header.bottomAnchor),
            line.leadingAnchor.constraint(equalTo: root.leadingAnchor),
            line.trailingAnchor.constraint(equalTo: root.trailingAnchor),
            page.topAnchor.constraint(equalTo: line.bottomAnchor),
            page.leadingAnchor.constraint(equalTo: root.leadingAnchor),
            page.trailingAnchor.constraint(equalTo: root.trailingAnchor),
            page.bottomAnchor.constraint(equalTo: root.bottomAnchor),
        ])
        view = root
        showLocation()
        showHistory()
    }

    private static func button(symbol: String, label: String) -> NSButton {
        let image = NSImage(systemSymbolName: symbol, accessibilityDescription: label) ?? NSImage()
        let button = NSButton(image: image, target: nil, action: nil)
        button.bezelStyle = .accessoryBarAction
        button.controlSize = .small
        button.toolTip = label
        return button
    }

    private static func button(title: String) -> NSButton {
        let button = NSButton(title: title, target: nil, action: nil)
        button.bezelStyle = .accessoryBarAction
        button.controlSize = .small
        button.font = .systemFont(ofSize: NSFont.smallSystemFontSize)
        return button
    }

    // MARK: - Showing

    /// Opens the popover at `anchor` in `view`, the page's web view, on `page`, or as it was
    /// left when it was last opened for `page`. It takes most of the window, at least
    /// `GitHubPopoverLayout.minimumSize` where the screen allows, and opens below the
    /// button.
    func show(_ page: URL, at anchor: NSRect, of view: NSView) {
        loadViewIfNeeded()
        let webView = webView ?? makeWebView()
        if let load = state.open(page) { webView.load(URLRequest(url: load)) }
        let size = GitHubPopoverLayout.contentSize(
            window: view.window?.contentLayoutRect.size ?? view.bounds.size,
            screen: view.window?.screen?.visibleFrame.size)
        preferredContentSize = size
        popover.contentSize = size
        popover.show(relativeTo: anchor, of: view, preferredEdge: view.isFlipped ? .maxY : .minY)
        webView.window?.makeFirstResponder(webView)
    }

    func close() { popover.close() }

    /// After Metabrowser > Clear GitHub Data…: the page loads again, signed out.
    func reload() { webView?.reload() }

    /// Lets the web view go at once: the tab gave up its pages, or the window closes.
    func discard() {
        popover.close()
        dropWebView()
    }

    private func makeWebView() -> WKWebView {
        let webView = WebConfiguration.makeGitHubWebView(isInspectable: isInspectable)
        webView.navigationDelegate = self
        webView.uiDelegate = self
        webView.frame = page.bounds
        webView.autoresizingMask = [.width, .height]
        page.addSubview(webView)
        observations = [
            webView.observe(\.url) { [weak self] _, _ in MainActor.assumeIsolated { self?.showLocation() } },
            webView.observe(\.canGoBack) { [weak self] _, _ in MainActor.assumeIsolated { self?.showHistory() } },
            webView.observe(\.canGoForward) { [weak self] _, _ in MainActor.assumeIsolated { self?.showHistory() } },
        ]
        self.webView = webView
        return webView
    }

    private func dropWebView() {
        release?.cancel()
        release = nil
        guard let webView else { return }
        observations = []
        webView.stopLoading()
        webView.navigationDelegate = nil
        webView.uiDelegate = nil
        webView.removeFromSuperview()
        self.webView = nil
        state.discard()
        showLocation()
        showHistory()
    }

    func popoverWillShow(_ notification: Notification) {
        release?.cancel()
        release = nil
    }

    func popoverDidClose(_ notification: Notification) {
        release?.cancel()
        release = Task { [weak self] in
            try? await Task.sleep(for: GitHubPopoverState.keptAfterClosing)
            guard !Task.isCancelled, let self, !popover.isShown else { return }
            dropWebView()
        }
    }

    /// The page the popover shows, for Copy Link and Open in Browser: the web view's, while
    /// it is one of GitHub's, or else the one it was opened for.
    private var shownPage: URL? {
        if let url = webView?.url, GitHubViewPolicy.staysInView(url) { return url }
        return state.openedFor
    }

    private func showLocation() {
        location.stringValue = GitHubView.location(webView?.url ?? state.openedFor)
        location.toolTip = webView?.url?.absoluteString
    }

    private func showHistory() {
        back.isEnabled = webView?.canGoBack ?? false
        forward.isEnabled = webView?.canGoForward ?? false
    }

    private func showFailure(_ error: any Error) {
        location.stringValue = "The page did not load: \(error.localizedDescription)"
    }

    // MARK: - Actions, from the header or the main menu

    @objc func navigateBack(_ sender: Any?) { webView?.goBack() }
    @objc func navigateForward(_ sender: Any?) { webView?.goForward() }
    @objc func reloadPage(_ sender: Any?) { webView?.reload() }

    // github.com at its own zoom, apart from the pages' remembered one and never saved.
    @objc func actualSize(_ sender: Any?) { webView?.pageZoom = 1 }
    @objc func zoomIn(_ sender: Any?) { webView.map { $0.pageZoom = PageZoom.zoomedIn($0.pageZoom) } }
    @objc func zoomOut(_ sender: Any?) { webView.map { $0.pageZoom = PageZoom.zoomedOut($0.pageZoom) } }

    /// Off while the popover has the keyboard (`validateMenuItem`), so neither prints nor
    /// searches the page hidden behind it.
    @objc func printPage(_ sender: Any?) {}
    @objc func performFindAction(_ sender: Any?) {}

    /// The header's Open in Browser, or File > Open in Default Browser: the page the popover
    /// shows, in the default browser, and the popover closes.
    @objc func openInDefaultBrowser(_ sender: Any?) {
        guard let page = shownPage else { return NSSound.beep() }
        NSWorkspace.shared.open(page)
        popover.performClose(sender)
    }

    /// The header's Copy Link: the page the popover shows, as a URL and as text.
    @objc func copyLink(_ sender: Any?) {
        guard let page = shownPage else { return NSSound.beep() }
        let board = NSPasteboard.general
        board.clearContents()
        board.writeObjects([page as NSURL])
        board.setString(page.absoluteString, forType: .string)
    }

    /// Command-W closes the popover, not the window behind it.
    @objc func performClose(_ sender: Any?) { popover.performClose(sender) }

    override func cancelOperation(_ sender: Any?) { popover.performClose(sender) }

    func validateMenuItem(_ item: NSMenuItem) -> Bool {
        switch item.action {
        case #selector(navigateBack(_:)): webView?.canGoBack ?? false
        case #selector(navigateForward(_:)): webView?.canGoForward ?? false
        case #selector(reloadPage(_:)), #selector(actualSize(_:)), #selector(zoomIn(_:)), #selector(zoomOut(_:)):
            webView != nil
        case #selector(openInDefaultBrowser(_:)), #selector(copyLink(_:)): shownPage != nil
        case #selector(printPage(_:)), #selector(performFindAction(_:)): false
        default: true
        }
    }
}

extension GitHubPopover: WKNavigationDelegate, WKUIDelegate {
    func webView(
        _ webView: WKWebView, decidePolicyFor action: WKNavigationAction,
        decisionHandler: @escaping @MainActor (WKNavigationActionPolicy) -> Void
    ) {
        let linkClick = action.navigationType == .linkActivated
        let decision = GitHubViewPolicy.decide(
            action.request.url, isMainFrame: action.targetFrame?.isMainFrame ?? true,
            byUser: [.linkActivated, .formSubmitted, .formResubmitted].contains(action.navigationType),
            shouldDownload: action.shouldPerformDownload,
            wantsNewWindow: linkClick && action.modifierFlags.contains(.command))
        decisionHandler(follow(decision) ? .allow : .cancel)
    }

    func webView(
        _ webView: WKWebView, decidePolicyFor response: WKNavigationResponse,
        decisionHandler: @escaping @MainActor (WKNavigationResponsePolicy) -> Void
    ) {
        guard response.isForMainFrame else { return decisionHandler(.allow) }
        let disposition = (response.response as? HTTPURLResponse)?.value(forHTTPHeaderField: "Content-Disposition")
        let decision = GitHubViewPolicy.decideResponse(
            response.response.url,
            ResponsePolicy.decide(canShowMIMEType: response.canShowMIMEType, contentDisposition: disposition))
        decisionHandler(follow(decision) ? .allow : .cancel)
    }

    /// Carries out `decision`, and says whether WebKit goes on with the load.
    private func follow(_ decision: NavigationDecision) -> Bool {
        switch decision {
        case .allow: return true
        case .openExternally(let url):
            NSWorkspace.shared.open(url)
            return false
        case .download, .openInNewWindow, .cancel: return false
        }
    }

    func webView(_ webView: WKWebView, didCommit navigation: WKNavigation!) {
        showLocation()  // in place of a failure the header showed
    }

    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: any Error) {
        // A load the policy stopped, or one superseded by the next, is no failure.
        let error = error as NSError
        if error.domain == NSURLErrorDomain, error.code != NSURLErrorCancelled { showFailure(error) }
    }

    func webViewWebContentProcessDidTerminate(_ webView: WKWebView) {
        if recoveries.allow() { webView.reload() }
    }

    /// `target=_blank` to a GitHub page loads here, in place; anything else on the web opens
    /// in the default browser.
    func webView(
        _ webView: WKWebView, createWebViewWith configuration: WKWebViewConfiguration,
        for action: WKNavigationAction, windowFeatures: WKWindowFeatures
    ) -> WKWebView? {
        switch GitHubViewPolicy.decideNewWindow(action.request.url) {
        case .allow: webView.load(action.request)
        case .openExternally(let url): NSWorkspace.shared.open(url)
        case .download, .openInNewWindow, .cancel: break
        }
        return nil
    }
}
