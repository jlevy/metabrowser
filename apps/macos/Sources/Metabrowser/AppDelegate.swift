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
        setup: { [weak self] in self?.operations.launchableSetup() }, open: { [weak self] in self?.request($0) })
    private let launchGate = LaunchGate()
    /// The repositories' lane (`LaunchLane`), whose servers walk ports apart from a
    /// folder's, so they start behind a gate of their own, and a first clone holds up no
    /// folder (`gate(for:)`).
    private let repositoryLaunchGate = LaunchGate()
    private let runtimeModel = RuntimeModel()
    /// The runtime, and the folders waiting for one. `runtimeModel` only mirrors it.
    private lazy var selection = RuntimeSelection(settings: settings, setup: settings.usable())
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
        session: { [weak self] path in
            self?.sessions[URL(filePath: path, directoryHint: .isDirectory).path(percentEncoded: false)] as? FolderSession
        })
    /// Set when a launch found no runtime, so the last session is restored once one is.
    private var restoreAfterDiscovery = false
    private var runtimeWindow: RuntimeWindowController?
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
    /// File > Open URL…, made the first time it is chosen and kept: it starts empty each
    /// time it comes on screen.
    private lazy var openURLWindow = OpenURLWindowController(
        onOpen: { [weak self] in self?.checkEnteredLink($0) },
        onDrop: { [weak self] in self?.stopCheckingEnteredLink($0) })
    /// The dry run for the link File > Open URL… awaits, and the task that applies its
    /// answer: at most one, since the panel awaits one answer and stops this one when it
    /// drops it (`stopCheckingEnteredLink`).
    private var enteredLinkCheck: (link: URL, task: Task<Void, Never>)?
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
    }

    func applicationSupportsSecureRestorableState(_ app: NSApplication) -> Bool { true }

    /// Folders dropped on the Dock icon, opened with Open With, or passed to `open -a`, and
    /// links sent with `open -b`, as `metab LINK --present` sends them.
    func application(_ application: NSApplication, open urls: [URL]) {
        urls.forEach(request)
    }

    /// The Dock icon's menu: the recent targets, as File > Open Recent lists them.
    func applicationDockMenu(_ sender: NSApplication) -> NSMenu? {
        recentFolders.dockMenu()
    }

    func applicationShouldOpenUntitledFile(_ sender: NSApplication) -> Bool { true }

    /// A launch or reopen with nothing to show offers the Open panel.
    func applicationOpenUntitledFile(_ sender: NSApplication) -> Bool {
        if selection.setup != nil {
            if sessions.openServers.isEmpty && selection.waitingFolders.isEmpty && linksAreIdle { openFolder(nil) }
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
    /// folder already open brings its window forward. A GitHub link opens as `requestLink`
    /// says.
    func request(_ url: URL) {
        guard url.isFileURL else { return requestLink(url) }
        let path = FileChecks.canonicalPath(url.path(percentEncoded: false))
        let openRoots = folderSessions.filter(\.isLocal).map(\.path)
        guard let target = OpenTarget.resolve(path, kind: OpenTarget.Kind(of: path), openRoots: openRoots) else {
            return refuse(
                "Metabrowser opens folders and files",
                "\(url.lastPathComponent) is not a folder or a file, or it no longer exists.")
        }
        let root = URL(filePath: target.root, directoryHint: .isDirectory)
        if let reason = CLIServeLaunch.unservableReason(root) {
            return refuse("Metabrowser cannot open this folder", "\(root.lastPathComponent) cannot be served: \(reason).")
        }
        recentFolders.noteOpened(root, isOpen: sessions[root.path(percentEncoded: false)] != nil)
        if let session = sessions[root.path(percentEncoded: false)] as? FolderSession {
            session.showFrontWindow(page: target.page)
            return
        }
        if let current = selection.setup?.runtime, !selection.isUnverified,
           !current.isCurrent(fingerprint: FileFingerprint.of(current.executable)) {
            beginRecheck()
        }
        // A request waiting for a runtime is resolved again when one is found.
        guard selection.setupForOpening(URL(filePath: path)) != nil, let session = session(for: .folder(root)) else {
            if !selection.isBusy { showSettings(nil) }
            return
        }
        folderWindows.place(session.makeWindow(page: target.page))
        Task {
            await session.startServer()
            self.recentFolders.refreshAfterOpen()
        }
    }

    /// Opens a GitHub link. `metab` resolves each (`PresentDryRun`), one at a time
    /// (`LinkQueue`), to its repository and the canonical link to serve it with. A
    /// repository with a window starts its server again on that link, so the window shows
    /// the revision and page the link names (`FolderSession.open(link:)`). Otherwise a new
    /// session starts its server on the link, after asking first when `metab`'s cache does
    /// not hold the repository, a question that waits beside the queue (`CloneQuestions`).
    /// The links a burst could not open are said in one alert once the burst has ended. A
    /// link waits for a runtime as a folder does. A repository's windows are not saved with
    /// the session (`FolderWindows.snapshot`).
    private func requestLink(_ url: URL) {
        guard GitHubLink.accepts(url) else {
            return noteLinkProblem(LinkAlert(
                message: "Metabrowser opens folders, files, and GitHub links",
                detail: "\(GitHubLink.shown(url)) is not a folder, a file, or an https link to GitHub."))
        }
        if let current = selection.setup?.runtime, !selection.isUnverified,
           !current.isCurrent(fingerprint: FileFingerprint.of(current.executable)) {
            beginRecheck()
        }
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

    /// File > Open URL…: one field for a full GitHub URL, which opens as a link sent to
    /// the app does, in the repository's mirror and never a checkout of it
    /// (`OpenURLPanel`). The panel asks `metab` itself, with the command `resolveLink`
    /// runs, so a refusal is said in the panel, which stays open to fix the text, and not
    /// in the alert at the end of a burst.
    @objc func showOpenURL(_ sender: Any?) {
        openURLWindow.show()
    }

    /// Asks `metab` about a link typed into File > Open URL…, and opens its plan as a
    /// link sent to the app opens (`open(_:with:)`). With no `metab` the app can run now,
    /// as while it finds or checks one, the link goes to the link queue instead, which
    /// waits for one as it waits for any link (`requestLink`): the panel closes, and a
    /// refusal comes as the alert at the end of the burst.
    private func checkEnteredLink(_ link: URL) {
        if let current = selection.setup?.runtime, !selection.isUnverified,
           !current.isCurrent(fingerprint: FileFingerprint.of(current.executable)) {
            beginRecheck()
        }
        guard let setup = operations.launchableSetup() else {
            if let waiting = openURLWindow.handOff() { requestLink(waiting) }
            return
        }
        enteredLinkCheck?.task.cancel()
        let task = Task {
            let answer = await askMetab(about: link, with: setup)
            // Dropped by an edit, Cancel, or closing the panel, which cancelled this task
            // and so killed the dry run (`CommandRunner.finish`): its answer is moot.
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
                  let plan = openURLWindow.answered(answer, for: link, metab: Self.describe(setup))
            else { return }
            await open(plan, with: setup)
            showNextLinkModal()
        }
        enteredLinkCheck = (link, task)
    }

    /// The Open URL… panel no longer awaits the answer about `link`: cancelling its task
    /// kills the dry run's process group at once (`CommandRunner.finish`), so an edit,
    /// Cancel, or a closed panel leaves no `metab` running for it.
    private func stopCheckingEnteredLink(_ link: URL) {
        guard let check = enteredLinkCheck, check.link == link else { return }
        check.task.cancel()
        enteredLinkCheck = nil
    }

    /// Shows `plan` in its repository's window, or in a new session whose server starts on
    /// `plan.link`. A new window loads its server's entry page, which the server resolves
    /// from the link against its mirror, so a ref with a `/` in it opens the right page.
    ///
    /// A repository nobody has said may be cloned is looked up in `metab`'s cache in the
    /// link's turn; one the cache does not hold asks, and its question, with any later
    /// links into it, waits beside the queue, so the links behind it go on (`CloneQuestions`).
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
            if await isCached(root, with: setup) {
                if let link = clones.found(root), !isQuitting { openRepository(root, on: link) }
            } else {
                clones.ask(root)
                showNextLinkModal()
            }
        }
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

    /// The repository's window, whose server starts again on `link`, or a new session whose
    /// server starts on it. Without a runtime accepted now, the link waits for one, and is
    /// resolved again.
    ///
    /// Either is an open, so the repository moves to the front of the recent targets: a
    /// new session's server records it as it starts, and the app records one already open
    /// itself, since starting its server again on a link records nothing
    /// (`FolderServer.restart`).
    private func openRepository(_ root: SessionRoot, on link: URL) {
        if let session = sessions[root.key] as? FolderSession {
            recentFolders.noteOpened(root.url, isOpen: true)
            return session.open(link: link)
        }
        guard selection.setupForOpening(link) != nil, let session = session(for: root, link: link) else {
            if !selection.isBusy { showSettings(nil) }
            return
        }
        folderWindows.place(session.makeWindow())
        Task {
            await session.startServer()
            self.recentFolders.refreshAfterOpen()
        }
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
        let clone = alert.runModal() == .alertSecondButtonReturn
        AppLog.app.info("\(name, privacy: .public): clone \(clone ? "confirmed" : "declined", privacy: .public)")
        return clone
    }

    /// The open session for `root`, or a new one with no window and no server yet; nil
    /// without a runtime or for a folder that cannot be served.
    private func session(for root: URL) -> FolderSession? {
        session(for: .folder(root))
    }

    /// The open session for `root`, or a new one, which starts its server with `link` when
    /// one is given (`FolderSession.init`).
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
        session.onLinkSelectionMissing = { [weak self] missing, link, outcome in
            let name = missing.served.identity().fullName
            if let alert = LinkAlert.selectionMissing(outcome, link: link, repository: name) { self?.noteLinkProblem(alert) }
        }
        session.onAllWindowsClosed = { [weak self] closed in
            self?.sessions.retire(closed)
            self?.folderWindows.folderClosed(closed)
            self?.retitleWindows()
        }
        session.onTitleChange = { [weak self] _ in self?.retitleWindows() }
        session.onWindowShown = { [weak self] folder, controller in
            self?.folderWindows.windowShown(controller, of: folder)
        }
        session.onLayoutChange = { [weak self] in self?.folderWindows.scheduleSave() }
        sessions.insert(session, for: key)
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
        selection.takeWaitingFolders().forEach(request)
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
            switch finish.operation {
            case .search:
                if showPanelAfterDiscovery, sessions.openServers.isEmpty, selection.waitingFolders.isEmpty, linksAreIdle {
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
        case (.choice(let path), .rejected(let rejected)):
            runtimeModel.notice = "\(path) is not a working metab: \(RuntimeView.describe(rejected))."
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
        waiting.forEach(request)
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

    /// Validates the chosen file and uses it, which overtakes a search still running
    /// (`RuntimeOperations.choose`).
    private func adoptChosen(_ path: String) async {
        runtimeModel.notice = nil
        await operations.choose(path)
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

    /// Works out the first-run steps from the last search and what is installed now,
    /// asking uv, when there is one, where it puts `metab`.
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
        let hasHomebrew = RuntimeDiscovery.homebrewBins.contains { FileChecks.isExecutableFile($0 + "/brew") }
        let guide = SetupGuide(
            tried: selection.tried, uv: uv.found, binDirectory: uv.binDirectory, home: env.home,
            loginPath: lastLoginPath, hasHomebrew: hasHomebrew, refusedUv: uv.refused)
        AppLog.app.info(
            "first-run steps: \(guide.steps.map(\.command).joined(separator: "; "), privacy: .public); waiting for metab in \(uv.binDirectory, privacy: .public)"
        )
        runtimeModel.guide = guide
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
        NSWorkspace.shared.open(ProjectLinks.readme)
    }
}
