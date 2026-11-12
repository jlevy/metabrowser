import AppKit
import ShellCore
import os

enum AppLog {
    static let subsystem = Bundle.main.bundleIdentifier ?? "io.github.jlevy.metabrowser"
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
        store: SessionStore(directory: Self.supportDirectory),
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
    /// The runtime's file, or where `metab` may appear while there is none.
    private var watch: SetupWatch?
    private var watchedRuntime: Runtime?
    private var watchedPaths: [String] = []
    private var isOfferingRestart = false
    /// The login shell's `PATH` from the last search that read it, for the first-run steps.
    private var lastLoginPath: [String]?
    private var guideRequests = 0

    // MARK: - Lifecycle

    func applicationWillFinishLaunching(_ notification: Notification) {
        NSApp.mainMenu = MainMenu.build(recentFolders: recentFolders)
        installTerminationSignals()
        presentRuntime()
        // AppKit delivers launch folders (`open -a`, Open With) after this method and
        // before applicationDidFinishLaunching. Marking the search as running now makes
        // such a folder wait for it, instead of opening Settings as if none was found.
        // Restoring now puts the last session's windows behind any such folder.
        if selection.setup == nil {
            restoreAfterDiscovery = true
            beginDiscovery()
        } else if let runtime = selection.setup?.runtime,
                  !runtime.isCurrent(fingerprint: FileFingerprint.of(runtime.executable)) {
            // A saved runtime whose file changed, or whose version this build does not
            // accept, is checked before the restored folders start it.
            restoreAfterDiscovery = true
            beginRecheck()
        } else {
            restoreLastSession()
        }
    }

    /// `~/Library/Application Support/<bundle identifier>`, so each variant has its own.
    private static var supportDirectory: URL {
        URL.applicationSupportDirectory.appending(path: AppLog.subsystem, directoryHint: .isDirectory)
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        LaunchLocationNotice.showIfNeeded()
        if let setup = selection.setup {
            AppLog.app.info("using saved runtime \(setup.runtime.executable, privacy: .public)")
            openPendingFolders()
        }
        startWatching()
    }

