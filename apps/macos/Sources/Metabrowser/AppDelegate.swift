import AppKit
import ShellCore
import os

/// This build: its name, its variant, and the folders it keeps apart from the other
/// variant's.
nonisolated let appIdentity = AppIdentity.current

/// The servers this app process runs, for the next launch to end if this one crashes or
/// is force-quit, in the variant's Application Support folder.
nonisolated let serverRecords = ServerRecords(
    directory: appIdentity.supportDirectory().appending(path: "servers", directoryHint: .isDirectory),
    onError: { AppLog.app.error("\($0, privacy: .public)") })

nonisolated enum AppLog {
    static let subsystem = appIdentity.bundleIdentifier
    static let app = Logger(subsystem: subsystem, category: "app")
    static let server = Logger(subsystem: subsystem, category: "server")
}

/// App lifecycle: the runtime, the folder sessions, the menus, and quitting.
final class AppDelegate: NSObject, NSApplicationDelegate {
    private let settings = RuntimeSettings()
    private lazy var recentFolders = RecentFoldersMenu { [weak self] in self?.request($0) }
    private let launchGate = LaunchGate()
    private let runtimeModel = RuntimeModel()
    /// The runtime, and the folders waiting for one. `runtimeModel` only mirrors it.
    private lazy var selection = RuntimeSelection(settings: settings, setup: settings.usable())
    /// Open folders by canonical path (one session, and so one server, per root), plus
    /// the sessions of closed windows whose servers are still stopping.
    private let sessions = ServerFleet()
    private lazy var folderWindows = FolderWindows(
        store: SessionStore(directory: appIdentity.supportDirectory()),
        openSessions: { [weak self] in self?.sessions.openServers.compactMap { $0 as? FolderSession } ?? [] },
        session: { [weak self] path in
            self?.sessions[URL(filePath: path, directoryHint: .isDirectory).path(percentEncoded: false)] as? FolderSession
        })
    /// Set when a launch found no runtime, so the last session is restored once one is.
    private var restoreAfterDiscovery = false
    private var runtimeWindow: RuntimeWindowController?
    private var signalSources: [any DispatchSourceSignal] = []
    private var showPanelAfterDiscovery = false
    private var isTerminating = false

    // MARK: - Lifecycle

    func applicationWillFinishLaunching(_ notification: Notification) {
        NSApp.mainMenu = MainMenu.build(appName: appIdentity.name, recentFolders: recentFolders)
        installTerminationSignals()
        reapOrphans()
        presentRuntime()
        // AppKit delivers launch folders (`open -a`, Open With) after this method and
        // before applicationDidFinishLaunching. Marking the search as running now makes
        // such a folder wait for it, instead of opening Settings as if none was found.
        // Restoring now puts the last session's windows behind any such folder.
        if selection.setup == nil {
            restoreAfterDiscovery = true
            beginDiscovery()
        } else {
            restoreLastSession()
        }
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        if let setup = selection.setup {
            AppLog.app.info("using saved runtime \(setup.runtime.executable, privacy: .public)")
            openPendingFolders()
        }
    }

    func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool { true }

    /// Folders dropped on the Dock icon, opened with Open With, or passed to `open -a`.
    func application(_ application: NSApplication, open urls: [URL]) {
        urls.forEach(request)
    }

    func applicationShouldOpenUntitledFile(_ sender: NSApplication) -> Bool { true }

    /// A launch or reopen with nothing to show offers the Open panel.
    func applicationOpenUntitledFile(_ sender: NSApplication) -> Bool {
        if selection.setup != nil {
            if sessions.openServers.isEmpty && selection.waitingFolders.isEmpty { openFolder(nil) }
        } else {
            showPanelAfterDiscovery = true
        }
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    /// Stops every server, each with SIGTERM to its group, a bounded wait, then SIGKILL,
    /// before the app exits.
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        folderWindows.saveForQuit()
        guard !sessions.isEmpty else { return .terminateNow }
        AppLog.app.info(
            "quitting: stopping \(self.sessions.openServers.count) server(s), \(self.sessions.stoppingCount) already stopping"
        )
        Task {
            await sessions.stopAll()
            AppLog.app.info("all servers stopped")
            NSApp.reply(toApplicationShouldTerminate: true)
        }
        return .terminateLater
    }

