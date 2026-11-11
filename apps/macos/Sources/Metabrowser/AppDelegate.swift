import AppKit
import ShellCore
import os

enum AppLog {
    static let subsystem = Bundle.main.bundleIdentifier ?? "io.github.jlevy.metabrowser"
    static let app = Logger(subsystem: subsystem, category: "app")
    static let server = Logger(subsystem: subsystem, category: "server")
}

/// App lifecycle: the runtime, the folder sessions, the menus, and quitting.
final class AppDelegate: NSObject, NSApplicationDelegate, NSMenuDelegate {
    private let settings = RuntimeSettings()
    private let recents = RecentFolderStore()
    private let launchGate = LaunchGate()
    private let runtimeModel = RuntimeModel()
    private var setup: RuntimeSetup?
    /// Open folders by canonical path (one session, and so one server, per root), plus
    /// the sessions of closed windows whose servers are still stopping.
    private let sessions = ServerFleet()
    /// Folders asked for before a runtime was found.
    private var pendingFolders: [URL] = []
    private var runtimeWindow: RuntimeWindowController?
    private var signalSources: [any DispatchSourceSignal] = []
    private var showPanelAfterDiscovery = false
    private var isTerminating = false

    // MARK: - Lifecycle

    func applicationWillFinishLaunching(_ notification: Notification) {
        NSApp.mainMenu = MainMenu.build(recentFolders: self)
        installTerminationSignals()
        setup = settings.usable()
        runtimeModel.setup = setup
        // AppKit delivers launch folders (`open -a`, Open With) after this method and
        // before applicationDidFinishLaunching. Marking the search as running now makes
        // such a folder wait for it, instead of opening Settings as if none was found.
        if setup == nil { beginDiscovery() }
    }

    func applicationDidFinishLaunching(_ notification: Notification) {
        if let setup {
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
        if setup != nil {
            if sessions.openServers.isEmpty && pendingFolders.isEmpty { openFolder(nil) }
        } else {
            showPanelAfterDiscovery = true
        }
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    /// Stops every server, each with SIGTERM to its group, a bounded wait, then SIGKILL,
    /// before the app exits.
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
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
            source.setEventHandler { @Sendable [weak self] in
                let main = CFRunLoopGetMain()
                CFRunLoopPerformBlock(main, CFRunLoopMode.commonModes.rawValue) {
                    MainActor.assumeIsolated { self?.terminateForSignal(signalNumber) }
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
            } else if setup != nil {
                openFolder(nil)
            } else {
                showSettings(nil)
            }
        }
        return true
    }

    // MARK: - Folders

    /// Opens `url` in its own window and server, or brings its window forward.
    func request(_ url: URL) {
        guard url.isFileURL else { return }
        let root = URL(
            filePath: FileChecks.canonicalPath(url.path(percentEncoded: false)), directoryHint: .isDirectory)
        let key = root.path(percentEncoded: false)
        guard FileChecks.isDirectory(key) else {
            return refuse("Metabrowser opens folders", "\(url.lastPathComponent) is not a folder. Open the folder that contains it.")
        }
        if let reason = CLIServeLaunch.unservableReason(root) {
            return refuse("Metabrowser cannot open this folder", "\(url.lastPathComponent) cannot be served: \(reason).")
        }
        var folders = recents.folders
        folders.add(key)
        recents.folders = folders
        if let session = sessions[key] as? FolderSession {
            session.showFrontWindow()
            return
        }
        guard let setup else {
            if !pendingFolders.contains(root) { pendingFolders.append(root) }
            if !runtimeModel.isSearching { showSettings(nil) }
            return
        }
        let session = FolderSession(root: root, setup: setup, gate: launchGate)
        session.onAllWindowsClosed = { [weak self] closed in self?.sessions.retire(closed) }
        sessions.insert(session, for: key)
        session.start()
    }

    private func refuse(_ message: String, _ detail: String) {
        let alert = NSAlert()
        alert.messageText = message
        alert.informativeText = detail
        alert.runModal()
    }

    private func openPendingFolders() {
        let folders = pendingFolders
        pendingFolders.removeAll()
        folders.forEach(request)
    }

    @objc func openFolder(_ sender: Any?) {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = false
        panel.allowsMultipleSelection = true
        panel.prompt = "Open"
        panel.message = "Choose a folder to browse with Metabrowser."
        panel.begin { [weak self] response in
            guard response == .OK else { return }
            panel.urls.forEach { self?.request($0) }
        }
    }

    @objc func openRecent(_ sender: NSMenuItem) {
        guard let path = sender.representedObject as? String else { return }
        request(URL(filePath: path, directoryHint: .isDirectory))
    }

    @objc func clearRecent(_ sender: Any?) {
        var folders = recents.folders
        folders.clear()
        recents.folders = folders
    }

    /// Rebuilds File > Open Recent each time it opens.
    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        for path in recents.folders.existing() {
            let item = NSMenuItem(
                title: FileManager.default.displayName(atPath: path), action: #selector(openRecent(_:)),
                keyEquivalent: "")
            item.representedObject = path
            item.toolTip = path
            item.image = NSWorkspace.shared.icon(forFile: path)
            item.image?.size = NSSize(width: 16, height: 16)
            menu.addItem(item)
        }
        if menu.items.isEmpty {
            menu.addItem(NSMenuItem(title: "No Recent Folders", action: nil, keyEquivalent: ""))
        }
        menu.addItem(.separator())
        menu.addItem(NSMenuItem(title: "Clear Menu", action: #selector(clearRecent(_:)), keyEquivalent: ""))
    }

    // MARK: - Runtime

    /// Marks a search as running before returning, so a folder requested in the same
    /// run-loop turn waits for it, then runs the search.
    private func beginDiscovery() {
        guard !runtimeModel.isSearching else { return }
        runtimeModel.isSearching = true
        runtimeModel.notice = nil
        Task { await discoverRuntime() }
    }

    /// Searches the documented locations for `metab`; on success, saves the result and
    /// opens any folder that was waiting for it. Started only by `beginDiscovery`.
    private func discoverRuntime() async {
        let report = await RuntimeDiscovery.discover(.live(saved: settings.load()?.runtime))
        runtimeModel.isSearching = false
        runtimeModel.tried = report.tried
        guard let found = report.setup else {
            AppLog.app.error("no metab found in \(report.tried.count) places")
            runtimeModel.setup = nil
            showSettings(nil)
            return
        }
        use(found)
        if showPanelAfterDiscovery, sessions.openServers.isEmpty, pendingFolders.isEmpty { openFolder(nil) }
        showPanelAfterDiscovery = false
    }

    private func use(_ found: RuntimeSetup) {
        AppLog.app.info(
            "using metab \(found.runtime.version, privacy: .public) at \(found.runtime.executable, privacy: .public) (\(found.runtime.source.label, privacy: .public))"
        )
        settings.save(found)
        setup = found
        runtimeModel.setup = found
        openPendingFolders()
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

    private func adoptChosen(_ path: String) async {
        runtimeModel.notice = nil
        let result = await RuntimeDiscovery.validate(path, .live(saved: nil))
        guard case .valid(let version) = result else {
            runtimeModel.notice = "\(path) is not a working metab: \(RuntimeView.describe(result))."
            return
        }
        let tools = setup?.tools
            ?? RuntimeDiscovery.resolveTools(loginPath: nil, isExecutable: FileChecks.isExecutableFile)
        use(RuntimeSetup(runtime: Runtime(executable: path, version: version, source: .chosen), tools: tools))
        runtimeModel.notice = "Folders already open keep their server until you restart it."
    }

    private func runDoctor() async {
        guard let setup else { return }
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
