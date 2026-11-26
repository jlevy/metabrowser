import AppKit
import ShellCore

/// The folder windows as a whole: a newly opened folder's window, which folder a window
/// switches to and what becomes of the one it leaves, which background pages keep their
/// web views, and the session saved for the next launch and restored from it.
///
/// Every folder opens in a window of its own, and no folder window takes tabs
/// (`BrowserWindowController`). The decisions are `ShellCore`'s (`OpenFolders`,
/// `SwitchedAwayPage`, `PageDiscardPolicy`, `RestoreQueue`, `RestoreRun`, `SavedSession`),
/// where they are tested; this class reads the windows and pages from AppKit and applies
/// them.
final class FolderWindows {
    /// How long a change waits before the session is saved, so a burst of changes, such
    /// as a restore or a run of clicks, writes the file once.
    static let saveDelay = Duration.milliseconds(500)

    let preferences = WindowPreferences()
    private let store: SessionStore
    private let discardPolicy = PageDiscardPolicy()
    private let home = FileChecks.canonicalPath(NSHomeDirectory())
    private let openSessions: () -> [FolderSession]
    /// The open session by its key (`FolderSession.path`, `SessionRoot.key`), which every
    /// key `OpenFolders` and the restore hold names, a repository's included.
    private let sessionForKey: (String) -> FolderSession?
    /// When each page was last shown, on `shownCount`.
    private var lastShown: [ObjectIdentifier: UInt64] = [:]
    /// The open folders, by session key, in the order they opened and by when each was
    /// last shown.
    private(set) var openFolders = OpenFolders()
    private var shownCount: UInt64 = 0
    /// The restore's server starts, while it has roots to start.
    private var restoreRun: RestoreRun?
    private var pendingSave: Task<Void, Never>?
    /// Saving starts once the last session has been restored or passed over, so a quit
    /// before then cannot replace it with an empty one, and stops at the quit's save, so
    /// the windows closing after it cannot either.
    private var isRecording = false

    init(
        store: SessionStore, openSessions: @escaping () -> [FolderSession],
        session: @escaping (String) -> FolderSession?
    ) {
        self.store = store
        self.openSessions = openSessions
        sessionForKey = session
    }

    // MARK: - New windows

    /// Shows a folder's new window, a window of its own: every window a folder gets comes
    /// here, apart from the restore's (`restore(using:)`). Folder windows take no tabs
    /// (`BrowserWindowController`), so nothing joins it to another window.
    func place(_ controller: BrowserWindowController) {
        guard let window = controller.window else { return }
        window.makeKeyAndOrderFront(nil)
        // Shown now even if the app is not active and the window does not become key, as
        // when a folder arrives from `open -a` while another app is in front.
        noteShown(controller.page)
        if let session = controller.page.session { openFolders.show(session.path) }
        discardBackgroundPages()
    }

    // MARK: - Shown windows and discarded pages

    /// A folder window became key, which is how the user brings one forward: it counts as
    /// shown, its server starts if a restore was holding it, and background pages past the
    /// limit give up their web views.
    func windowShown(_ controller: BrowserWindowController, of session: FolderSession) {
        noteShown(controller.page)
        openFolders.show(session.path)
        // Bringing it forward starts the folder as the user's choice. A restored start
        // already waiting at the launch gate gets a check that its path still names its
        // folder instead, so one that now leads elsewhere moves its pages first
        // (`RestoreRun.select`).
        session.launchCheck = nil
        if restoreRun?.select(session.path) == true { startRestoredServers() }
        discardBackgroundPages()
        scheduleSave()
    }

    private func noteShown(_ page: FolderPage) {
        shownCount += 1
        lastShown[ObjectIdentifier(page)] = shownCount
    }

    /// A session was made for a folder the user opened, or a restore reopened.
    func folderOpened(_ session: FolderSession) {
        openFolders.open(session.path)
    }

    /// The open folder a click on the Dock icon brings forward when no window is on
    /// screen: the one shown most recently, which may be minimized or in the background.
    func mostRecentFolder() -> FolderSession? {
        openFolders.byRecency.lazy.compactMap(sessionForKey).first { !$0.pages.isEmpty }
    }

    /// Every page of `session` has closed.
    func folderClosed(_ session: FolderSession) {
        restoreRun?.folderClosed(session.path)
        openFolders.close(session.path)
        scheduleSave()
    }

