import AppKit
import ShellCore
import WebKit

/// One opened folder: one server, and the windows that show it.
///
/// The first window opens before the server starts and shows its progress; windows the
/// page opens (`target=_blank`, Command-click) join it as tabs. When the last window
/// closes, the server stops: a folder nobody is looking at keeps no process running.
/// A restored folder's windows open before its server starts, which `FolderWindows`
/// schedules.
final class FolderSession: ManagedServer {
    let root: URL
    let logURL: URL
    /// This app's claim on the folder's log while it serves the folder; another running
    /// copy of the app that serves it too writes a log of its own.
    private let logLease: ServerLogLease?
    /// The supervisor, behind the gate every start and restart passes.
    private let server: FolderServer
    private var supervisor: ServerSupervisor { server.supervisor }
    private(set) var windows: [BrowserWindowController] = []
    private var endpoint: ServerEndpoint?
    private var failure: ServerFailure?
    /// What every window of the folder calls itself: from the folder's path until the
    /// server answers `/api/identity`.
    private(set) var title: WindowTitle
    private var identityRequest: Task<Void, Never>?
    var onAllWindowsClosed: ((FolderSession) -> Void)?
    /// A window became key, which is how a tab is selected.
    var onWindowShown: ((FolderSession, BrowserWindowController) -> Void)?
    /// A window opened or closed, or a page changed: what the saved session records.
    var onLayoutChange: (() -> Void)?
    /// A start or restart is waiting for a runtime the app accepts.
    var onWaitingForRuntime: (() -> Void)?

    /// `accepted` is the runtime a server may start from at the moment it would start,
    /// which every start, Retry, and Restart Server ask, not `setup`.
    init(root: URL, setup: RuntimeSetup, gate: LaunchGate, accepted: @escaping () -> RuntimeSetup?) {
        self.root = root
        title = WindowTitle(.localFolder(root))
        let logs = appIdentity.logsDirectory()
        do {
            logLease = try ServerLogLease.claim(for: root, in: logs)
        } catch {
            // Each launch prepares the log too, and a launch that cannot shows why.
            AppLog.app.error("\(String(describing: error), privacy: .public)")
            logLease = nil
        }
        let logURL = logLease?.url ?? ServerLog.url(for: root, in: logs)
        self.logURL = logURL
        let launch = CLIServeLaunch()
        let spec = { (setup: RuntimeSetup) in
            launch.spec(serving: root, with: setup, inherited: ProcessInfo.processInfo.environment, logURL: logURL)
        }
        // Each launch prepares the log first, so a log that cannot be kept fails the
        // launch, and the window says why.
        let supervisor = ServerSupervisor(
            spec: spec(setup), launch: launch, gate: gate,
            makeProcess: { spec in
                if let logURL = spec.logURL { try ServerLog.prepare(logURL) }
                return try SpawnedProcess(spec)
            })
        server = FolderServer(supervisor: supervisor, accepted: accepted, spec: spec)
        let name = root.lastPathComponent
        supervisor.onEvent = { message in
            AppLog.server.info("\(name, privacy: .public): \(message, privacy: .public)")
            do {
                try ServerLog.append(message, to: logURL)
            } catch {
                // The event itself is in the unified log, on the line above.
                AppLog.server.error("\(name, privacy: .public): \(String(describing: error), privacy: .public)")
            }
        }
        supervisor.onChange = { [weak self] state in self?.serverChanged(state) }
    }

    var folderName: String { FileManager.default.displayName(atPath: root.path(percentEncoded: false)) }

    /// The folder's canonical path without a trailing slash, as `OpenTarget` and the saved
    /// session name it.
    var path: String { FolderSession.path(of: root) }

    static func path(of root: URL) -> String {
        var path = root.path(percentEncoded: false)
        while path.count > 1, path.hasSuffix("/") { path.removeLast() }
        return path
    }

    /// Every server child not yet reaped; each pid is also its process group.
    var childPIDs: [pid_t] { supervisor.childPIDs }

    /// The runtime the server last started from, which an upgrade compares with; nil for
    /// a folder whose server has not started, such as a restored one waiting for its tab.
    var startedRuntime: Runtime? { server.startedRuntime }

    /// Whether a start or restart is waiting for a runtime the app accepts.
    var isWaitingForRuntime: Bool { server.held != nil }

    /// Starts the server from the runtime accepted now, unless one is starting, running,
    /// or stopping, and returns once that start is ready or has failed. Without an
    /// accepted runtime the windows say so, and the start waits for `resume()`. False if
    /// `launchCheck` refused it.
    @discardableResult
    func startServer() async -> Bool {
        if await !server.start() { waitForRuntime() }
        return !supervisor.launchWasRefused
    }

    /// For a restored background folder, the check made just before its server would
    /// spawn, after the launch gate (`ServerSupervisor.mayLaunch`); nil once one of its
    /// tabs is selected, which starts it as the user's choice.
    var launchCheck: (() -> Bool)? {
        get { supervisor.mayLaunch }
        set { supervisor.mayLaunch = newValue }
    }

    /// Retry and Restart Server: a fresh server from the runtime accepted now, which may
    /// not be the one this folder started with. Without one, nothing is stopped, and the
    /// restart waits for `resume()`.
    func retry() {
        Task {
            if await !server.restart() { waitForRuntime() }
        }
    }

    /// Carries out a start or restart that waited for a runtime, now that one is accepted.
    func resume() async {
        await server.resume()
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
        await supervisor.shutDown()
    }

    /// Brings the folder's front window forward, showing `page` in it if one is given,
    /// and checks that its server still answers: a hung one is stopped, and its windows
    /// say so and offer Retry.
    func showFrontWindow(page: PageAddress? = nil) {
        let front = windows.first { $0.window?.isVisible == true } ?? windows.first
        if let page, let front {
            front.show(page)  // which checks before it loads
        } else {
            Task { _ = await checkHealth() }
        }
        front?.window?.makeKeyAndOrderFront(nil)
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
        return controller
    }

    private func addTab(_ controller: BrowserWindowController, besides parent: BrowserWindowController) {
        guard let window = controller.window else { return }
        parent.window?.addTabbedWindow(window, ordered: .above)
        window.makeKeyAndOrderFront(nil)
    }

    private func serverChanged(_ state: ServerState) {
        switch state {
        case .starting:
            endpoint = nil
            failure = nil
            windows.forEach { $0.showStarting() }
        case .ready(let ready):
            endpoint = ready
            failure = nil
            let authorization = supervisor.launch.authorization(for: ready)
            windows.forEach { $0.attach(ready, authorization: authorization) }
            requestIdentity(from: ready, authorization: authorization)
        case .failed(let failed):
            endpoint = nil
            failure = failed
            windows.forEach { $0.showFailure(failed) }
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
        let next = WindowTitle(answer.identity(or: .localFolder(root)))
        let name = root.lastPathComponent
        let titled = "\(name): titled \"\(next.plain)\""
        switch answer {
        case .identity:
            AppLog.app.info("\(titled, privacy: .public) from /api/identity")
        case .failed(let reason):
            AppLog.app.error(
                "\(titled, privacy: .public) from the folder's path: /api/identity failed, \(reason, privacy: .public)")
        }
        guard next != title else { return }
        title = next
        windows.forEach { $0.showTitle(next) }
    }
}
