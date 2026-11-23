import AppKit
import ShellCore
import os

/// This build: its name, its variant, its bundle identifier, which keeps its settings
/// and recents apart from the other variant's, and the log and session folders, named
/// for the app, that both variants share.
nonisolated let appIdentity = AppIdentity.current

nonisolated enum AppLog {
    static let subsystem = appIdentity.bundleIdentifier
    static let app = Logger(subsystem: subsystem, category: "app")
    static let server = Logger(subsystem: subsystem, category: "server")
}

/// App lifecycle: the runtime, the folder sessions, the menus, and quitting.
final class AppDelegate: NSObject, NSApplicationDelegate {
    private let settings = RuntimeSettings()
    private lazy var recentFolders = RecentTargetsMenu(
        setup: { [weak self] in self?.operations.launchableSetup() }, open: { [weak self] in self?.requestRecent($0) })
    /// The folder chooser each window's title opens (`FolderChooser`).
    private lazy var folderChooser = FolderChooserMenu(
        openFolders: { [weak self] in self?.folderWindows.chooserFolders(for: $0) ?? [] },
        recent: { [weak self] in self?.recentFolders.listed() ?? [] },
        choose: { [weak self] in self?.choose($0, in: $1) },
        hasBackgroundFolders: { [weak self] in self?.folderSessions.contains(where: \.isInBackground) ?? false },
        closeBackgroundFolders: { [weak self] in
            AppLog.app.info("closing every folder open in the background")
            self?.folderWindows.closeBackgroundFolders()
        })
    /// View > Switch Folder…, the chooser's keyboard route (`FolderSwitcher`), made the
    /// first time it opens (`showSwitchFolder`).
    private var switchFolderPanel: SwitchFolderWindowController?
    private let launchGate = LaunchGate()
    /// The repositories' lane (`LaunchLane`), whose servers walk ports apart from a
    /// folder's, so they start behind a gate of their own, and a first clone holds up no
    /// folder (`gate(for:)`).
    private let repositoryLaunchGate = LaunchGate()
    private let runtimeModel = RuntimeModel()
    /// The runtime, and the folders waiting for one. `runtimeModel` only mirrors it.
    private lazy var selection = RuntimeSelection(settings: settings, setup: settings.usable())
    /// The window each waiting folder was asked to open in (`request(_:into:)`).
    private var waitingWindows = WaitingWindows<BrowserWindowController>()
    /// The recent repositories the user chose that still wait in RuntimeSelection.
    private var waitingRecentRepositories: Set<URL> = []
    /// The searches, rechecks, and choices that change `selection`, and what follows each.
    private lazy var operations: RuntimeOperations = {
        let settings = self.settings
        let operations = RuntimeOperations(
            selection: selection,
            work: RuntimeOperations.Work(
                discover: { await RuntimeDiscovery.discover(.live(saved: settings.load()?.runtime)) },
                validate: { path, source in
                    let fingerprint = FileFingerprint.of(path)
                    return (fingerprint, await RuntimeDiscovery.validate(path, .live(saved: nil), source: source))
                },
                tools: { RuntimeDiscovery.resolveTools(loginPath: nil, isExecutable: FileChecks.isExecutableFile) }))
        operations.onChange = { [weak self] in self?.presentRuntime() }
        operations.onStart = { start in
            if case .recheck(let path) = start {
                AppLog.app.info("\(path, privacy: .public) changed; checking its version again")
            }
        }
        operations.onFinish = { [weak self] in await self?.finished($0) }
        operations.onRefusal = { path, reason in
            AppLog.app.error(
                "not starting a server from \(path, privacy: .public): \(reason, privacy: .public); checking it again")
        }
        return operations
    }()
    /// Open folders by canonical path and repositories by canonical URL
    /// (`SessionRoot.key`: one session, and so one server, per root), plus the sessions of
    /// closed windows whose servers are still stopping.
    private let sessions = ServerFleet()
    private lazy var folderWindows = FolderWindows(
        store: SessionStore(directory: appIdentity.supportDirectory()),
        openSessions: { [weak self] in self?.sessions.openServers.compactMap { $0 as? FolderSession } ?? [] },
        session: { [weak self] key in self?.sessions[key] as? FolderSession })
    /// Set when a launch found no runtime, so the last session is restored once one is.
    private var restoreAfterDiscovery = false
    private var runtimeWindow: RuntimeWindowController?
    /// Help > Check Setup…, made the first time it is chosen and kept.
    private var checkSetupWindow: CheckSetupWindowController?
    private let checkSetupModel = CheckSetupModel()
    /// The `metab --doctor --json` run Check Setup… awaits: at most one.
    private var checkSetupRun: Task<Void, Never>?
    private var signalSources: [any DispatchSourceSignal] = []
    private var showPanelAfterDiscovery = false
    private var isTerminating = false
    /// Set once a quit has begun stopping the servers, so a link that `metab` resolves
    /// after that starts none.
    private var isQuitting = false
    /// The GitHub links waiting for `metab` to resolve them, one at a time.
    private var links = LinkQueue()
    /// The repositories a link may clone, and the questions about the rest, which wait
    /// beside the queue.
    private var clones = CloneQuestions()
    /// What the links since the last alert could not open, said once the burst has ended.
    private var linkProblems = LinkProblems()
    /// Whether a clone question or the problems alert is up: one at a time.
    private var isShowingLinkModal = false
    private weak var cloneQuestionAlert: NSAlert?
    /// File > Open URL…, made the first time it is chosen and kept: it starts empty each
    /// time it comes on screen.
    private lazy var openURLWindow = OpenURLWindowController(
        onOpen: { [weak self] in self?.checkEnteredLink($0) },
        onDrop: { [weak self] in self?.stopCheckingEnteredLink($0) })
    /// The panel's one request, waiting for its own dry run or for a runtime to check it.
    private var enteredLinkCheck: (request: OpenURLPanel.Request, task: Task<Void, Never>)?
    private var waitingEnteredLink: OpenURLPanel.Request?
    private var hasPendingEnteredLink: Bool { enteredLinkCheck != nil || waitingEnteredLink != nil }
    /// The runtime's file, or where `metab` may appear while there is none.
    private var watch: SetupWatch?
    private var watchedRuntime: Runtime?
    private var watchedPaths: [String] = []
    private var isOfferingRestart = false
    /// The login shell's `PATH` from the last search that read it, for locating uv.
    private var lastLoginPath: [String]?
    private var guideRequests = 0