    /// The pages of folders in the background, which no window shows, past the policy's
    /// limit give up their web views, least recently shown first. A page a window shows,
    /// minimized or not, keeps its own.
    private func discardBackgroundPages() {
        let pages = openSessions().flatMap(\.pages)
        let ids = Set(pages.map(ObjectIdentifier.init))
        lastShown = lastShown.filter { ids.contains($0.key) }
        let activity = pages.map { page in
            PageActivity(
                id: ObjectIdentifier(page), isBackground: page.host?.window == nil, isLive: !page.isDiscarded,
                lastShown: lastShown[ObjectIdentifier(page)] ?? 0)
        }
        let discards = Set(discardPolicy.discards(activity))
        for page in pages where discards.contains(ObjectIdentifier(page)) {
            let name = page.session?.folderName ?? ""
            AppLog.app.info("discarding the background page of \(name, privacy: .public)")
            page.discardPage()
        }
    }

    // MARK: - Switching and closing folders

    /// Shows `session` in `controller`'s window in place of the folder it shows: the
    /// folder's page in the background if it has one, else a new page of it. The page the
    /// window leaves stays open in the background, or closes if its folder has another
    /// page (`SwitchedAwayPage`).
    /// A new page opens at `address`, if one is given.
    ///
    /// Every switch comes through here, and this is where a window with a sheet open
    /// refuses one (`FolderSwitch.refused`): it beeps, keeps its page, and returns false.
    /// It returns true once the window shows `session`.
    @discardableResult
    func switchWindow(
        _ controller: BrowserWindowController, to session: FolderSession, page address: PageAddress? = nil
    ) -> Bool {
        let old = controller.page
        let decision = FolderSwitch.decide(
            Self.switching(controller), showsFolder: old.session === session,
            leftFolderPages: old.session?.pages.count ?? 1)
        switch decision {
        case .alreadyShown:
            return true
        case .refused:
            AppLog.app.info("not switching a window to \(session.folderName, privacy: .public): a sheet is open on it")
            NSSound.beep()
            return false
        case .show(let left, let countsAsShown):
            let page = session.backgroundPage ?? session.makePage(page: address)
            controller.show(page)
            switch left {
            case .keepInBackground:
                AppLog.app.info("\(old.session?.folderName ?? "", privacy: .public) stays open in the background")
            case .close:
                old.close()
            }
            // Counting it as shown revives a discarded page and starts a restored folder as
            // the user's choice; a minimized window does that once it is brought back.
            if countsAsShown { page.shown() }
            discardBackgroundPages()
            scheduleSave()
            return true
        }
    }

    /// File > Close Folder: every window showing `session` switches to a folder in the
    /// background, the one shown most recently first, or closes if none is left, and the
    /// folder's pages close, which stops its server (`OpenFolders.closing`). A sheet open on
    /// any of those windows holds it all up: it beeps, closes nothing, and returns false.
    @discardableResult
    func closeFolder(_ session: FolderSession) -> Bool {
        let controllers = Self.frontToBack(session.windows)
        let open = Dictionary(openSessions().map { ($0.path, $0) }, uniquingKeysWith: { first, _ in first })
        let background = Set(open.values.filter(\.isInBackground).map(\.path))
        switch openFolders.closing(session.path, windows: controllers.map(Self.switching), background: background) {
        case .refused(let blocked):
            AppLog.app.info(
                "not closing \(session.folderName, privacy: .public): a sheet is open on \(blocked.count) of its windows")
            NSSound.beep()
            return false
        case .steps(let steps):
            let byID = Dictionary(uniqueKeysWithValues: controllers.map { (ObjectIdentifier($0), $0) })
            for step in steps {
                guard let controller = byID[step.window] else { continue }
                if let key = step.showing, let next = open[key] {
                    switchWindow(controller, to: next)
                } else {
                    controller.window?.close()
                }
            }
            session.pages.forEach { $0.close() }
            return true
        }
    }

    /// `controller`'s window as a switch sees it.
    private static func switching(_ controller: BrowserWindowController) -> SwitchingWindow<ObjectIdentifier> {
        SwitchingWindow(
            id: ObjectIdentifier(controller), isOnScreen: controller.window?.isMiniaturized != true,
            hasSheet: controller.window?.attachedSheet != nil)
    }