    /// Coming back from Terminal, where an install or upgrade most likely ran.
    func applicationDidBecomeActive(_ notification: Notification) {
        lookForRuntimeChanges()
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
        for pid in sessions.childPIDs {
            AppLog.app.error("server \(pid) still running at exit; stopping its group")
            kill(-pid, SIGTERM)
            for _ in 0..<20 where kill(pid, 0) == 0 { usleep(50_000) }
            kill(-pid, SIGKILL)
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
        // AppKit does not quit while a sheet or modal alert waits for an answer, such as
        // the offer to restart after an upgrade, and a signal has nobody to answer it.
        for window in NSApp.windows {
            if let sheet = window.attachedSheet { window.endSheet(sheet, returnCode: .abort) }
        }
        if NSApp.modalWindow != nil { NSApp.abortModal() }
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
        if let current = selection.setup?.runtime, !selection.isRechecking,
           !current.isCurrent(fingerprint: FileFingerprint.of(current.executable)) {
            beginRecheck()
        }
        // A request waiting for a runtime is resolved again when one is found.
        guard selection.setupForOpening(URL(filePath: path)) != nil, let session = session(for: root) else {
            if !selection.isSearching && !selection.isRechecking { showSettings(nil) }
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
            AppLog.app.error("no usable metab in \(report.tried.count) places")
            lastLoginPath = report.loginPath
            await prepareGuide()
            showSettings(nil)
        case .rejected, .superseded:
            AppLog.app.info("a search finished after a newer choice; its result is dropped")
        }
    }

    private func adopted(_ found: RuntimeSetup) {
        AppLog.app.info(
            "using metab \(found.runtime.version, privacy: .public) at \(found.runtime.executable, privacy: .public) (\(found.runtime.source.label, privacy: .public))"
        )
        runtimeModel.guide = nil
        if restoreAfterDiscovery {
            restoreAfterDiscovery = false
            restoreLastSession()
        }
        openPendingFolders()
        offerRestart(for: found.runtime)
    }

    /// The Settings window shows what `selection` holds, and the watch follows it.
    private func presentRuntime() {
        runtimeModel.setup = selection.setup
        runtimeModel.isSearching = selection.isSearching
        runtimeModel.tried = selection.tried
        rewatch()
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
        let fingerprint = FileFingerprint.of(path)
        let result = await RuntimeDiscovery.validate(path, .live(saved: nil))
        let outcome = selection.finishChoice(ticket, path: path, result: result, fingerprint: fingerprint) {
            RuntimeDiscovery.resolveTools(loginPath: nil, isExecutable: FileChecks.isExecutableFile)
        }
        presentRuntime()
        switch outcome {
        case .adopted(let found):
            adopted(found)
            runtimeModel.notice = "Folders already open keep their server until you restart it with File > Restart Server or Retry."
        case .rejected(.tooOld(let version)):
            runtimeModel.notice = "\(path) is metab \(version), and Metabrowser needs \(MetabRequirement.minimum) or later."
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
            timeout: .seconds(60))
        runtimeModel.isRunningDoctor = false
        var lines = result.output
        if let error = result.launchError { lines.append("could not run: \(error)") }
        if result.timedOut { lines.append("(stopped after 60 seconds)") }
        if let status = result.status { lines.append("(\(ExitStatus(waitStatus: status)))") }
        runtimeModel.doctorOutput = lines.joined(separator: "\n")
    }

    // MARK: - Watching the Runtime

    /// Looks at the watched files every `SetupWatch.interval` for the app's lifetime.
    private func startWatching() {
        rewatch()
        Task { [weak self] in
            while true {
                do {
                    try await Task.sleep(for: SetupWatch.interval, tolerance: SetupWatch.interval / 2)
                } catch {
                    return  // cancelled, which only ending the app does
                }
                self?.lookForRuntimeChanges()
            }
        }
    }

    /// Watches the runtime's file against the fingerprint it was validated with, or,
    /// with no runtime, every place discovery finds `metab` without a shell. A watch is
    /// replaced only when the runtime changes, so a change it has seen once still settles.
    private func rewatch() {
        if let runtime = selection.setup?.runtime {
            guard watch == nil || runtime != watchedRuntime else { return }
            watchedRuntime = runtime
            watchedPaths = []
            watch = SetupWatch(runtime: runtime)
            return
        }
        let env = DiscoveryEnvironment.live(saved: settings.load()?.runtime)
        var metab = RuntimeDiscovery.cheapCandidates(env).map(\.0)
        if let bin = runtimeModel.guide?.binDirectory, !metab.contains(bin + "/metab") { metab.append(bin + "/metab") }
        let uv = SetupGuide.uvCandidates(home: env.home, environment: env.environment, loginPath: lastLoginPath)
        guard watch == nil || watchedRuntime != nil || metab + uv != watchedPaths else { return }
        watchedRuntime = nil
        watchedPaths = metab + uv
        watch = SetupWatch(waitingFor: metab, uv: uv)
    }

    /// Skipped while a search or recheck runs, so a change it has not seen stays
    /// pending in the watch until the next look.
    private func lookForRuntimeChanges() {
        guard !selection.isSearching, !selection.isRechecking, let action = watch?.look() else { return }
        switch action {
        case .recheck: beginRecheck()
        case .discover: beginDiscovery()
        case .replan: Task { await prepareGuide() }
        }
    }

    /// Works out the first-run steps from the last search and what is installed now,
    /// asking uv, when there is one, where it puts `metab`.
    private func prepareGuide() async {
        guideRequests += 1
        let request = guideRequests
        let env = DiscoveryEnvironment.live(saved: nil)
        let uv = SetupGuide.uvCandidates(home: env.home, environment: env.environment, loginPath: lastLoginPath)
            .first(where: FileChecks.isExecutableFile)
        var binDirectory = RuntimeDiscovery.uvToolBinDirectory(env)
        if let uv {
            switch await UvToolDirectory.ask(uv: uv, env: env) {
            case .directory(let directory):
                binDirectory = directory
            case .failed(let reason):
                // The guide names the directory it waits in, so the user sees the guess.
                AppLog.app.error(
                    "\(uv, privacy: .public) did not say where it installs tools (\(reason, privacy: .public)); waiting in \(binDirectory, privacy: .public), uv's documented default"
                )
            }
        }
        // A runtime that arrived meanwhile, or a newer request, makes this one moot.
        guard request == guideRequests, selection.setup == nil else { return }
        let hasHomebrew = RuntimeDiscovery.homebrewBins.contains { FileChecks.isExecutableFile($0 + "/brew") }
        let guide = SetupGuide(
            tried: selection.tried, uv: uv, binDirectory: binDirectory, home: env.home, loginPath: lastLoginPath,
            hasHomebrew: hasHomebrew)
        AppLog.app.info(
            "first-run steps: \(guide.steps.map(\.command).joined(separator: "; "), privacy: .public); waiting for metab in \(binDirectory, privacy: .public)"
        )
        runtimeModel.guide = guide
        rewatch()
    }

    private func beginRecheck() {
        guard let previous = selection.setup, !selection.isRechecking, !selection.isSearching else { return }
        let ticket = selection.startRecheck()
        Task { await recheckRuntime(previous, ticket) }
    }

    /// Runs `--version` on the runtime again. A new compatible version is adopted, with
    /// an offer to restart the servers started from the old one; anything else leaves no
    /// runtime, and a search looks for another.
    private func recheckRuntime(_ previous: RuntimeSetup, _ ticket: RuntimeSelection.Ticket) async {
        let path = previous.runtime.executable
        AppLog.app.info("\(path, privacy: .public) changed; checking its version again")
        let fingerprint = FileFingerprint.of(path)
        let result = await RuntimeDiscovery.validate(path, .live(saved: nil))
        let outcome = selection.finishRecheck(ticket, fingerprint: fingerprint, result: result)
        presentRuntime()
        switch outcome {
        case .adopted(let found):
            adopted(found)
        case .notFound:
            AppLog.app.error(
                "\(path, privacy: .public) is no longer usable (\(RuntimeView.describe(result), privacy: .public)); searching again"
            )
            beginDiscovery()
        case .rejected, .superseded:
            AppLog.app.info("a recheck finished after a newer search or choice; its result is dropped")
        }
    }

    /// Offers to restart the open servers that `current`'s executable started at another
    /// version. Restarting them is the user's choice: a restart reloads every window.
    ///
    /// The offer is a sheet, not `runModal`: this runs inside a main-actor task, and a
    /// modal loop entered from a main-queue job stops every other main-actor job,
    /// quitting included, until the alert closes.
    private func offerRestart(for current: Runtime) {
        guard !isOfferingRestart else { return }
        let folders = sessions.openServers.compactMap { $0 as? FolderSession }
        let outdated = RuntimeUpgrade.outdated(folders.map(\.runtime), current: current).map { folders[$0] }
        guard let window = outdated.lazy.compactMap({ $0.windows.first?.window }).first else { return }
        let prompt = RuntimeUpgrade.prompt(outdated: outdated.map(\.runtime), current: current)
        isOfferingRestart = true
        let alert = NSAlert()
        alert.messageText = prompt.title
        alert.informativeText = prompt.message
        alert.addButton(withTitle: "Restart Servers")
        alert.addButton(withTitle: "Not Now")
        window.makeKeyAndOrderFront(nil)
        alert.beginSheetModal(for: window) { [weak self] response in
            guard let self else { return }
            isOfferingRestart = false
            guard response == .alertFirstButtonReturn else {
                AppLog.app.info("restart after the upgrade declined; File > Restart Server restarts a folder")
                return
            }
            // Chosen now, not when the sheet opened: an upgrade or restart may have run since.
            let latest = selection.setup?.runtime ?? current
            sessions.openServers.compactMap { $0 as? FolderSession }
                .filter { !RuntimeUpgrade.outdated([$0.runtime], current: latest).isEmpty }
                .forEach { $0.retry() }
        }
    }

    // MARK: - Help

    @objc func revealLogsFolder(_ sender: Any?) {
        let directory = ServerLog.directory()
        try? FileManager.default.createDirectory(
            at: directory, withIntermediateDirectories: true, attributes: [.posixPermissions: 0o700])
        NSWorkspace.shared.open(directory)
    }

    @objc func openDocumentation(_ sender: Any?) {
        NSWorkspace.shared.open(URL(string: "https://github.com/jlevy/metabrowser#readme")!)
    }
}
