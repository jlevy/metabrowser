import AppKit
import ShellCore
import WebKit

/// One opened folder or GitHub repository (`SessionRoot`): one server, and the windows
/// that show it.
///
/// The first window opens before the server starts and shows its progress; windows the
/// page opens (`target=_blank`, Command-click) join it as tabs. When the last window
/// closes, the server stops: a folder nobody is looking at keeps no process running.
/// A restored folder's windows open before its server starts, which `FolderWindows`
/// schedules.
final class FolderSession: ManagedServer {
    /// What the session serves, which keys it.
    let served: SessionRoot
    /// The folder's file URL, or the repository's canonical URL.
    var root: URL { served.url }
    /// The folder's log, which each launch claims before it spawns, so another running
    /// copy of the app serving the folder too writes a log of its own.
    private let log: FolderLog
    var logURL: URL { log.url }
    /// The supervisor, behind the gate every start and restart passes.
    private let server: FolderServer
    private var supervisor: ServerSupervisor { server.supervisor }
    private(set) var windows: [BrowserWindowController] = []
    private var endpoint: ServerEndpoint?
    private var failure: ServerFailure?
    /// What every window of the folder calls itself: from the folder's path until the
    /// server answers `/api/identity`.
    private(set) var title: WindowTitle
    /// Every window's `window.title`: the short name, or the full name while another open
    /// folder shares the short name, which the app delegate decides across folders
    /// (`WindowTitle.windowTitles`).
    var windowTitle: String {
        didSet { if windowTitle != oldValue { windows.forEach { $0.showTitle(title, windowTitle: windowTitle) } } }
    }
    private var identityRequest: Task<Void, Never>?
    /// What the server is started with: the folder, or the repository link `open(link:)`
    /// gave last, and the link that waits for a start under way (`RepositoryLinks`). Every
    /// start, Retry, and Restart Server reads the target as it builds its command.
    private let target: StartTarget
    /// Retries and restarts asked for and not yet carried out, which a link into a ready
    /// repository counts as a start on the target (`RepositoryLinks.receive`).
    private var restartsInFlight = 0
    /// The window a link restarted the server for, which says that it waits while the old
    /// server serves the other tabs.
    private weak var linkWindow: BrowserWindowController?
    /// Asks the ready server whether it found what the link it started on names.
    private var selectionWatch: Task<Void, Never>?
    /// Whether the start waits for another repository's, which the status view says.
    private var isWaitingAtGate = false
    /// The folder's title changed, so every open folder's window title may change.
    var onTitleChange: ((FolderSession) -> Void)?
    var onAllWindowsClosed: ((FolderSession) -> Void)?
    /// A window became key, which is how a tab is selected.
    var onWindowShown: ((FolderSession, BrowserWindowController) -> Void)?
    /// A window opened or closed, or a page changed: what the saved session records.
    var onLayoutChange: (() -> Void)?
    /// A start or restart is waiting for a runtime the app accepts.
    var onWaitingForRuntime: (() -> Void)?
    /// A restart or a resumed start of a restored background folder was refused by its
    /// root check: it now waits for one of its tabs to be selected (`FolderWindows`).
    var onRootRefused: ((FolderSession) -> Void)?
    /// A repository's server could not find what the link it started on names, and serves
    /// another revision (`LinkSelection`).
    var onLinkSelectionMissing: ((FolderSession, URL, LinkSelection.Outcome) -> Void)?