    // MARK: - Lifecycle

    func applicationWillFinishLaunching(_ notification: Notification) {
        NSApp.mainMenu = MainMenu.build(appName: appIdentity.name, recentFolders: recentFolders)
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
        // And where `metab` may have served a folder, which File > Open Recent then lists.
        recentFolders.refresh()
        // And where a GitHub sign-in may have been fixed: a repository whose start failed on
        // GitHub starts again, and no other window changes.
        sessions.openServers.compactMap { $0 as? FolderSession }.forEach { $0.recheckAfterActivation() }
    }

    func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool { true }

    /// Folders dropped on the Dock icon, opened with Open With, or passed to `open -a`, and
    /// links sent with `open -b`, as `metab LINK --present` sends them.
    func application(_ application: NSApplication, open urls: [URL]) {
        urls.forEach { request($0) }
    }

    /// The Dock icon's menu: the recent targets, as File > Open Recent lists them.
    func applicationDockMenu(_ sender: NSApplication) -> NSMenu? {
        recentFolders.dockMenu()
    }

    func applicationShouldOpenUntitledFile(_ sender: NSApplication) -> Bool { true }

    /// A launch or reopen with nothing to show offers the Open panel.
    func applicationOpenUntitledFile(_ sender: NSApplication) -> Bool {
        if selection.setup != nil {
            if sessions.openServers.isEmpty && selection.waitingFolders.isEmpty && linksAreIdle && !hasPendingEnteredLink {
                openFolder(nil)
            }
        } else {
            showPanelAfterDiscovery = true
        }
        return true
    }

    func applicationShouldTerminateAfterLastWindowClosed(_ sender: NSApplication) -> Bool { false }