    /// A last resort for any server child still unreaped here, which the normal quit
    /// path never leaves.
    func applicationWillTerminate(_ notification: Notification) {
        let remaining = sessions.childPIDs
        guard !remaining.isEmpty else { return }
        AppLog.app.error("servers \(remaining, privacy: .public) still running at exit; stopping their groups")
        let survivors = ExitSweep.end(remaining)
        if !survivors.isEmpty {
            AppLog.app.error("servers \(survivors, privacy: .public) outlasted SIGTERM; their groups got SIGKILL")
        }
    }

    /// Ends the servers an earlier run of this variant left running, as a crashed or
    /// force-quit app does, in the background: new servers need not wait for it, since
    /// each picks a free port. Each ending goes to the unified log and to the folder's
    /// server log.
    private func reapOrphans() {
        let orphans = serverRecords.orphans
        guard !orphans.isEmpty else { return }
        AppLog.app.info("\(orphans.count) server(s) of an app that did not quit are recorded; ending any still running")
        let logs = appIdentity.logsDirectory()
        Task {
            let outcomes = await OrphanReaper.reap(orphans, table: .live)
            for outcome in outcomes {
                AppLog.server.info("\(outcome.summary, privacy: .public)")
                if case .gone = outcome { continue }
                let root = URL(filePath: outcome.record.root, directoryHint: .isDirectory)
                do {
                    try ServerLog.append(outcome.summary, to: ServerLog.url(for: root, in: logs))
                } catch {
                    AppLog.server.error("\(String(describing: error), privacy: .public)")
                }
            }
            serverRecords.settleOrphans(outcomes)
        }
    }

    /// AppKit's default for SIGTERM, SIGINT, and SIGHUP is to die on the spot, which
    /// would orphan every server. Route them through the normal quit instead.
    ///
    /// The quit must start from the run loop, not from inside the dispatch handler:
    /// `.terminateLater` spins a nested run loop until the servers have stopped, and
    /// that loop cannot drain the main dispatch queue (where the stopping task runs)
    /// while one of that queue's own blocks is still on the stack. Calling `terminate`
    /// directly here deadlocked the first live run.
    ///
    /// The handler must be `@Sendable`. Without it, main-actor default isolation infers
    /// the closure as main-actor, and Swift 6's runtime check traps (SIGTRAP) when it
    /// runs on the global queue: the second live run died that way, orphaning its server.
    private func installTerminationSignals() {
        for signalNumber in [SIGTERM, SIGINT, SIGHUP] {
            signal(signalNumber, SIG_IGN)
            let source = DispatchSource.makeSignalSource(signal: signalNumber, queue: .global())
            // The block finds the delegate on the main actor rather than capturing `self`,
            // so nothing crosses from this nonisolated block into the main actor (Swift 6.2
            // rejected the captured form as a data race).
            source.setEventHandler { @Sendable in
                let main = CFRunLoopGetMain()
                CFRunLoopPerformBlock(main, CFRunLoopMode.commonModes.rawValue) {
                    MainActor.assumeIsolated {
                        (NSApp.delegate as? AppDelegate)?.terminateForSignal(signalNumber)
                    }
                }
                CFRunLoopWakeUp(main)
            }
            source.resume()
            signalSources.append(source)
        }
    }

