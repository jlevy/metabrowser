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
    var onAllWindowsClosed: ((FolderSession) -> Void)?

    init(root: URL, setup: RuntimeSetup, gate: LaunchGate) {
        self.root = root
        title = WindowTitle(.localFolder(root))
        let logURL = ServerLog.url(for: root)
        self.logURL = logURL
        do {
            try ServerLog.prepare(logURL)
        } catch {
            AppLog.app.error("could not prepare \(logURL.path, privacy: .public): \(error, privacy: .public)")
        }
        let launch = CLIServeLaunch()
        let spec = LaunchSpec(
            executable: setup.runtime.executable,
            arguments: launch.arguments(serving: root),
            environment: ChildEnvironment.build(
                inherited: ProcessInfo.processInfo.environment, toolDirectories: setup.tools.directories),
            // `metab .` run from Terminal reads `.env` files upward from the folder.
            workingDirectory: root.path(percentEncoded: false),
            stdinLine: launch.stdinLine,
            logURL: logURL)
        supervisor = ServerSupervisor(spec: spec, launch: launch, gate: gate)
        let name = root.lastPathComponent
        supervisor.onEvent = { message in
            ServerLog.append(message, to: logURL)
            AppLog.server.info("\(name, privacy: .public): \(message, privacy: .public)")
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

    func retry() {
        Task { await supervisor.restart() }
    }

    func shutDown() async {
        identityRequest?.cancel()
        await supervisor.shutDown()
    }

    func showFrontWindow() {
        let front = windows.first { $0.window?.isVisible == true } ?? windows.first
        front?.window?.makeKeyAndOrderFront(nil)
    }

    func revealLog() {
        NSWorkspace.shared.activateFileViewerSelecting([logURL])
    }

    /// Command-click on a link to this folder's server.
    func openWindow(at url: URL, besides parent: BrowserWindowController) {
        let controller = makeWindow()
        addTab(controller, besides: parent)
        controller.load(url)
    }

    /// `target=_blank` and `window.open`: WebKit loads the request into the view returned.
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