    /// `controllers` in the order their windows stand on screen, front first; minimized
    /// windows follow, in the order given.
    private static func frontToBack(_ controllers: [BrowserWindowController]) -> [BrowserWindowController] {
        let rank = Dictionary(
            NSApp.orderedWindows.enumerated().map { (ObjectIdentifier($1), $0) }, uniquingKeysWith: { first, _ in first })
        let ranked = controllers.enumerated().map { offset, controller in
            (controller, controller.window.flatMap { rank[ObjectIdentifier($0)] } ?? Int.max, offset)
        }
        return ranked.sorted { ($0.1, $0.2) < ($1.1, $1.2) }.map(\.0)
    }

    /// The open folders in the order they opened, as `controller`'s window sees each, for
    /// its folder chooser (`FolderChooser`). A folder whose session has no page yet, as
    /// during a restore, is left out.
    func chooserFolders(for controller: BrowserWindowController) -> [FolderChooser.OpenFolder] {
        let sessions = Dictionary(openSessions().map { ($0.path, $0) }, uniquingKeysWith: { first, _ in first })
        return openFolders.inOrderOpened.compactMap { key in
            guard let session = sessions[key], !session.pages.isEmpty else { return nil }
            let shown: FolderChooser.Shown =
                session.pages.contains { $0.host === controller } ? .here
                : session.isInBackground ? .background : .inAnotherWindow
            return FolderChooser.OpenFolder(
                key: key, title: session.windowTitle, location: session.location,
                mark: RootMark(session.title.identity.kind), shown: shown)
        }
    }

    /// Closes every folder open in the background.
    func closeBackgroundFolders() {
        for session in openSessions() where session.isInBackground {
            session.pages.forEach { $0.close() }
        }
    }

    // MARK: - The saved session

    /// The folder windows now, front first, each with its page, then the folders open in
    /// the background, the one shown most recently first.
    ///
    /// A repository's windows are left out: the saved session names folders by path
    /// (`SavedPage.root`), and its restore admits each path again (`RootAdmission`), which
    /// a repository's URL is not.
    func snapshot() -> SavedSession {
        var owners: [ObjectIdentifier: (session: FolderSession, controller: BrowserWindowController)] = [:]
        for session in openSessions() where session.isLocal {
            for controller in session.windows {
                if let window = controller.window { owners[ObjectIdentifier(window)] = (session, controller) }
            }
        }
        // orderedWindows lists the windows on screen, front to back; the rest (minimized
        // windows) follow in any order.
        let candidates = NSApp.orderedWindows + openSessions().flatMap(\.windows).compactMap(\.window)
        var seen = Set<ObjectIdentifier>()
        var windows: [SavedWindow] = []
        for window in candidates {
            guard seen.insert(ObjectIdentifier(window)).inserted, let owner = owners[ObjectIdentifier(window)] else {
                continue
            }
            windows.append(SavedWindow(
                pages: [SavedPage(root: owner.session.path, page: owner.controller.page.currentPage)],
                selected: 0, frame: window.frameDescriptor))
        }
        let background = openFolders.byRecency.compactMap { path -> SavedPage? in
            guard let session = sessionForKey(path), session.isLocal, session.isInBackground,
                  let page = session.pages.first
            else { return nil }
            return SavedPage(root: session.path, page: page.currentPage)
        }
        return SavedSession(windows: windows, background: background)
    }

    func scheduleSave() {
        guard isRecording else { return }
        pendingSave?.cancel()
        pendingSave = Task { [weak self] in
            do {
                try await Task.sleep(for: Self.saveDelay)
            } catch {
                return  // cancelled by a newer change, which saves instead
            }
            self?.save()
        }
    }

    /// The quit's save, before the servers stop and the windows close.
    func saveForQuit() {
        guard isRecording else { return }
        pendingSave?.cancel()
        save()
        isRecording = false
    }

    private func save() {
        do {
            try store.save(snapshot())
        } catch {
            // The next launch then restores the session saved before this one. Nothing in
            // this session depends on the file, so there is nothing to undo here.
            AppLog.app.error(
                "could not save the session to \(self.store.url.path(percentEncoded: false), privacy: .public): \(error, privacy: .public)")
        }
    }

    // MARK: - Restore