    /// Stops every server, each with SIGTERM to its group, a bounded wait, then SIGKILL,
    /// before the app exits.
    func applicationShouldTerminate(_ sender: NSApplication) -> NSApplication.TerminateReply {
        isQuitting = true
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

    /// A click on the Dock icon with no window on screen shows the open folder shown most
    /// recently, which may be minimized or in the background, else offers the Open panel.
    func applicationShouldHandleReopen(_ sender: NSApplication, hasVisibleWindows: Bool) -> Bool {
        if !hasVisibleWindows {
            if let session = folderWindows.mostRecentFolder() {
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
    /// folder already open brings its window forward. A GitHub link opens as `requestLink`
    /// says.
    ///
    /// With `window`, a folder that opens is shown in that window in place of the folder it
    /// shows (`FolderWindows.switchWindow`), as the folder chooser opens a recent folder,
    /// and one that waits for a runtime still opens there (`WaitingWindows`). A link still
    /// opens in a window of its own: which repository it names is `metab`'s answer, which
    /// arrives later.
    ///
    /// With `inOwnFolder`, a file opens in its own folder even inside an open one, as
    /// `metab FILE` would serve it (Help > Open Event Log, `EventLogLocation`). With
    /// `remember` false, the folder is not added to Open Recent, by the app or by the
    /// server it starts.
    func request(
        _ url: URL, into window: BrowserWindowController? = nil, inOwnFolder: Bool = false,
        remember: Bool = true
    ) {
        guard url.isFileURL else { return requestLink(url) }
        let path = FileChecks.canonicalPath(url.path(percentEncoded: false))
        let openRoots = inOwnFolder ? [String]() : folderSessions.filter(\.isLocal).map(\.path)
        guard let target = OpenTarget.resolve(path, kind: OpenTarget.Kind(of: path), openRoots: openRoots) else {
            return refuse(
                "Metabrowser opens folders and files",
                "\(url.lastPathComponent) is not a folder or a file, or it no longer exists.")
        }
        let root = URL(filePath: target.root, directoryHint: .isDirectory)
        if let reason = CLIServeLaunch.unservableReason(root) {
            return refuse("Metabrowser cannot open this folder", "\(root.lastPathComponent) cannot be served: \(reason).")
        }
        let open = sessions[SessionRoot.folder(root).key] as? FolderSession
        if remember { recentFolders.noteOpened(root, isOpen: open != nil) }
        if let session = open {
            session.showFrontWindow(page: target.page)
            return
        }
        recheckChangedRuntime()
        // A request waiting for a runtime is resolved again when one is found.
        let waiting = URL(filePath: path)
        guard selection.setupForOpening(waiting) != nil, let session = session(for: .folder(root)) else {
            if let window, selection.waitingFolders.contains(waiting) { waitingWindows.wait(waiting, in: window) }
            if !selection.isBusy { showSettings(nil) }
            return
        }
        // A window with a sheet open refuses the switch (`FolderWindows.switchWindow`); the
        // folder, whose session now exists, then opens in a window of its own rather than
        // in the background with no page.
        let switched = window.map { folderWindows.switchWindow($0, to: session, page: target.page) } ?? false
        if !switched { folderWindows.place(session.makeWindow(page: target.page)) }
        Task {
            await session.startServer(recording: remember)
            if remember { self.recentFolders.refreshAfterOpen() }
        }
    }

    /// Opens a GitHub link. `metab` resolves each (`PresentDryRun`), one at a time
    /// (`LinkQueue`), to its repository and the canonical link into it. A repository with
    /// a window opens the link in its running server, which shows the revision and page
    /// the link names (`FolderSession.open(link:)`, `SourceLink`). Otherwise a new session
    /// starts its server on the repository and opens the link once it is ready, after
    /// asking first when `metab`'s cache does not hold the repository, a question that
    /// waits beside the queue (`CloneQuestions`).
    /// The links a burst could not open are said in one alert once the burst has ended. A
    /// link waits for a runtime as a folder does. A repository's windows are not saved with
    /// the session (`FolderWindows.snapshot`).
    private func requestLink(_ url: URL) {
        guard GitHubLink.accepts(url) else {
            return noteLinkProblem(LinkAlert(
                message: "Metabrowser opens folders, files, and GitHub links",
                detail: "\(GitHubLink.shown(url)) is not a folder, a file, or an https link to GitHub."))
        }
        recheckChangedRuntime()
        guard selection.setupForOpening(url) != nil else {
            if selection.droppedLinks > 0 { showNextLinkModal() }
            if !selection.isBusy { showSettings(nil) }
            return
        }
        switch links.offer(url) {
        case .queued:
            break
        case .repeated:
            AppLog.app.info("a link already waiting was sent again; it opens once")
        case .dropped:
            AppLog.app.error("\(LinkQueue.limit) links are waiting to be resolved; one more was dropped")
        }
        resolveNextLink()
    }

    /// Resolves the next waiting link, unless one is being resolved; once none waits, the
    /// burst may have ended (`showNextLinkModal`).
    private func resolveNextLink() {
        guard let url = links.next() else {
            if links.isIdle { showNextLinkModal() }
            return
        }
        Task {
            await resolveLink(url)
            links.finish()
            resolveNextLink()
        }
    }

    /// The link itself is logged private: it is what a sender wrote, which can carry a
    /// token that `metab` drops. The repository it resolves to is canonical and carries none.
    private func resolveLink(_ url: URL) async {
        guard !isQuitting else { return }
        guard let setup = operations.launchableSetup() else {
            // Refused at this moment and being checked again: the link waits for that check.
            _ = selection.setupForOpening(url)
            return
        }
        let answer = await askMetab(about: url, with: setup)
        guard !isQuitting else { return }
        let link = url.absoluteString
        switch answer {
        case .plan(let plan):
            AppLog.app.info(
                "\(link, privacy: .private) resolves to \(plan.kind.rawValue, privacy: .public) in \(plan.repository.absoluteString, privacy: .public)")
            await open(plan, with: setup)
        case .refused(let refusal):
            AppLog.app.info("metab refused \(link, privacy: .private): \(refusal.code, privacy: .public)")
        case .unreadable(let reason, _):
            AppLog.app.error("could not resolve \(link, privacy: .private): metab \(reason, privacy: .public)")
        }
        if let alert = answer.alert(link: url, metab: Self.describe(setup)) {
            noteLinkProblem(alert)
        }
    }

    /// What `metab LINK --present --dry-run --format json` says `url` opens: the one
    /// command a link sent to the app and a link typed into File > Open URL… are both
    /// resolved with.
    private func askMetab(about url: URL, with setup: RuntimeSetup) async -> PresentAnswer {
        let spec = PresentDryRun.spec(
            for: url, with: setup, inherited: ProcessInfo.processInfo.environment, home: NSHomeDirectory())
        return PresentDryRun.answer(await CommandRunner.run(spec, timeout: PresentDryRun.timeout))
    }

    /// The `metab` an alert or the Open URL… panel names when it could not read its answer.
    private static func describe(_ setup: RuntimeSetup) -> String {
        "metab \(setup.runtime.version) at \(setup.runtime.executable)"
    }

    /// File > Open URL…: a GitHub URL or repository shortcut, always opened in a mirror.
    /// The panel owns the submission through the dry run and window placement, so a
    /// refusal stays under the field and the app can stop work on a cancelled request.
    @objc func showOpenURL(_ sender: Any?) {
        openURLWindow.show()
    }

    private func checkEnteredLink(_ request: OpenURLPanel.Request) {
        guard !isQuitting else { return }
        recheckChangedRuntime()
        guard let setup = operations.launchableSetup() else {
            waitForEnteredRuntime(request)
            return
        }
        guard openURLWindow.setWaitingForRuntime(false, for: request) else { return }
        waitingEnteredLink = nil
        enteredLinkCheck?.task.cancel()
        let link = request.link
        let task = Task {
            let answer = await askMetab(about: link, with: setup)
            // Editing or closing the panel cancels this dry run.
            guard !Task.isCancelled else { return }
            enteredLinkCheck = nil
            let text = link.absoluteString
            switch answer {
            case .plan(let plan):
                AppLog.app.info(
                    "Open URL…: \(text, privacy: .private) resolves to \(plan.kind.rawValue, privacy: .public) in \(plan.repository.absoluteString, privacy: .public)")
            case .refused(let refusal):
                AppLog.app.info("Open URL…: metab refused \(text, privacy: .private): \(refusal.code, privacy: .public)")
            case .unreadable(let reason, let output):
                AppLog.app.error(
                    "Open URL…: could not resolve \(text, privacy: .private): metab \(reason, privacy: .public); its last output: \(output.suffix(PresentDryRun.shownLines).joined(separator: " | "), privacy: .private)")
            }
            guard !isQuitting,
                  let plan = openURLWindow.answered(answer, for: request, metab: Self.describe(setup))
            else { return }
            if openEntered(plan) {
                openURLWindow.presented(for: request)
            } else if selection.isBusy {
                waitForEnteredRuntime(request)
            } else {
                openURLWindow.failed("Metabrowser could not open a repository window. Try again.", for: request)
            }
        }
        enteredLinkCheck = (request, task)
    }

    private func waitForEnteredRuntime(_ request: OpenURLPanel.Request) {
        if selection.isBusy {
            if openURLWindow.setWaitingForRuntime(true, for: request) { waitingEnteredLink = request }
        } else {
            waitingEnteredLink = nil
            openURLWindow.failed(Self.openURLRuntimeUnavailable, for: request)
        }
    }

    private static let openURLRuntimeUnavailable =
        "Metabrowser needs a server runtime to open this URL. Find or choose metab in Settings, then try again."

    private func failEnteredRuntimeWait() {
        guard let request = waitingEnteredLink else { return }
        waitingEnteredLink = nil
        openURLWindow.failed(Self.openURLRuntimeUnavailable, for: request)
    }

    /// The panel no longer awaits this submission, so it cannot open when a runtime is
    /// found or after its current dry run returns.
    private func stopCheckingEnteredLink(_ request: OpenURLPanel.Request) {
        if waitingEnteredLink == request { waitingEnteredLink = nil }
        guard let check = enteredLinkCheck, check.request == request else { return }
        check.task.cancel()
        enteredLinkCheck = nil
    }

    /// Shows `plan` in its repository's window, or in a new session of the repository.
    /// Either way the repository's one server, started on the repository itself, opens
    /// `plan.link` once it is ready (`FolderSession.open(link:)`, `SourceLink`): it
    /// resolves the link against its mirror, so a ref with a `/` in it opens the right
    /// page, and a second pull request of the repository opens in the same window.
    ///
    /// A sent link looks up its repository in the cache unless it already has approval.
    /// A repository the cache does not hold needs a question. The question and later
    /// links into that repository wait beside the queue, so other links go on.
    private func open(_ plan: PresentPlan, with setup: RuntimeSetup) async {
        let root = SessionRoot.repository(plan.repository)
        if let session = sessions[root.key] as? FolderSession {
            recentFolders.noteOpened(root.url, isOpen: true)
            return session.open(link: plan.link)
        }
        let name = root.identity().fullName
        switch clones.arrive(plan.link, into: root) {
        case .open:
            openRepository(root, on: plan.link)
        case .waits:
            AppLog.app.info("\(name, privacy: .public): a link waits for the answer about cloning it")
        case .declined:
            AppLog.app.info("\(name, privacy: .public): a link was not opened, since cloning it was declined")
        case .dropped:
            AppLog.app.error(
                "\(CloneQuestions.limit) repositories wait for an answer about cloning them; a link into \(name, privacy: .public) was dropped")
        case .lookUp:
            let cached = await isCached(root, with: setup)
            // An explicit open can supersede this lookup while it is suspended.
            guard !isQuitting, sessions[root.key] == nil else { return }
            if cached {
                if let link = clones.found(root) { openRepository(root, on: link) }
            } else {
                clones.ask(root)
                showNextLinkModal()
            }
        }
    }

    /// Opens the plan from a native Open URL submission or a selected recent repository.
    /// That choice authorizes this open. Once its window is shown, a pending question
    /// for an earlier link into the same repository has nothing left to decide.
    private func openEntered(_ plan: PresentPlan) -> Bool {
        let root = SessionRoot.repository(plan.repository)
        guard !isQuitting, openRepository(root, on: plan.link, waitForRuntime: false) else { return false }
        if clones.openedExplicitly(root), let alert = cloneQuestionAlert, NSApp.modalWindow === alert.window {
            NSApp.abortModal()
        }
        showNextLinkModal()
        return true
    }

    /// Whether `metab`'s cache holds `root` (`RepositoryCache`); an answer the app cannot
    /// read is no, so the user is asked.
    private func isCached(_ root: SessionRoot, with setup: RuntimeSetup) async -> Bool {
        let folder = appIdentity.supportDirectory()
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let answer = await RepositoryCache.lookUp(
            root.url, folder: folder.path(percentEncoded: false), with: setup,
            inherited: ProcessInfo.processInfo.environment)
        switch answer {
        case .cached:
            return true
        case .notCached:
            return false
        case .unknown(let reason):
            AppLog.app.error(
                "could not ask metab whether it has \(root.key, privacy: .public): \(reason, privacy: .public); asking before it clones")
            return false
        }
    }

    /// The repository's window, whose server opens `link`, or a new session whose first
    /// ready server opens it. A new session's window joins the window of an open checkout of
    /// the repository as a tab, if one is on screen (`CheckoutWindow`), and is placed as a
    /// new folder's otherwise. Returns whether a window was shown. A sent link missing its
    /// runtime waits and is resolved again; a native choice can handle that wait itself.
    ///
    /// Either is an open, so the repository moves to the front of the recent targets: a
    /// new session's server records it as it starts, and the app records one already open
    /// itself, since opening a link in its server records nothing.
    @discardableResult
    private func openRepository(_ root: SessionRoot, on link: URL, waitForRuntime: Bool = true) -> Bool {
        if let session = sessions[root.key] as? FolderSession {
            recentFolders.noteOpened(root.url, isOpen: true)
            session.open(link: link, showingProgress: !waitForRuntime)
            return true
        }
        let setup = waitForRuntime ? selection.setupForOpening(link) : operations.launchableSetup()
        guard setup != nil, let session = session(for: root, link: link) else {
            if waitForRuntime, !selection.isBusy { showSettings(nil) }
            return false
        }
        let window = session.makeWindow()
        if let checkout = checkout(of: root.url) {
            AppLog.app.info(
                "\(root.key, privacy: .public): its mirror opens as a tab of the checkout \(checkout.root.lastPathComponent, privacy: .private)")
            folderWindows.place(window, besides: checkout)
        } else {
            folderWindows.place(window)
        }
        Task {
            await session.startServer()
            self.recentFolders.refreshAfterOpen()
        }
        return true
    }

    /// The open checkout of `repository` whose window a new window of its mirror joins as
    /// a tab, or nil (`CheckoutWindow`).
    private func checkout(of repository: URL) -> FolderSession? {
        let open = folderWindows.openFolders.byRecency.compactMap { sessions[$0] as? FolderSession }
        let candidates = open.map { session in
            CheckoutWindow.Candidate(
                key: session.path, root: session.served, repository: session.title.identity.repository,
                isShown: session.pages.contains { $0.host?.window?.isVisible == true })
        }
        return CheckoutWindow.host(for: repository, among: candidates).flatMap { sessions[$0] as? FolderSession }
    }

    private func noteLinkProblem(_ alert: LinkAlert) {
        linkProblems.note(alert)
        showNextLinkModal()
    }

    /// Whether no link waits or is being resolved, and no repository waits for the cache or
    /// a question: the end of a burst, and what the app checks before it offers the Open
    /// panel, since a link under way is about to open a window.
    private var linksAreIdle: Bool { links.isIdle && clones.isIdle }

    /// Asks the next clone question, or once the burst has ended, says in one alert what
    /// its links could not open. One modal at a time, from the run loop (`onRunLoop`):
    /// what gathers while one is up is shown when it closes (review C9 on #539).
    private func showNextLinkModal() {
        onRunLoop { [weak self] in self?.raiseNextLinkModal() }
    }

    private func raiseNextLinkModal() {
        guard !isShowingLinkModal, !isQuitting else { return }
        if let root = clones.nextQuestion() {
            isShowingLinkModal = true
            let clone = askToClone(root)
            isShowingLinkModal = false
            if let link = clones.answer(root, clone: clone), !isQuitting { openRepository(root, on: link) }
        } else {
            guard linksAreIdle else { return }
            linkProblems.noteTurnedAway(links.takeDropped(), .queueFull)
            linkProblems.noteTurnedAway(clones.takeDropped(), .questionsFull)
            linkProblems.noteTurnedAway(selection.takeDroppedLinks(), .runtimeWaitFull)
            for (root, count) in clones.endBurst().sorted(by: { $0.key.key < $1.key.key }) {
                linkProblems.note(LinkAlert.declined(root.identity().fullName, count: count))
            }
            guard let alert = linkProblems.take() else { return }
            isShowingLinkModal = true
            refuse(alert.message, alert.detail)
            isShowingLinkModal = false
        }
        showNextLinkModal()
    }

    /// Asks whether to clone `root`, which its links wait for. Cancel is the default
    /// button, so a Return typed into another app as this one comes forward declines
    /// (review C7 on #539). A quit for a signal aborts the alert, which declines.
    private func askToClone(_ root: SessionRoot) -> Bool {
        let name = root.identity().fullName
        let alert = NSAlert()
        alert.messageText = "Clone \(name)?"
        alert.informativeText =
            "Metabrowser has no copy of \(name) yet. Opening this link clones the repository into metab’s cache, and reads it and its pull requests with your gh sign-in."
        alert.addButton(withTitle: "Cancel")  // the first button is the default
        alert.addButton(withTitle: "Clone and Open")
        cloneQuestionAlert = alert
        defer { cloneQuestionAlert = nil }
        let clone = alert.runModal() == .alertSecondButtonReturn
        guard clones.asking == root else { return false }
        AppLog.app.info("\(name, privacy: .public): clone \(clone ? "confirmed" : "declined", privacy: .public)")
        return clone
    }

    /// The open session for `root`, or a new one with no window and no server yet; nil
    /// without a runtime or for a folder that cannot be served.
    private func session(for root: URL) -> FolderSession? {
        session(for: .folder(root))
    }

    /// The open session for `root`, or a new one, whose first ready server opens `link`
    /// when one is given (`FolderSession.init`).
    private func session(for root: SessionRoot, link: URL? = nil) -> FolderSession? {
        let key = root.key
        if let open = sessions[key] as? FolderSession { return open }
        guard let setup = selection.setup, CLIServeLaunch.unservableReason(root.url) == nil else { return nil }
        let session = FolderSession(
            root: root, link: link, setup: setup, gate: gate(for: root.lane),
            accepted: { [weak self] in self?.operations.launchableSetup() })
        session.onWaitingForRuntime = { [weak self] in
            // A search, recheck, or choice that is running settles it, and opens Settings if it finds nothing.
            if self?.selection.isBusy == false { self?.showSettings(nil) }
        }
        session.onRootRefused = { [weak self] refused in self?.folderWindows.rootRefused(refused) }
        session.onLinkNotFound = { [weak self] missing, link, outcome in
            let name = missing.served.identity().fullName
            if let alert = LinkAlert.linkNotFound(outcome, link: link, repository: name) { self?.noteLinkProblem(alert) }
        }
        session.onAllPagesClosed = { [weak self] closed in
            self?.sessions.retire(closed)
            self?.folderWindows.folderClosed(closed)
            self?.retitleWindows()
        }
        session.onTitleChange = { [weak self] _ in self?.retitleWindows() }
        session.onWindowShown = { [weak self] folder, controller in
            self?.folderWindows.windowShown(controller, of: folder)
        }
        session.onLayoutChange = { [weak self] in self?.folderWindows.scheduleSave() }
        session.onPlaceWindow = { [weak self] in self?.folderWindows.place($0) }
        sessions.insert(session, for: key)
        folderWindows.folderOpened(session)
        retitleWindows()
        return session
    }

    /// The launch gate of `lane`'s servers: one per lane, whose port walks do not meet.
    private func gate(for lane: LaunchLane) -> LaunchGate {
        switch lane {
        case .folders: launchGate
        case .repositories: repositoryLaunchGate
        }
    }

    /// Gives every open folder's windows their `window.title`: the short name, or the full
    /// name while another open folder shares the short name (`WindowTitle.windowTitles`).
    private func retitleWindows() {
        let open = folderSessions
        for (session, title) in zip(open, WindowTitle.windowTitles(open.map(\.title))) {
            session.windowTitle = title
        }
        // A folder opened, closed, or was renamed: the Switch Folder panel, if up, lists
        // the folders again.
        switchFolderPanel?.foldersChanged()
    }

    /// The folder chooser for `window`'s title.
    func folderChooserMenu(for window: BrowserWindowController) -> NSMenu {
        folderChooser.menu(for: window)
    }

    /// View > Switch Folder…, over `window`.
    func showSwitchFolder(over window: BrowserWindowController) {
        let panel = switchFolderPanel ?? makeSwitchFolderPanel()
        switchFolderPanel = panel
        panel.show(over: window)
    }

    private func makeSwitchFolderPanel() -> SwitchFolderWindowController {
        SwitchFolderWindowController(
            rows: { [weak self] window in
                guard let self else { return [] }
                return FolderChooser.panelRows(
                    open: folderWindows.chooserFolders(for: window), byRecency: folderWindows.openFolders.byRecency,
                    recent: recentFolders.listed())
            },
            choose: { [weak self] in self?.choose($0, in: $1) },
            close: { [weak self] key in
                guard let self, let session = folderSessions.first(where: { $0.path == key }) else { return }
                closeFolder(session)
            })
    }

    /// Carries out a choice made in the folder chooser of `window`, or of the window the
    /// Switch Folder panel was opened over (`FolderChooser.action`).
    func choose(_ action: FolderChooser.Action, in window: BrowserWindowController?) {
        let open = { (key: String) in self.folderSessions.first { $0.path == key } }
        switch action {
        case .nothing:
            return
        case .showHere(let key):
            guard let window, let session = open(key) else { return }
            AppLog.app.info("switching a window to \(session.folderName, privacy: .public)")
            folderWindows.switchWindow(window, to: session)
        case .bringForward(let key):
            open(key)?.showFrontWindow()
        case .newWindow(let key):
            guard let session = open(key) else { return }
            // A folder in the background moves its page to the new window; one shown
            // elsewhere gets a second page.
            if session.isInBackground {
                session.showFrontWindow()
            } else {
                folderWindows.place(session.makeWindow())
            }
        case .openHere(let url):
            recentFolders.openListed(url) { [weak self] in self?.requestRecent($0, into: window) }
        case .openInNewWindow(let url):
            recentFolders.openListed(url) { [weak self] in self?.requestRecent($0) }
        }
    }

    /// Reopens the canonical repository the user chose in Open Recent, the Dock menu,
    /// or the folder chooser. A recent folder follows the usual native folder path.
    private func requestRecent(_ url: URL, into window: BrowserWindowController? = nil) {
        guard !isQuitting else { return }
        guard let repository = PresentPlan.repositoryURL(url.absoluteString) else {
            return request(url, into: window)
        }
        recheckChangedRuntime()
        let plan = PresentPlan(kind: .repository, repository: repository, link: repository)
        guard !openEntered(plan) else { return }
        _ = selection.setupForOpening(repository)
        if selection.waitingFolders.contains(repository) { waitingRecentRepositories.insert(repository) }
        if selection.droppedLinks > 0 { showNextLinkModal() }
        if !selection.isBusy { showSettings(nil) }
    }

    /// File > Close Folder, for the folder the key window shows. Returns false, having
    /// beeped, when a sheet open on one of the folder's windows holds it up
    /// (`FolderWindows.closeFolder`).
    @discardableResult
    func closeFolder(_ session: FolderSession) -> Bool {
        AppLog.app.info("closing \(session.folderName, privacy: .public) in every window")
        return folderWindows.closeFolder(session)
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

    /// Runs `body` from the run loop rather than inside a main-actor job. A modal loop
    /// entered from a main-actor job stops every other main-actor job, quitting included,
    /// until the alert closes (see `offerRestart`), so an alert a task raises runs from the
    /// run loop instead, as the quit for a signal does (`installTerminationSignals`).
    private func onRunLoop(_ body: @escaping () -> Void) {
        let main = CFRunLoopGetMain()
        CFRunLoopPerformBlock(main, CFRunLoopMode.commonModes.rawValue) {
            MainActor.assumeIsolated { body() }
        }
        CFRunLoopWakeUp(main)
    }

    private func openPendingFolders() {
        openReleased(selection.takeWaitingFolders())
    }

    /// Opens the folders that waited for a runtime, each in the window it was asked to
    /// open in if that window is still open.
    private func openReleased(_ folders: [URL]) {
        for (folder, window) in waitingWindows.release(folders) {
            if waitingRecentRepositories.remove(folder) != nil {
                requestRecent(folder, into: window)
            } else {
                request(folder, into: window)
            }
        }
    }

    @objc func openFolder(_ sender: Any?) {
        let panel = NSOpenPanel()
        panel.canChooseDirectories = true
        panel.canChooseFiles = true
        panel.allowsMultipleSelection = true
        // People often want a dot-folder, such as `~/.claude` for an agent's logs, but the
        // open panel hides them by default and few know Command-Shift-Period, which
        // still toggles them for this panel.
        panel.showsHiddenFiles = true
        panel.prompt = "Open"
        panel.message = "Choose a folder to browse with Metabrowser, or a file to see in its folder."
        panel.begin { [weak self] response in
            guard response == .OK else { return }
            panel.urls.forEach { self?.request($0) }
        }
    }

    // MARK: - Runtime

    /// A search the launch, Find Again, or the watch starts (`RuntimeOperations`). It
    /// counts as running before this returns, so a folder requested in the same run-loop
    /// turn waits for it.
    private func beginDiscovery() {
        guard !selection.isSearching else { return }
        runtimeModel.notice = nil
        operations.beginDiscovery()
    }

    /// Shows how a search, recheck, or choice ended, and opens the folders that waited
    /// for a runtime when one was adopted. A search, recheck, or choice that a newer one
    /// overtook changes nothing when it finishes.
    private func finished(_ finish: RuntimeOperations.Finish) async {
        if case .search(let report) = finish.operation {
            for outcome in report.tried {
                guard case .untrusted(let reason) = outcome.result else { continue }
                AppLog.app.error("not running \(outcome.path, privacy: .public): \(reason, privacy: .public)")
            }
        }
        switch (finish.operation, finish.outcome) {
        case (_, .adopted(let found)):
            adopted(found, opening: finish.released)
            if let request = waitingEnteredLink { checkEnteredLink(request) }
            switch finish.operation {
            case .search:
                if showPanelAfterDiscovery, sessions.openServers.isEmpty, selection.waitingFolders.isEmpty,
                   linksAreIdle, !hasPendingEnteredLink {
                    openFolder(nil)
                }
                showPanelAfterDiscovery = false
            case .choice(let path):
                var notice =
                    "Folders already open keep their server until you restart it with File > Restart Server or Retry."
                // A chosen file runs as chosen; the check discovery would make is shown, not applied.
                if let reason = ExecutableTrust.refusal(path) {
                    notice += " Metabrowser runs \(path) because you chose it, although \(reason)."
                }
                runtimeModel.notice = notice
            case .recheck:
                break
            }
        case (.search(let report), .notFound):
            // Folders already open keep their servers; new ones wait for a runtime.
            AppLog.app.error("no usable metab in \(report.tried.count) places")
            lastLoginPath = report.loginPath
            failEnteredRuntimeWait()
            await prepareGuide()
            showSettings(nil)
        case (.recheck(let path, let result), .notFound):
            AppLog.app.error(
                "\(path, privacy: .public) is no longer usable (\(RuntimeView.describe(result), privacy: .public)); searching again"
            )
        case (.choice(let path), .rejected(.tooOld(let version))):
            runtimeModel.notice = MetabRequirement.flagShortfall(version).map {
                "\(path) is metab \(version), \($0), which Metabrowser needs."
            } ?? "\(path) is metab \(version), and Metabrowser needs \(MetabRequirement.minimum) or later."
            if !selection.needsRecheck && !selection.needsSearch { failEnteredRuntimeWait() }
        case (.choice(let path), .rejected(let rejected)):
            runtimeModel.notice = "\(path) is not a working metab: \(RuntimeView.describe(rejected))."
            if !selection.needsRecheck && !selection.needsSearch { failEnteredRuntimeWait() }
        case (.search, _):
            AppLog.app.info("a search finished after a newer choice; its result is dropped")
        case (.recheck, _):
            AppLog.app.info("a recheck finished after a newer search or choice; its result is dropped")
        case (.choice, _):
            break
        }
    }

    private func adopted(_ found: RuntimeSetup, opening waiting: [URL]) {
        AppLog.app.info(
            "using metab \(found.runtime.version, privacy: .public) at \(found.runtime.executable, privacy: .public) (\(found.runtime.source.label, privacy: .public))"
        )
        runtimeModel.guide = nil
        if restoreAfterDiscovery {
            restoreAfterDiscovery = false
            restoreLastSession()
        }
        openReleased(waiting)
        let held = folderSessions.filter(\.isWaitingForRuntime)
        offerRestart(for: found.runtime)
        // A paused restore carries on in its own order, each root admitted again in its
        // turn; the folders the user opened or restarted meanwhile start one at a time.
        folderWindows.runtimeAccepted()
        Task {
            for session in held { await session.resume() }
        }
    }

    private var folderSessions: [FolderSession] { sessions.openServers.compactMap { $0 as? FolderSession } }

    /// The Settings window shows what `selection` holds, and the watch follows it.
    private func presentRuntime() {
        runtimeModel.setup = selection.setup
        runtimeModel.isSearching = selection.isSearching
        runtimeModel.isChoosing = selection.isChoosing
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
                    checkSetup: { [weak self] in self?.showCheckSetup(nil) },
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

    /// Validates the chosen file and uses it, which overtakes a search still running
    /// (`RuntimeOperations.choose`).
    private func adoptChosen(_ path: String) async {
        runtimeModel.notice = nil
        await operations.choose(path)
    }

    /// Help > Check Setup…: runs `metab --doctor --json` each time the window comes on
    /// screen, unless a run is under way, and shows its report (`DoctorRun`).
    @objc func showCheckSetup(_ sender: Any?) {
        if checkSetupWindow == nil {
            checkSetupWindow = CheckSetupWindowController(
                model: checkSetupModel,
                actions: CheckSetupActions(
                    checkAgain: { [weak self] in self?.runCheckSetup() },
                    openSettings: { [weak self] in self?.showSettings(nil) }))
        }
        runCheckSetup()
        checkSetupWindow?.showWindow(nil)
        checkSetupWindow?.window?.makeKeyAndOrderFront(nil)
    }

    private func runCheckSetup() {
        guard checkSetupRun == nil else { return }
        let setup = selection.setup
        let model = checkSetupModel
        model.header = DoctorRun.header(app: appIdentity, setup: setup)
        model.hasRuntime = setup != nil
        guard let setup else {
            model.answer = nil
            return
        }
        model.isRunning = true
        checkSetupRun = Task { [weak self] in
            let result = await CommandRunner.run(
                DoctorRun.spec(
                    setup: setup, inherited: ProcessInfo.processInfo.environment, appBundle: Bundle.main.bundlePath),
                timeout: DoctorRun.timeout)
            let answer = DoctorRun.answer(result)
            if case .unreadable(let reason, _) = answer {
                AppLog.app.error("metab --doctor --json \(reason, privacy: .public)")
            }
            model.answer = answer
            model.isRunning = false
            self?.checkSetupRun = nil
        }
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

    /// Open requests check immediately because the watch waits for files to settle.
    private func recheckChangedRuntime() {
        if let runtime = selection.setup?.runtime, !selection.isUnverified,
           !runtime.isCurrent(fingerprint: FileFingerprint.of(runtime.executable)) {
            beginRecheck()
        }
    }

    /// Watches the runtime's file against the fingerprint it was validated with, or,
    /// with no runtime, every place discovery looks for `metab` and every candidate the
    /// last search tried. A watch is replaced only when the runtime changes, so a change
    /// it has seen once still settles.
    private func rewatch() {
        if let runtime = selection.setup?.runtime {
            guard watch == nil || runtime != watchedRuntime else { return }
            watchedRuntime = runtime
            watchedPaths = []
            watch = SetupWatch(runtime: runtime)
            return
        }
        let env = DiscoveryEnvironment.live(saved: settings.load()?.runtime)
        let metab = SetupWatch.metabPaths(
            cheap: RuntimeDiscovery.cheapCandidates(env).map(\.0), tried: selection.tried,
            binDirectory: runtimeModel.guide?.binDirectory)
        let uv = SetupGuide.uvCandidates(home: env.home, environment: env.environment, loginPath: lastLoginPath)
        guard watch == nil || watchedRuntime != nil || metab + uv != watchedPaths else { return }
        watchedRuntime = nil
        watchedPaths = metab + uv
        watch = SetupWatch(waitingFor: metab, uv: uv)
    }

    /// Skipped while a search, recheck, or choice runs, so a change it has not seen stays
    /// pending in the watch until the next look, and no automatic check overtakes a file
    /// the user chose.
    private func lookForRuntimeChanges() {
        guard !selection.isBusy, let action = watch?.look() else { return }
        switch action {
        case .recheck: beginRecheck()
        case .discover: beginDiscovery()
        case .replan: Task { await prepareGuide() }
        }
    }

    /// Reports the last search and asks uv, when available, where to watch for metab.
    private func prepareGuide() async {
        guideRequests += 1
        let request = guideRequests
        runtimeModel.isPreparingGuide = true
        defer { if request == guideRequests { runtimeModel.isPreparingGuide = false } }
        let env = DiscoveryEnvironment.live(saved: nil)
        let candidates = SetupGuide.uvCandidates(home: env.home, environment: env.environment, loginPath: lastLoginPath)
        // Only a uv no other account can change is run (ExecutableTrust).
        let uv = await UvToolDirectory.survey(candidates, env: env, refusal: { ExecutableTrust.refusal($0) })
        for refused in uv.refused {
            AppLog.app.error(
                "not running \(refused.path, privacy: .public): \(refused.reason, privacy: .public)")
        }
        if let ran = uv.run, let reason = uv.failure {
            // The guide names the directory it waits in, so the user sees the guess.
            AppLog.app.error(
                "\(ran, privacy: .public) did not say where it installs tools (\(reason, privacy: .public)); waiting in \(uv.binDirectory, privacy: .public), uv's documented default"
            )
        }
        // A runtime that arrived meanwhile, or a newer request, makes this one moot.
        guard request == guideRequests, selection.setup == nil else { return }
        runtimeModel.guide = SetupGuide(
            tried: selection.tried, binDirectory: uv.binDirectory, home: env.home, refusedUv: uv.refused)
        rewatch()
    }

    /// Holds new servers off the runtime, whose file changed, and checks it again, unless
    /// a search, recheck, or choice already running settles it first
    /// (`RuntimeOperations.beginRecheck`). A new compatible version is adopted, with an
    /// offer to restart the servers started from the old one; anything else leaves no
    /// runtime, and a search looks for another.
    private func beginRecheck() {
        operations.beginRecheck()
    }

    /// Offers to restart the open servers that `current`'s executable started at another
    /// version. Restarting them is the user's choice: a restart reloads every window. A
    /// folder whose server never started, such as a restored one waiting for its tab, is
    /// not offered, and one waiting for a runtime starts from `current` anyway.
    ///
    /// The offer is a sheet, not `runModal`: this runs inside a main-actor task, and a
    /// modal loop entered from a main-queue job stops every other main-actor job,
    /// quitting included, until the alert closes.
    private func offerRestart(for current: Runtime) {
        guard !isOfferingRestart else { return }
        let folders = folderSessions.filter { !$0.isWaitingForRuntime }
        let outdated = RuntimeUpgrade.outdated(folders.map(\.startedRuntime), current: current).map { folders[$0] }
        guard let window = outdated.lazy.compactMap({ $0.windows.first?.window }).first else { return }
        let prompt = RuntimeUpgrade.prompt(outdated: outdated.compactMap(\.startedRuntime), current: current)
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
            // Chosen now, not when the sheet opened: an upgrade, a restart, or a rejection
            // may have come since. With no runtime accepted now, nothing is stopped.
            guard let latest = operations.launchableSetup()?.runtime else {
                AppLog.app.error("not restarting after the upgrade: no metab Metabrowser can run is selected now")
                if !selection.isBusy { showSettings(nil) }
                return
            }
            let folders = folderSessions
            RuntimeUpgrade.outdated(folders.map(\.startedRuntime), current: latest).forEach { folders[$0].retry() }
        }
    }

    // MARK: - About and Help

    /// The standard About panel, which reads the version and build from the bundle,
    /// with the build variant and a link to the repository.
    @objc func showAbout(_ sender: Any?) {
        let centered = NSMutableParagraphStyle()
        centered.alignment = .center
        let font = NSFont.systemFont(ofSize: NSFont.smallSystemFontSize)
        let credits = NSMutableAttributedString(string: appIdentity.buildLine + "\n\n", attributes: [
            .font: font,
            .foregroundColor: NSColor.secondaryLabelColor,
            .paragraphStyle: centered,
        ])
        let repository = ProjectLinks.repository
        credits.append(NSAttributedString(string: repository.absoluteString, attributes: [
            .font: font,
            .link: repository,
            .paragraphStyle: centered,
        ]))
        NSApp.orderFrontStandardAboutPanel(options: [.applicationName: appIdentity.name, .credits: credits])
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

    /// Help > Open Event Log: Metabrowser's own log of what its servers did, in a Metabrowser
    /// window. `metab` says where the log is and which segment is newest
    /// (`EventLogLocation`), and the segment opens in a window on the log's own directory,
    /// not inside an open folder that holds it, and without a place in Open Recent
    /// (`EventLogLocation.Action`). A log that does not exist yet, or a `metab` that cannot
    /// say, is told in an alert, not left as a menu item that does nothing.
    @objc func openEventLog(_ sender: Any?) {
        guard let setup = selection.setup else {
            if !selection.isBusy { showSettings(nil) }
            return
        }
        let folder = appIdentity.supportDirectory()
        try? FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        Task {
            let answer = await EventLogLocation.locate(
                folder: folder.path(percentEncoded: false), with: setup,
                inherited: ProcessInfo.processInfo.environment)
            onRunLoop { [weak self] in
                switch EventLogLocation.action(for: answer) {
                case .open(let segment):
                    self?.request(segment, inOwnFolder: true, remember: false)
                case .tell(let title, let message):
                    if case .unavailable(let reason) = answer {
                        AppLog.app.error("could not ask metab where the event log is: \(reason, privacy: .public)")
                    }
                    self?.refuse(title, message)
                }
            }
        }
    }

    @objc func openDocumentation(_ sender: Any?) {
        NSWorkspace.shared.open(ProjectLinks.readme)
    }

    // MARK: - Website data

    /// Metabrowser > Clear Website Data…: empties the store every web pane shares
    /// (`WebDataStore`), for one site that stored something or for all of them, which signs
    /// you out of each in every window, then reloads, signed out, each open page's popover
    /// whose site's data was cleared, whether a window shows the page or its folder is in
    /// the background. Cancel is the default button, as for the clone question, so a stray
    /// Return keeps the sign-in.
    @objc func clearWebsiteData(_ sender: Any?) {
        Task {
            let sites = await WebDataStore.sites()
            let clearing = askWhichWebsiteDataToClear(sites)
            switch clearing {
            case .cancelled: return
            case .all: AppLog.app.info("clearing website data: every site")
            case .sites: AppLog.app.info("clearing website data: one site")
            }
            await WebDataStore.clear(clearing)
            for page in folderSessions.flatMap(\.pages) { page.reloadWebPopover(after: clearing) }
        }
    }

    /// Asks which sites' data to clear, from a pop-up of `WebDataClearing.menu(sites)`.
    private func askWhichWebsiteDataToClear(_ sites: [String]) -> WebDataClearing {
        let alert = NSAlert()
        alert.messageText = "Clear website data?"
        alert.informativeText =
            "This signs you out of the websites Metabrowser shows in its own web views, such as View on GitHub, and removes the cookies, cache, and other data they stored there. It does not change your gh sign-in, your browser, or Metabrowser’s own settings."
        let choice = NSPopUpButton(frame: NSRect(x: 0, y: 0, width: 260, height: 26), pullsDown: false)
        for title in WebDataClearing.menu(sites) {
            choice.menu?.addItem(title.map { NSMenuItem(title: $0, action: nil, keyEquivalent: "") } ?? .separator())
        }
        choice.selectItem(at: 0)
        alert.accessoryView = choice
        alert.addButton(withTitle: "Cancel")  // the first button is the default
        let clear = alert.addButton(withTitle: "Clear")
        clear.hasDestructiveAction = true
        let confirmed = alert.runModal() == .alertSecondButtonReturn
        return WebDataClearing(confirmed: confirmed, selected: choice.indexOfSelectedItem, sites: sites)
    }
}