    /// `accepted` is the runtime a server may start from at the moment it would start,
    /// which every start, Retry, and Restart Server ask, not `setup`.
    ///
    /// - Parameter link: for a repository, what its server is started with: the canonical
    ///   link it was opened with (`PresentPlan.link`), so `metab` pins what the link selects
    ///   and reads a pull request it names, as `metab LINK` in Terminal does. Nil serves the
    ///   root itself.
    init(
        root served: SessionRoot, link: URL? = nil, setup: RuntimeSetup, gate: LaunchGate,
        accepted: @escaping () -> RuntimeSetup?
    ) {
        self.served = served
        let root = served.url
        title = WindowTitle(served.identity())
        windowTitle = title.text
        let log = FolderLog(root: root, directory: appIdentity.logsDirectory())
        self.log = log
        let launch = CLIServeLaunch(basePort: served.lane.basePort)
        let target = StartTarget(RepositoryLinks(target: link ?? root))
        self.target = target
        let spec = { (setup: RuntimeSetup) in
            launch.spec(serving: target.url, with: setup, inherited: ProcessInfo.processInfo.environment, logURL: log.url)
        }
        // Each launch claims and prepares the log first, so a log that cannot be claimed or
        // kept fails the launch, the window says why, and Retry tries again.
        let supervisor = ServerSupervisor(
            spec: spec(setup), launch: launch, policy: .serving(served), gate: gate, makeProcess: log.processFactory())
        server = FolderServer(supervisor: supervisor, accepted: accepted, spec: spec)
        let name = root.lastPathComponent
        supervisor.onEvent = { message in
            AppLog.server.info("\(name, privacy: .public): \(message, privacy: .public)")
            do {
                try ServerLog.append(message, to: log.url)
            } catch {
                // The event itself is in the unified log, on the line above.
                AppLog.server.error("\(name, privacy: .public): \(String(describing: error), privacy: .public)")
            }
        }
        supervisor.onChange = { [weak self] state in self?.serverChanged(state) }
        // A folder waits a moment at its gate; a repository can wait out another's first clone.
        if !served.isLocal {
            supervisor.onGateWait = { [weak self] waiting in
                guard let self else { return }
                isWaitingAtGate = waiting
                // A restart on a link waits while the old server serves: the link's window
                // stops showing the old revision and says it waits; the other tabs serve on.
                if waiting, case .ready = self.supervisor.state { linkWindow?.showStarting() }
                windows.forEach { $0.showWaitingAtGate(waiting) }
            }
        }
    }

    /// The folder's name as Finder shows it, or the repository's.
    var folderName: String {
        switch served {
        case .folder(let url): FileManager.default.displayName(atPath: url.path(percentEncoded: false))
        case .repository: served.identity().shortName
        }
    }

    /// Where the status view says the session is: the folder's path with `~` for home, or
    /// `github.com/<owner>/<repo>`.
    var location: String {
        switch served {
        case .folder(let url): (url.path(percentEncoded: false) as NSString).abbreviatingWithTildeInPath
        case .repository: served.identity().fullName
        }
    }

    /// Whether the session serves a folder on this Mac. Only a folder is a root that a file
    /// opens in (`OpenTarget`), a recent folder, or a tab of the saved session.
    var isLocal: Bool { served.isLocal }

    /// The folder's canonical path without a trailing slash, as `OpenTarget` and the saved
    /// session name it; for a repository, its key, which is no path, so no restore names it.
    var path: String { isLocal ? FolderSession.path(of: root) : served.key }

    static func path(of root: URL) -> String {
        var path = root.path(percentEncoded: false)
        while path.count > 1, path.hasSuffix("/") { path.removeLast() }
        return path
    }

    /// Every server child not yet reaped; each pid is also its process group.
    var childPIDs: [pid_t] { supervisor.childPIDs }

    /// The runtime the server last spawned from, which an upgrade compares with; nil for
    /// a folder whose server has not spawned, such as a restored one waiting for its tab.
    var startedRuntime: Runtime? { server.startedRuntime }

    /// Whether a start or restart the user asked for is waiting for a runtime the app
    /// accepts. A restore's start waits in its queue instead.
    var isWaitingForRuntime: Bool { server.held != nil }

    /// Whether a runtime is accepted now.
    var isRuntimeAccepted: Bool { server.isRuntimeAccepted }

    /// A folder the user opened: starts its server from the runtime accepted when it
    /// spawns, unless one is starting, running, or stopping, and returns once that start
    /// is ready or has failed. Without an accepted runtime the windows say so, and the
    /// start waits for `resume()`.
    func startServer() async {
        settle(await server.start())
    }

    /// A restored folder's turn (`FolderWindows`): the same start, which waits in the
    /// restore's queue rather than here when there is no runtime, so it is admitted again
    /// and keeps its place.
    func startRestored() async -> FolderServer.Outcome {
        let outcome = await server.start(holding: false)
        if outcome == .waitingForRuntime { waitForRuntime() }
        return outcome
    }

    /// For a restored folder, the root check made just before its server would spawn,
    /// after the launch gate and beside the runtime check (`FolderServer`, `RestoreRun`):
    /// a background one's admission, and once one of its tabs is selected, that its
    /// saved path still names its own folder.
    var launchCheck: (() -> Bool)? {
        get { server.rootCheck }
        set { server.rootCheck = newValue }
    }

    /// Retry and Restart Server: a fresh server from the runtime accepted now, which may
    /// not be the one this folder started with. Without one, nothing is stopped, and the
    /// restart waits for `resume()`.
    func retry() {
        restartsInFlight += 1
        Task {
            settle(await server.restart())
            restartsInFlight -= 1
        }
    }

    /// Carries out a start or restart that waited for a runtime, now that one is accepted.
    func resume() async {
        if let outcome = await server.resume() { settle(outcome) }
    }