    private func terminateForSignal(_ signalNumber: Int32) {
        guard !isTerminating else { return }
        isTerminating = true
        AppLog.app.info("received signal \(signalNumber); quitting")
        NSApp.terminate(nil)
    }

    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows: Bool) -> Bool {
        if !hasVisibleWindows {
            if let session = sessions.openServers.first as? FolderSession {
                session.showFrontWindow()
            } else if selection.setup != nil {
                openFolder(nil)
            } else {
                showSettings(nil)
            }
        }
        return true
    }

    // MARK: - Folders

    /// Opens `url`: a folder in its own server and window or tab, or a file at its page
    /// inside the open folder that holds it, else inside its own folder (`OpenTarget`). A
    /// folder already open brings its window forward.
    func request(_ url: URL) {
        guard url.isFileURL else { return }
        let path = FileChecks.canonicalPath(url.path(percentEncoded: false))
        let openRoots = sessions.openServers.compactMap { ($0 as? FolderSession)?.path }
        guard let target = OpenTarget.resolve(path, kind: OpenTarget.Kind(of: path), openRoots: openRoots) else {
            return refuse(
                "Metabrowser opens folders and files",
                "\(url.lastPathComponent) is not a folder or a file, or it no longer exists.")
        }
        let root = URL(filePath: target.root, directoryHint: .isDirectory)
        if let reason = CLIServeLaunch.unservableReason(root) {
            return refuse("Metabrowser cannot open this folder", "\(root.lastPathComponent) cannot be served: \(reason).")
        }
        RecentFoldersMenu.noteOpened(root)
        if let session = sessions[root.path(percentEncoded: false)] as? FolderSession {
            session.showFrontWindow(page: target.page)
            return
        }
        // A request waiting for a runtime is resolved again when one is found.
        guard selection.setupForOpening(URL(filePath: path)) != nil, let session = session(for: root) else {
            if !selection.isSearching { showSettings(nil) }
            return
        }
        folderWindows.place(session.makeWindow(page: target.page))
        Task { await session.startServer() }
    }

    /// The open session for `root`, or a new one with no window and no server yet; nil
    /// without a runtime or for a folder that cannot be served.
    private func session(for root: URL) -> FolderSession? {
        let key = root.path(percentEncoded: false)
        if let open = sessions[key] as? FolderSession { return open }
        guard let setup = selection.setup, CLIServeLaunch.unservableReason(root) == nil else { return nil }
        let session = FolderSession(
            root: root, setup: setup, gate: launchGate, currentSetup: { [weak self] in self?.selection.setup })
        session.onAllWindowsClosed = { [weak self] closed in
            self?.sessions.retire(closed)
            self?.folderWindows.folderClosed(closed)
        }
        session.onWindowShown = { [weak self] folder, controller in
            self?.folderWindows.windowShown(controller, of: folder)
        }
        session.onLayoutChange = { [weak self] in self?.folderWindows.scheduleSave() }
        sessions.insert(session, for: key)
        return session
    }

    private func restoreLastSession() {
        folderWindows.restore { [weak self] root in self?.session(for: root) }
    }

    private func refuse(_ message: String, _ detail: String) {
        let alert = NSAlert()
        alert.messageText = message
        alert.informativeText = detail
        alert.runModal()
    }

    private func openPendingFolders() {
        selection.takeWaitingFolders().forEach(request)
    }

    @objc func openFolder(_ sender: Any?) {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = true
        panel.allowsMultipleSelection = true
        panel.prompt = "Open"
        panel.message = "Choose a folder to browse with Metabrowser, or a file to see in its folder."
        panel.begin { [weak self] response in
            guard response == .OK else { return }
            panel.urls.forEach { self?.request($0) }
        }
    }

    // MARK: - Runtime

    /// Marks a search as running before returning, so a folder requested in the same
    /// run-loop turn waits for it, then runs the search.
    private func beginDiscovery() {
        guard !selection.isSearching else { return }
        let ticket = selection.startSearch()
        runtimeModel.notice = nil
        presentRuntime()
        Task { await discoverRuntime(ticket) }
    }

    /// Searches the documented locations for `metab`; on success, saves the result and
    /// opens any folder that was waiting for it. Started only by `beginDiscovery`. A
    /// search that a later Choose metab… overtook changes nothing when it finishes.
    private func discoverRuntime(_ ticket: RuntimeSelection.Ticket) async {
        let report = await RuntimeDiscovery.discover(.live(saved: settings.load()?.runtime))
        let outcome = selection.finishSearch(ticket, with: report)
        presentRuntime()
        switch outcome {
        case .adopted(let found):
            adopted(found)
            if showPanelAfterDiscovery, sessions.openServers.isEmpty, selection.waitingFolders.isEmpty {
                openFolder(nil)
            }
            showPanelAfterDiscovery = false
        case .notFound:
            // Folders already open keep their servers; new ones wait for a runtime.
            AppLog.app.error("no metab found in \(report.tried.count) places")
            showSettings(nil)
        case .rejected, .superseded:
            AppLog.app.info("a search finished after a newer choice; its result is dropped")
        }
    }

    private func adopted(_ found: RuntimeSetup) {
        AppLog.app.info(
            "using metab \(found.runtime.version, privacy: .public) at \(found.runtime.executable, privacy: .public) (\(found.runtime.source.label, privacy: .public))"
        )
        if restoreAfterDiscovery {
            restoreAfterDiscovery = false
            restoreLastSession()
        }
        openPendingFolders()
    }

    /// The Settings window shows what `selection` holds.
    private func presentRuntime() {
        runtimeModel.setup = selection.setup
        runtimeModel.isSearching = selection.isSearching
        runtimeModel.tried = selection.tried
    }

    @objc func showSettings(_ sender: Any?) {
        if runtimeWindow == nil {
            runtimeWindow = RuntimeWindowController(
                model: runtimeModel,
                actions: RuntimeActions(
                    findAgain: { [weak self] in self?.beginDiscovery() },
                    choose: { [weak self] in self?.chooseRuntime() },
                    runDoctor: { [weak self] in Task { await self?.runDoctor() } },
                    revealLogs: { [weak self] in self?.revealLogsFolder(nil) }))
        }
        runtimeWindow?.showWindow(nil)
        runtimeWindow?.window?.makeKeyAndOrderFront(nil)
    }

    private func chooseRuntime() {
        let panel = NSOpenPanel()
        panel.canChooseFiles = true
        panel.canChooseDirectories = false
        panel.allowsMultipleSelection = false
        panel.showsHiddenFiles = true
        panel.resolvesAliases = false  // keep ~/.local/bin/metab, not the tool venv behind it
        panel.treatsFilePackagesAsDirectories = true
        panel.directoryURL = URL(filePath: NSHomeDirectory()).appending(path: ".local/bin")
        panel.message = "Choose the metab command-line tool."
        panel.begin { [weak self] response in
            guard response == .OK, let url = panel.url else { return }
            Task { await self?.adoptChosen(url.path(percentEncoded: false)) }
        }
    }

    /// Validates the chosen file and uses it, which overtakes a search still running.
    private func adoptChosen(_ path: String) async {
        runtimeModel.notice = nil
        let ticket = selection.startChoice()
        presentRuntime()
        let result = await RuntimeDiscovery.validate(path, .live(saved: nil))
        let outcome = selection.finishChoice(ticket, path: path, result: result) {
            RuntimeDiscovery.resolveTools(loginPath: nil, isExecutable: FileChecks.isExecutableFile)
        }
        presentRuntime()
        switch outcome {
        case .adopted(let found):
            adopted(found)
            runtimeModel.notice = "Folders already open keep their server until you restart it with File > Restart Server or Retry."
        case .rejected(let rejected):
            runtimeModel.notice = "\(path) is not a working metab: \(RuntimeView.describe(rejected))."
        case .notFound, .superseded:
            break
        }
    }

    private func runDoctor() async {
        guard let setup = selection.setup else { return }
        runtimeModel.isRunningDoctor = true
        let result = await CommandRunner.run(
            LaunchSpec(
                executable: setup.runtime.executable, arguments: ["--doctor"],
                environment: ChildEnvironment.build(
                    inherited: ProcessInfo.processInfo.environment, toolDirectories: setup.tools.directories)),
            timeout: RuntimeDiscovery.doctorTimeout)
        runtimeModel.isRunningDoctor = false
        runtimeModel.doctorOutput = result.transcript(timeout: RuntimeDiscovery.doctorTimeout).joined(separator: "\n")
    }

    // MARK: - About and Help

    /// The standard About panel, which reads the version and build from the bundle,
    /// with a line saying which build this is: both variants are named Metabrowser.
    @objc func showAbout(_ sender: Any?) {
        let centered = NSMutableParagraphStyle()
        centered.alignment = .center
        let line = NSAttributedString(string: appIdentity.buildLine, attributes: [
            .font: NSFont.systemFont(ofSize: NSFont.smallSystemFontSize),
            .foregroundColor: NSColor.secondaryLabelColor,
            .paragraphStyle: centered,
        ])
        NSApp.orderFrontStandardAboutPanel(options: [.applicationName: appIdentity.name, .credits: line])
    }

    /// Creates the folder first, since it holds nothing until a folder has been served.
    @objc func revealLogsFolder(_ sender: Any?) {
        let directory = appIdentity.logsDirectory()
        do {
            try FileManager.default.createDirectory(
                at: directory, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        } catch {
            AppLog.app.error("could not create the logs folder: \(error, privacy: .public)")
            return refuse(
                "Could not open the logs folder",
                "\(directory.path(percentEncoded: false)) could not be created: \(error.localizedDescription) "
                    + "Check that ~/Library/Logs is a folder you can write to.")
        }
        NSWorkspace.shared.open(directory)
    }

    @objc func openDocumentation(_ sender: Any?) {
        NSWorkspace.shared.open(URL(string: "https://github.com/jlevy/metabrowser#readme")!)
    }
}