    /// Recreates the last session's windows, unless Settings turned that off, and starts
    /// their servers one at a time, the front window's first (`RestoreQueue`).
    ///
    /// Every saved page opens in a window of its own. This build saves one page per
    /// window; a window an earlier build saved with several folders in its tabs reopens as
    /// one window per tab: the one it showed at its frame and in front, the others placed
    /// behind it as new windows are, each loading its page once it is brought forward.
    ///
    /// - Parameter makeSession: the folder's session, made without a window or a server,
    ///   or nil if the folder cannot be served or there is no runtime; also asked, later,
    ///   for the folder a selected window's saved path leads to (`RestoreRun`).
    func restore(using makeSession: @escaping (URL) -> FolderSession?) {
        defer { isRecording = true }
        guard preferences.restoresLastSession else { return }
        let saved: SavedSession
        do {
            guard let loaded = try store.load() else { return }
            saved = loaded
        } catch {
            // The next save replaces the unreadable file with the windows of this launch.
            AppLog.app.error(
                "could not read the saved session at \(self.store.url.path(percentEncoded: false), privacy: .public), so none is restored: \(error, privacy: .public)")
            return
        }
        // Cut to the budget before anything is resolved or built, then resolve each root
        // again: the file may have been edited, and a folder replaced by a link.
        let limited = saved.limited(to: .standard)
        if limited.pageCount < saved.pageCount {
            AppLog.app.error(
                "the saved session has \(saved.windows.count) window(s) and \(saved.pageCount) page(s); restoring the front \(limited.windows.count) and \(limited.pageCount), the restore budget")
        }
        let home = self.home
        let admitted = limited.admitted { RootAdmission.admit($0, home: home) }
        // A session left with folders in the background and no window shows one of them.
        let session = admitted.session.withFrontWindow
        if session.pageCount < limited.pageCount {
            AppLog.app.info(
                "not restoring \(limited.pageCount - session.pageCount) page(s) whose folders are gone or whose saved paths are not canonical")
        }
        // Sessions first, so the folders open in the order the windows stand in, then the
        // background folders' (`SavedSession.roots`); the windows are then built back to front.
        for root in session.roots {
            _ = makeSession(URL(filePath: root, directoryHint: .isDirectory))
        }
        var front: BrowserWindowController?
        // Back to front, so that each window ordered in lands in front of the ones behind it.
        for (index, savedWindow) in session.windows.enumerated().reversed() {
            var made: [BrowserWindowController] = []
            var shown: BrowserWindowController?
            for (pageIndex, saved) in savedWindow.pages.enumerated() {
                guard let folder = makeSession(URL(filePath: saved.root, directoryHint: .isDirectory)) else {
                    AppLog.app.error("not restoring a window of \(saved.root, privacy: .public): it cannot be served")
                    continue
                }
                let isShown = pageIndex == savedWindow.selected
                let controller = folder.makeWindow(page: saved.page, discarded: !isShown)
                made.append(controller)
                if isShown { shown = controller }
            }
            guard let lead = shown ?? made.first else { continue }
            if let frame = savedWindow.frame { lead.window?.setFrame(from: frame) }
            for controller in made where controller !== lead { controller.window?.orderFront(nil) }
            lead.window?.orderFront(nil)
            if index == 0 { front = lead }
        }
        // Folders in the background reopen with a page each and no window; each starts
        // when a window first shows it (`RestoreQueue`).
        for saved in session.background {
            guard let folder = makeSession(URL(filePath: saved.root, directoryHint: .isDirectory)) else {
                AppLog.app.error("not restoring \(saved.root, privacy: .public) in the background: it cannot be served")
                continue
            }
            _ = folder.makePage(page: saved.page, discarded: true)
        }
        let queue = RestoreQueue(session, isProtected: admitted.deferred.contains)
        for path in queue.deferred {
            sessionForKey(path)?.pages.forEach { $0.showWaitingForSelection() }
        }
        let run = RestoreRun(
            queue, folder: { [weak self] in self?.sessionForKey($0) },
            admit: { RootAdmission.admit($0, home: home) },
            movePages: { [weak self] in self?.movePages(of: $0, to: $1, making: makeSession) ?? false })
        run.onEvent = { [weak self] in self?.restoreChanged($0) }
        restoreRun = run
        AppLog.app.info(
            "restoring \(session.windows.count) window(s) and \(session.background.count) folder(s) in the background: \(queue.pending.count) server(s) to start, \(queue.deferred.count) waiting to be shown")
        front?.window?.makeKeyAndOrderFront(nil)
        startRestoredServers()
    }