    /// What the windows show, and who is told, after a start or restart that did not spawn.
    private func settle(_ outcome: FolderServer.Outcome) {
        switch outcome {
        case .launched: break
        case .waitingForRuntime: waitForRuntime()
        case .refusedByRoot:
            AppLog.app.info(
                "\(self.root.lastPathComponent, privacy: .public) changed since it was restored; it starts when its tab is selected")
            windows.forEach { $0.showWaitingForSelection() }
            onRootRefused?(self)
        }
    }

    private func waitForRuntime() {
        AppLog.app.info("\(self.root.lastPathComponent, privacy: .public): waiting for a metab Metabrowser can run")
        switch supervisor.state {
        case .ready, .starting, .stopping: break  // a running server keeps running
        case .stopped, .failed: windows.forEach { $0.showWaitingForRuntime() }
        }
        onWaitingForRuntime?()
    }

    func shutDown() async {
        identityRequest?.cancel()
        selectionWatch?.cancel()
        target.links.shutDown()  // a link held for a start under way starts nothing now
        await supervisor.shutDown()
    }

    /// Brings the folder's front window forward, showing `page` in it if one is given,
    /// and checks that its server still answers: a hung one is stopped, and its windows
    /// say so and offer Retry.
    func showFrontWindow(page: PageAddress? = nil) {
        let front = frontWindow
        if let page, let front {
            front.show(page)  // which checks before it loads
        } else {
            Task { _ = await checkHealth() }
        }
        front?.window?.makeKeyAndOrderFront(nil)
    }

    /// The window a link or a reopen brings forward: the first one on screen.
    private var frontWindow: BrowserWindowController? {
        windows.first { $0.window?.isVisible == true } ?? windows.first
    }

    /// A link into this repository, which its front window is to show: the server starts
    /// again on `link` (`PresentPlan.link`), and the window loads its entry page.
    ///
    /// The window may show another branch, commit, or pull request's head than `link`
    /// names, and the app cannot tell which, since only the mirror knows where a link's
    /// ref ends; so it never only navigates, which would show the link's page at the
    /// window's pin. The server resolves `link` as a first start does, pins what it names,
    /// and announces its page. A start under way, such as a first clone, runs to its end
    /// first, and the server then starts again on the newest link, from the cache; a link
    /// that start already runs on changes nothing (`RepositoryLinks`).
    func open(link: URL) {
        frontWindow?.window?.makeKeyAndOrderFront(nil)
        let name = root.lastPathComponent
        switch target.links.receive(link, state: supervisor.state, restarting: restartsInFlight > 0) {
        case .restart:
            restart()
        case .hold:
            AppLog.app.info("\(name, privacy: .public): a link waits for the start under way to end")
        case .none:
            AppLog.app.info("\(name, privacy: .public): its server is starting on that link already")
        }
    }

    /// Starts the server again on `target`, which a link just set: the front window loads
    /// the new server's entry page, and until then shows no page from the old one.
    private func restart() {
        selectionWatch?.cancel()
        linkWindow = frontWindow
        linkWindow?.showEntryPage()
        AppLog.app.info("\(self.root.lastPathComponent, privacy: .public): starting its server again on a link it was sent")
        retry()
    }

    /// Whether the server still answers, asked before a window joins it
    /// (`ServerSupervisor.checkHealth`).
    func checkHealth() async -> HealthCheck {
        await supervisor.checkHealth()
    }

    func revealLog() {
        NSWorkspace.shared.activateFileViewerSelecting([logURL])
    }

    /// Command-click on a link to this folder's server. The new tab holds the page before
    /// the health check runs, so a server that fails the check, and comes back with Retry,
    /// still shows it.
    func openWindow(at url: URL, besides parent: BrowserWindowController) {
        let page = PageAddress(url)
        let controller = makeWindow(page: page)
        addTab(controller, besides: parent)
        if let page { controller.show(page) }
    }

    /// `target=_blank` and `window.open`: WebKit loads the request into the view returned,
    /// at once, so it cannot wait for a health check; the page asking for it was just
    /// served.
    func openChildWindow(configuration: WKWebViewConfiguration, besides parent: BrowserWindowController) -> WKWebView {
        let controller = makeWindow(configuration: configuration)
        addTab(controller, besides: parent)
        return controller.webView
    }

    func windowClosed(_ controller: BrowserWindowController) {
        windows.removeAll { $0 === controller }
        if windows.isEmpty { onAllWindowsClosed?(self) }
        onLayoutChange?()
    }

    func windowShown(_ controller: BrowserWindowController) {
        onWindowShown?(self, controller)
    }

    func pageChanged() {
        onLayoutChange?()
    }

