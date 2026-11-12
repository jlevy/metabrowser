import AppKit
import ShellCore
import WebKit

/// One opened folder: one server, and the windows that show it.
///
/// The first window opens before the server starts and shows its progress; windows the
/// page opens (`target=_blank`, Command-click) join it as tabs. When the last window
/// closes, the server stops: a folder nobody is looking at keeps no process running.
final class FolderSession: ManagedServer {
    let root: URL
    let logURL: URL
    private let supervisor: ServerSupervisor
    private(set) var windows: [BrowserWindowController] = []
    private var endpoint: ServerEndpoint?
    private var failure: ServerFailure?
    /// What every window of the folder calls itself: from the folder's path until the
    /// server answers `/api/identity`.
    private(set) var title: WindowTitle
    private var identityRequest: Task<Void, Never>?
    /// The runtime the app would start now, which Retry and Restart Server use.
    private let currentSetup: () -> RuntimeSetup?
    var onAllWindowsClosed: ((FolderSession) -> Void)?

    init(root: URL, setup: RuntimeSetup, gate: LaunchGate, currentSetup: @escaping () -> RuntimeSetup?) {
        self.currentSetup = currentSetup
        self.root = root
        title = WindowTitle(.localFolder(root))
        let logURL = ServerLog.url(for: root, in: appIdentity.logsDirectory())
        self.logURL = logURL
        let launch = CLIServeLaunch()
        let spec = launch.spec(
            serving: root, with: setup, inherited: ProcessInfo.processInfo.environment, logURL: logURL)
        // Each launch prepares the log first, so a log that cannot be kept fails the
        // launch, and the window says why.
        supervisor = ServerSupervisor(
            spec: spec, launch: launch, gate: gate,
            makeProcess: { spec in
                if let logURL = spec.logURL { try ServerLog.prepare(logURL) }
                return try SpawnedProcess(spec)
            })
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

    /// Every server child not yet reaped; each pid is also its process group.
    var childPIDs: [pid_t] { supervisor.childPIDs }

    func start() {
        let controller = makeWindow()
        controller.showWindow(nil)
        Task { await supervisor.start() }
    }

    /// Retry and Restart Server: a fresh server from the runtime chosen now, which may not
    /// be the one this folder started with. With no runtime (a search found none), the
    /// folder keeps its own.
    func retry() {
        let spec = currentSetup().map {
            supervisor.launch.spec(
                serving: root, with: $0, inherited: ProcessInfo.processInfo.environment, logURL: logURL)
        }
        Task { await supervisor.restart(using: spec) }
    }

    func shutDown() async {
        identityRequest?.cancel()
        await supervisor.shutDown()
    }

    /// Brings the folder back, and checks that its server still answers: a hung one is
    /// stopped, and its windows say so and offer Retry.
    func showFrontWindow() {
        let front = windows.first { $0.window?.isVisible == true } ?? windows.first
        front?.window?.makeKeyAndOrderFront(nil)
        Task { _ = await supervisor.checkHealth() }
    }

    func revealLog() {
        NSWorkspace.shared.activateFileViewerSelecting([logURL])
    }

    /// Command-click on a link to this folder's server.
    func openWindow(at url: URL, besides parent: BrowserWindowController) {
        let controller = makeWindow()
        addTab(controller, besides: parent)
        attach(controller, loading: url)
    }

    /// Loads `url` in a window joining a running server once the server proves it still
    /// answers, since a live pid is not a working server. A server that does not answer
    /// fails, which every window shows; one not ready yet loads every window when it is.
    private func attach(_ controller: BrowserWindowController, loading url: URL) {
        Task {
            guard case .healthy = await supervisor.checkHealth() else { return }
            controller.load(url)
        }
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
    }

    private func makeWindow(configuration: WKWebViewConfiguration? = nil) -> BrowserWindowController {
        let controller = BrowserWindowController(session: self, configuration: configuration)
        windows.append(controller)
        controller.adoptServer(endpoint)
        if let failure { controller.showFailure(failure) }
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
        case .missingRoute:
            // The fallback named in FolderIdentity.localFolder: a metab older than the route.
            AppLog.app.info("\(titled, privacy: .public) from the folder's path: this metab has no /api/identity")
        case .failed(let reason):
            AppLog.app.error(
                "\(titled, privacy: .public) from the folder's path: /api/identity failed, \(reason, privacy: .public)")
        }
        guard next != title else { return }
        title = next
        windows.forEach { $0.showTitle(next) }
    }
}