    /// Starts the restored folders' servers one at a time (`RestoreRun.start`), unless a
    /// run is going, which picks up what changed.
    private func startRestoredServers() {
        guard let restoreRun else { return }
        Task { await restoreRun.start() }
    }

    /// What the restore's windows show, and the log says.
    private func restoreChanged(_ event: RestoreRun.Event) {
        switch event {
        case .changedBeforeItsTurn(let path):
            AppLog.app.info(
                "\(path, privacy: .public) changed since the launch admitted it; it starts when its window is brought forward")
            sessionForKey(path)?.pages.forEach { $0.showWaitingForSelection() }
        case .changedWhileWaiting(let path):
            AppLog.app.info(
                "\(path, privacy: .public) changed while it waited to start; it starts when its window is brought forward")
            sessionForKey(path)?.pages.forEach { $0.showWaitingForSelection() }
        case .waitingForRuntime(let pending):
            AppLog.app.info("the restore waits for a metab Metabrowser can run")
            for waiting in pending {
                sessionForKey(waiting)?.pages.forEach { $0.showWaitingForRuntime() }
            }
        case .moved(let saved, let canonical):
            AppLog.app.info(
                "\(saved, privacy: .public) now leads to \(canonical, privacy: .public); its windows show that folder")
        }
    }

    /// Moves every page of the folder `saved` to the session of `canonical`, the open one or
    /// a new one (`RestoreRun`), as `MovedPage` decides: a page a window shows is replaced
    /// in that window by a page of that session at the same address, and a page in the
    /// background by a page of that session in the background, unless it has a page there
    /// or is shown. `saved`'s session, left with no page, closes, which takes it out of the
    /// restore. False if no session can be made for `canonical` now, as without a runtime,
    /// which leaves the pages as they are.
    private func movePages(
        of saved: String, to canonical: String, making makeSession: (URL) -> FolderSession?
    ) -> Bool {
        guard let target = sessionForKey(canonical)
            ?? makeSession(URL(filePath: canonical, directoryHint: .isDirectory))
        else { return false }
        let pages = sessionForKey(saved)?.pages ?? []
        // Captured first: the pages that move in add none the plan closes.
        let targetBackground = target.pages.filter { $0.host == nil }
        let plan = MovedPage.plan(pages.map { $0.host != nil }, into: target.pages.map { $0.host != nil })
        for (page, fate) in zip(pages, plan.pages) {
            switch fate {
            case .replaceInWindow:
                if let host = page.host { replace(host, with: target) }
            case .moveToBackground:
                let moved = target.makePage(page: page.currentPage, discarded: true)
                lastShown[ObjectIdentifier(moved)] = lastShown[ObjectIdentifier(page)]
                page.close()
            case .close:
                page.close()
            }
        }
        // After the moves, so the target, shown now, never closes on the way.
        if plan.closesTargetBackgroundPages { targetBackground.forEach { $0.close() } }
        return true
    }

    /// Shows a page of `session` in `controller`'s window, at the address of the page the
    /// window shows, in that page's place, and closes that page. The window keeps its frame,
    /// Space, and full screen, and counts as shown again if it is key.
    private func replace(_ controller: BrowserWindowController, with session: FolderSession) {
        let old = controller.page
        let address = old.currentPage
        let page = session.makePage(page: address)
        controller.show(page)
        // Joining a server that is ready loads nothing by itself. Without a page of its
        // own, the window shows the folder's own page, the server's entry page.
        page.show(address ?? .view(of: ""))
        lastShown[ObjectIdentifier(page)] = lastShown[ObjectIdentifier(old)]
        old.close()
        if controller.window?.isKeyWindow == true { page.shown() }
    }

    /// A restored folder's restart, such as Restart Server or the one after an upgrade, was
    /// refused by its root check (`RestoreRun.rootRefused`): a selected one is resolved at
    /// once, which moves its pages to the folder its path now leads to.
    func rootRefused(_ session: FolderSession) {
        if restoreRun?.rootRefused(session.path) == true { startRestoredServers() }
    }

    /// A runtime was accepted: a restore that paused for want of one carries on.
    func runtimeAccepted() {
        if restoreRun?.runtimeAccepted() == true { startRestoredServers() }
    }
}

extension FolderSession: RestoredFolder {}