    /// A window not yet shown. It loads `page`, or the entry page, once the server is
    /// ready, and a `discarded` one only once it is shown.
    func makeWindow(
        configuration: WKWebViewConfiguration? = nil, page: PageAddress? = nil, discarded: Bool = false
    ) -> BrowserWindowController {
        let controller = BrowserWindowController(
            session: self, configuration: configuration, page: page, discarded: discarded)
        windows.append(controller)
        defer { onLayoutChange?() }
        controller.adoptServer(endpoint)
        if let failure { controller.showFailure(failure) }
        if isWaitingForRuntime, endpoint == nil { controller.showWaitingForRuntime() }
        if isWaitingAtGate { controller.showWaitingAtGate(true) }
        return controller
    }

    private func addTab(_ controller: BrowserWindowController, besides parent: BrowserWindowController) {
        guard let window = controller.window else { return }
        parent.window?.addTabbedWindow(window, ordered: .above)
        window.makeKeyAndOrderFront(nil)
    }

    private func serverChanged(_ state: ServerState) {
        selectionWatch?.cancel()
        // A link sent while a start was under way: that start has ended, so the server
        // starts again on the link before any window loads from the one that ended.
        switch state {
        case .ready, .failed, .stopped:
            if target.links.startEnded() != nil {
                endpoint = nil
                return restart()
            }
        case .starting, .stopping:
            break
        }
        switch state {
        case .starting:
            endpoint = nil
            failure = nil
            windows.forEach { $0.showStarting() }
        case .ready(let ready):
            endpoint = ready
            failure = nil
            linkWindow = nil
            let authorization = supervisor.launch.authorization(for: ready)
            windows.forEach { $0.attach(ready, authorization: authorization) }
            requestIdentity(from: ready, authorization: authorization)
            if !served.isLocal { watchSelection(of: ready, authorization: authorization) }
        case .failed(let failed):
            endpoint = nil
            failure = failed
            windows.forEach { $0.showFailure(failed) }
        case .stopping, .stopped:
            break
        }
    }

    /// Asks the ready repository server whether it found what its link names, for as
    /// long as its fetch for it runs, and tells the app delegate when it did not, since
    /// the windows then show another revision (`LinkSelection`). An answer from a server
    /// that has since restarted is dropped.
    private func watchSelection(of ready: ServerEndpoint, authorization: WebAuthorization) {
        let link = target.url
        selectionWatch = Task { [weak self] in
            let outcome = await LinkSelection.watch(origin: ready.origin, authorization: authorization)
            guard !Task.isCancelled, let self, self.endpoint == ready else { return }
            switch outcome {
            case .shown:
                break
            case .notFound, .fetchFailed:
                AppLog.app.info("\(self.root.lastPathComponent, privacy: .public): its server serves another revision than its link names")
                onLinkSelectionMissing?(self, link, outcome)
            case .unknown(let reason):
                AppLog.app.info("\(self.root.lastPathComponent, privacy: .public): not told what its link selects: \(reason, privacy: .public)")
            }
        }
    }

    /// Asks the ready server which folder it serves and retitles every window. An
    /// answer from a server that has since restarted is dropped.
    private func requestIdentity(from ready: ServerEndpoint, authorization: WebAuthorization) {
        identityRequest?.cancel()
        identityRequest = Task { [weak self] in
            let answer = await IdentityClient.fetch(origin: ready.origin, authorization: authorization)
            guard !Task.isCancelled, let self, self.endpoint == ready else { return }
            self.adopt(answer)
        }
    }

    private func adopt(_ answer: IdentityAnswer) {
        let next = WindowTitle(answer.identity(or: served.identity()))
        let name = root.lastPathComponent
        let titled = "\(name): titled \"\(next.text)\""
        switch answer {
        case .identity:
            AppLog.app.info("\(titled, privacy: .public) from /api/identity")
        case .failed(let reason):
            AppLog.app.error(
                "\(titled, privacy: .public) from the folder's path: /api/identity failed, \(reason, privacy: .public)")
        }
        guard next != title else { return }
        title = next
        // The app delegate retitles every open folder's windows, since this one's short name
        // may now be shared or no longer shared.
        if let onTitleChange { onTitleChange(self) } else { windowTitle = next.text }
        windows.forEach { $0.showTitle(next, windowTitle: windowTitle) }
    }
}

/// What a session's server is started with, which its command reads at each start, and
/// which a link into the repository replaces (`FolderSession.open(link:)`).
private final class StartTarget {
    var links: RepositoryLinks
    var url: URL { links.target }

    init(_ links: RepositoryLinks) {
        self.links = links
    }
}
