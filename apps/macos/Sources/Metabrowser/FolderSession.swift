import AppKit
import ShellCore
import WebKit

/// One opened folder or GitHub repository (`SessionRoot`): one server, and its pages
/// (`FolderPage`), each shown in a window or, for a folder open in the background, in
/// none (`OpenFolders`).
///
/// The first page opens before the server starts and shows its progress; pages the page
/// opens (`target=_blank`, Command-click) join it as tabs. When the last page closes, the
/// server stops: a closed folder keeps no process running, while a folder in the
/// background keeps its server for a switch back. A restored folder's pages open before
/// its server starts, which `FolderWindows` schedules.
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
    /// The folder's pages, in the order they opened.
    private(set) var pages: [FolderPage] = []
    /// The windows showing the folder's pages.
    var windows: [BrowserWindowController] { pages.compactMap(\.host) }
    /// Whether the folder is open in the background: it has a page, and no window shows
    /// any of its pages (`OpenFolders`).
    var isInBackground: Bool { !pages.isEmpty && pages.allSatisfy { $0.host == nil } }
    /// The folder's page in the background, which a window switching to the folder shows.
    var backgroundPage: FolderPage? { pages.first { $0.host == nil } }
    private var endpoint: ServerEndpoint?
    private var failure: ServerFailure?
    /// What every window of the folder calls itself: from the folder's path until the
    /// server answers `/api/identity`.
    private(set) var title: WindowTitle
    /// Every window's `window.title`: the short name, or the full name while another open
    /// folder shares the short name, which the app delegate decides across folders
    /// (`WindowTitle.windowTitles`).
    var windowTitle: String {
        didSet { if windowTitle != oldValue { showTitleInWindows() } }
    }
    private var identityRequest: Task<Void, Never>?
    /// The link into the repository that waits for its server to be ready
    /// (`RepositoryLinks`). The server itself is always started on the root.
    private var links: RepositoryLinks
    /// Retries and restarts asked for and not yet carried out, which a link into a ready
    /// repository waits for (`RepositoryLinks.receive`).
    private var restartsInFlight = 0
    /// Whether the start waits for another repository's, which the status view says, and
    /// the windows that asked for a restart, which say so while the old server serves the
    /// other tabs.
    private var restartWait = RestartWait<FolderPage>()
    /// Asks the ready server to open a link into the repository (`SourceLink`).
    private var linkRequest: Task<Void, Never>?
    /// The folder's title changed, so every open folder's window title may change.
    var onTitleChange: ((FolderSession) -> Void)?
    /// The folder's last page closed, shown or in the background: the folder closes.
    var onAllPagesClosed: ((FolderSession) -> Void)?
    /// A window showing one of the folder's pages became key, which is how a tab is
    /// selected.
    var onWindowShown: ((FolderSession, BrowserWindowController) -> Void)?
    /// A window opened or closed, or a page changed: what the saved session records.
    var onLayoutChange: (() -> Void)?
    /// A start or restart is waiting for a runtime the app accepts.
    var onWaitingForRuntime: (() -> Void)?
    /// A page of the folder's needs a window of its own, placed as a newly opened folder's
    /// is: a folder in the background was opened again, or a link brought it forward.
    var onPlaceWindow: ((BrowserWindowController) -> Void)?
    /// A restart or a resumed start of a restored background folder was refused by its
    /// root check: it now waits for one of its tabs to be selected (`FolderWindows`).
    var onRootRefused: ((FolderSession) -> Void)?
    /// A repository's mirror has nothing a link into it names, even after a refresh: the
    /// window stays where it was (`SourceLink`).
    var onLinkNotFound: ((FolderSession, URL, SourceLink.Outcome) -> Void)?

    /// `accepted` is the runtime a server may start from at the moment it would start,
    /// which every start, Retry, and Restart Server ask, not `setup`.
    ///
    /// - Parameter link: for a repository, the canonical link it was opened with
    ///   (`PresentPlan.link`), which its first ready server opens (`SourceLink`). The
    ///   server is started on the repository itself whatever the link, so one mirror
    ///   serves every link into the repository. Nil, or the repository's own URL, opens
    ///   the entry page.
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
        links = RepositoryLinks(waiting: link.flatMap { $0.absoluteString == root.absoluteString ? nil : $0 })
        let spec = { (setup: RuntimeSetup) in
            launch.spec(serving: root, with: setup, inherited: ProcessInfo.processInfo.environment, logURL: log.url)
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
        supervisor.onStartProgress = { [weak self] progress in
            self?.pages.forEach { $0.showStartProgress(progress) }
        }
        // A folder waits a moment at its gate; a repository can wait out another's first clone.
        if !served.isLocal {
            supervisor.onGateWait = { [weak self] waiting in
                guard let self else { return }
                // A restart of the ready server waits while it serves: the window that
                // asked stops showing the old page and says it waits; the other tabs serve on.
                restartWait.gateWait(waiting, state: self.supervisor.state).forEach { $0.showStarting() }
                pages.forEach { $0.showWaitingAtGate(waiting) }
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

    /// The session's one key (`SessionRoot.key`), which every lookup of an open folder
    /// uses: the folder's canonical path without a trailing slash, as `OpenTarget` and the
    /// saved session name it, or the repository's URL, which is no path, so no restore
    /// names it.
    var path: String { served.key }

    static func path(of root: URL) -> String {
        SessionRoot.folder(root).key
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
    /// is ready or has failed. That server records the folder as a recent target, which no
    /// other start does (`FolderServer.start`): not a restored folder's, a reload's, a
    /// retry's, or a restart's. Without an accepted runtime the windows say so, and the
    /// start waits for `resume()`.
    func startServer() async {
        settle(await server.start(recordsOpen: true))
    }

    /// Command-R in a window whose server has not started, such as a restored folder's
    /// still waiting its turn: the same start, joined if one is under way, but not an
    /// open, so it records nothing.
    func startForReload() async {
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
    ///
    /// - Parameter page: the page it was asked from, which says it waits while the restart
    ///   of a ready server waits at the launch gate (`RestartWait`); nil, as for the
    ///   restart an upgrade offers, is the front window's.
    func retry(from page: FolderPage? = nil) {
        restartWait.asked(from: page ?? frontPage, state: supervisor.state)?.showStarting()
        restartsInFlight += 1
        Task {
            settle(await server.restart())
            restartsInFlight -= 1
        }
    }

    /// The app became active, most likely back from Terminal: a server whose start failed
    /// in a way a sign-in there can fix starts again, as Retry does, so that the sign-in
    /// clears the windows' failure (`ServerFailure.rechecksOnActivation`).
    /// Any other session, other GitHub failures among them, is left as it is.
    func recheckAfterActivation() {
        guard case .failed = supervisor.state, let failure, failure.rechecksOnActivation else { return }
        let state = failure.gitHub?.state ?? ""
        AppLog.app.info(
            "\(self.root.lastPathComponent, privacy: .public): starting again on activation after \(state, privacy: .public)")
        retry()
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
            pages.forEach { $0.showWaitingForSelection() }
            onRootRefused?(self)
        }
    }

    private func waitForRuntime() {
        AppLog.app.info("\(self.root.lastPathComponent, privacy: .public): waiting for a metab Metabrowser can run")
        switch supervisor.state {
        case .ready, .starting, .stopping: break  // a running server keeps running
        case .stopped, .failed: pages.forEach { $0.showWaitingForRuntime() }
        }
        onWaitingForRuntime?()
    }

    func shutDown() async {
        identityRequest?.cancel()
        linkRequest?.cancel()
        links.shutDown()  // a link held for a start under way opens nothing now
        await supervisor.shutDown()
    }

    /// Brings the folder's front window forward, showing `page` in it if one is given,
    /// and checks that its server still answers: a hung one is stopped, and its windows
    /// say so and offer Retry.
    func showFrontWindow(page address: PageAddress? = nil) {
        let front = frontPage
        if let address, let front {
            front.show(address)  // which checks before it loads
        } else {
            Task { _ = await checkHealth() }
        }
        bringForward(front)
    }

    /// Brings forward the window showing `page`, or places it in a window of its own if
    /// none does, as for a folder in the background.
    private func bringForward(_ page: FolderPage?) {
        guard let page else { return }
        if let window = page.host?.window {
            window.makeKeyAndOrderFront(nil)
        } else {
            onPlaceWindow?(BrowserWindowController(page: page))
        }
    }

    /// The page a link or a reopen brings forward: the first one a window on screen shows.
    private var frontPage: FolderPage? {
        pages.first { $0.host?.window?.isVisible == true } ?? pages.first
    }

    /// A link into this repository, which its front window is to show. The ready server
    /// opens it (`SourceLink`): it starts a refresh of the mirror and says where the
    /// window goes, switching its pin first when the link names another revision, so the
    /// window never shows the link's page at another revision than the link's. A start
    /// under way, such as a first clone, or a restart waiting to replace the server, runs
    /// to its end first, and the newest link sent meanwhile opens then; a failed or
    /// stopped server starts again, and the link opens once it is ready
    /// (`RepositoryLinks`).
    func open(link: URL) {
        bringForward(frontPage)
        let name = root.lastPathComponent
        switch links.receive(link, state: supervisor.state, restarting: restartsInFlight > 0) {
        case .open:
            if let endpoint { request(link, from: endpoint) }
        case .hold:
            AppLog.app.info("\(name, privacy: .public): a link waits for the start under way to end")
        case .start:
            AppLog.app.info("\(name, privacy: .public): starting its server again for a link it was sent")
            retry(from: frontPage)
        case .none:
            AppLog.app.info("\(name, privacy: .public): a link into a closed session opens nothing")
        }
    }

    /// Asks the ready server to open `link`, and shows the page it names in the front
    /// window. An answer from a server that has since restarted, or for a link a newer one
    /// replaced, is dropped.
    private func request(_ link: URL, from ready: ServerEndpoint) {
        linkRequest?.cancel()
        let authorization = supervisor.launch.authorization(for: ready)
        linkRequest = Task { [weak self] in
            let outcome = await SourceLink.open(link, origin: ready.origin, authorization: authorization)
            guard !Task.isCancelled, let self, self.endpoint == ready else { return }
            let name = self.root.lastPathComponent
            switch outcome {
            case .page(let address):
                AppLog.app.info("\(name, privacy: .public): a link opens at its page")
                self.frontPage?.show(address)
            case .notFound(let code):
                AppLog.app.info("\(name, privacy: .public): the mirror has nothing a link names (\(code, privacy: .public))")
                self.onLinkNotFound?(self, link, outcome)
            case .unknown(let reason):
                AppLog.app.error("\(name, privacy: .public): a link was not opened: \(reason, privacy: .public)")
            }
        }
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
    func openWindow(at url: URL, besides parent: FolderPage) {
        let address = PageAddress(url)
        let controller = makeWindow(page: address)
        addTab(controller, besides: parent)
        if let address { controller.page.show(address) }
    }

    /// `target=_blank` and `window.open`: WebKit loads the request into the view returned,
    /// at once, so it cannot wait for a health check; the page asking for it was just
    /// served.
    func openChildWindow(configuration: WKWebViewConfiguration, besides parent: FolderPage) -> WKWebView {
        let controller = makeWindow(configuration: configuration)
        addTab(controller, besides: parent)
        return controller.page.webView
    }

    /// One of the folder's pages is gone for good (`FolderPage.close`).
    func pageClosed(_ page: FolderPage) {
        pages.removeAll { $0 === page }
        if pages.isEmpty { onAllPagesClosed?(self) }
        onLayoutChange?()
    }

    /// A window showing `page` became key, or began to show it.
    func pageShown(_ page: FolderPage) {
        guard let controller = page.host else { return }
        onWindowShown?(self, controller)
    }

    func pageChanged() {
        onLayoutChange?()
    }

    /// A page not yet shown, in a window of its own not yet ordered in. It loads `page`, or
    /// the entry page, once the server is ready, and a `discarded` one only once it is
    /// shown.
    func makeWindow(
        configuration: WKWebViewConfiguration? = nil, page address: PageAddress? = nil, discarded: Bool = false
    ) -> BrowserWindowController {
        BrowserWindowController(page: makePage(configuration: configuration, page: address, discarded: discarded))
    }

    /// A page of the folder's, which no window shows yet.
    func makePage(
        configuration: WKWebViewConfiguration? = nil, page address: PageAddress? = nil, discarded: Bool = false
    ) -> FolderPage {
        let page = FolderPage(session: self, configuration: configuration, page: address, discarded: discarded)
        pages.append(page)
        defer { onLayoutChange?() }
        page.adoptServer(endpoint)
        page.showStartProgress(supervisor.startProgress)
        if let failure { page.showFailure(failure) }
        if isWaitingForRuntime, endpoint == nil { page.showWaitingForRuntime() }
        if restartWait.isWaiting { page.showWaitingAtGate(true) }
        return page
    }

    private func addTab(_ controller: BrowserWindowController, besides parent: FolderPage) {
        guard let window = controller.window else { return }
        parent.host?.window?.addTabbedWindow(window, ordered: .above)
        window.makeKeyAndOrderFront(nil)
    }

    /// Every window showing one of the folder's pages takes the folder's title.
    private func showTitleInWindows() {
        windows.forEach { $0.showTitle(title, windowTitle: windowTitle) }
    }

    private func serverChanged(_ state: ServerState) {
        linkRequest?.cancel()
        restartWait.serverChanged()
        switch state {
        case .starting:
            endpoint = nil
            failure = nil
            pages.forEach { $0.showStarting() }
        case .ready(let ready):
            endpoint = ready
            failure = nil
            let authorization = supervisor.launch.authorization(for: ready)
            pages.forEach { $0.attach(ready, authorization: authorization) }
            requestIdentity(from: ready, authorization: authorization)
            if !served.isLocal, let link = links.serverReady() { request(link, from: ready) }
        case .failed(let failed):
            endpoint = nil
            let shown = served.isLocal ? failed : failed.diagnosingGitHub(repository: root)
            failure = shown
            pages.forEach { $0.showFailure(shown) }
        case .stopping, .stopped:
            break
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
        showTitleInWindows()
    }
}
