import AppKit
import ShellCore

/// The folder windows as a whole: where a newly opened folder's window goes, which
/// folder a window switches to and what becomes of the one it leaves, which background
/// pages keep their web views, and the session saved for the next launch and restored
/// from it.
///
/// The decisions are `ShellCore`'s (`FolderPlacement`, `OpenFolders`,
/// `SwitchedAwayPage`, `TabDiscardPolicy`, `RestoreQueue`, `RestoreRun`,
/// `SavedSession`), where they are tested; this class reads the windows, tabs, and pages
/// from AppKit and applies them.
final class FolderWindows {
    /// How long a change waits before the session is saved, so a burst of changes, such
    /// as a restore or a run of clicks, writes the file once.
    static let saveDelay = Duration.milliseconds(500)

    let preferences = WindowPreferences()
    private let store: SessionStore
    private let discardPolicy = TabDiscardPolicy()
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

    // MARK: - Placement

    /// Shows a newly opened folder's first window as a tab of the front folder window or
    /// as a window of its own, as Settings says.
    func place(_ controller: BrowserWindowController) {
        guard let window = controller.window else { return }
        let front = NSApp.orderedWindows.first {
            $0 !== window && $0.isVisible && $0.windowController is BrowserWindowController
        }
        let frontKind = front.map { $0.styleMask.contains(.fullScreen) ? FrontWindow.fullScreen : .window }
        switch preferences.placement.placement(system: Self.systemTabbing, front: frontKind) {
        case .tab:
            front?.addTabbedWindow(window, ordered: .above)
            window.makeKeyAndOrderFront(nil)
        case .window:
            Self.orderInAlone(window)
            window.makeKeyAndOrderFront(nil)
        }
        // Shown now even if the app is not active and the window does not become key, as
        // when a folder arrives from `open -a` while another app is in front.
        noteShown(controller.page)
        if let session = controller.page.session { openFolders.show(session.path) }
        discardBackgroundPages()
    }

    /// System Settings > Desktop & Dock > "Prefer tabs when opening documents".
    static var systemTabbing: SystemTabbing {
        switch NSWindow.userTabbingPreference {
        case .always: .always
        case .inFullScreen: .inFullScreen
        case .manual: .never
        @unknown default: .never
        }
    }

    /// Orders `window` in without a tab bar. With automatic tabbing, AppKit itself adds a
    /// window being ordered in to the key window's tabs when System Settings prefers tabs;
    /// tabbing is disallowed for that moment only, so the window can still be merged
    /// later with Merge All Windows or by dragging its tab.
    private static func orderInAlone(_ window: NSWindow) {
        window.tabbingMode = .disallowed
        window.orderFront(nil)
        window.tabbingMode = .automatic
    }

    // MARK: - Shown tabs and discarded pages

    /// A folder window became key, which is how a tab is selected: it counts as shown,
    /// its server starts if a restore was holding it, and background tabs past the limit
    /// give up their pages.
    func windowShown(_ controller: BrowserWindowController, of session: FolderSession) {
        noteShown(controller.page)
        openFolders.show(session.path)
        // A selection starts the folder as the user's choice. A restored start already
        // waiting at the launch gate gets a check that its path still names its folder
        // instead, so one that now leads elsewhere moves its tabs first (`RestoreRun.select`).
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

    /// Pages no window shows, of folders in the background, and the background tabs past
    /// the policy's limit give up their web views, least recently shown first.
    private func discardBackgroundPages() {
        let pages = openSessions().flatMap(\.pages)
        let ids = Set(pages.map(ObjectIdentifier.init))
        lastShown = lastShown.filter { ids.contains($0.key) }
        let activity = pages.map { page in
            TabActivity(
                id: ObjectIdentifier(page), isBackground: Self.isInBackground(page), isLive: !page.isDiscarded,
                lastShown: lastShown[ObjectIdentifier(page)] ?? 0)
        }
        let discards = Set(discardPolicy.discards(activity))
        for page in pages where discards.contains(ObjectIdentifier(page)) {
            let name = page.session?.folderName ?? ""
            AppLog.app.info("discarding the background page of \(name, privacy: .public)")
            page.discardPage()
        }
    }

    /// A page no window is showing: a background tab, or a folder's page in the background.
    private static func isInBackground(_ page: FolderPage) -> Bool {
        guard let window = page.host?.window else { return true }
        return isBackgroundTab(window)
    }

    // MARK: - Switching and closing folders

    /// Shows `session` in `controller`'s window in place of the folder it shows: the
    /// folder's page in the background if it has one, else a new page of it. The page the
    /// window leaves stays open in the background, or closes if its folder has another
    /// page (`SwitchedAwayPage`).
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
            // the user's choice; a hidden tab does that once it is selected.
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
            id: ObjectIdentifier(controller), isOnScreen: !isBackgroundTab(controller.window),
            hasSheet: controller.window?.attachedSheet != nil)
    }

    /// `controllers` in the order their windows stand on screen, front first; hidden tabs
    /// and minimized windows follow, in the order given.
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
                key: key, title: session.windowTitle, location: session.location, mark: RootMark(session.served),
                shown: shown)
        }
    }

    /// Closes every folder open in the background.
    func closeBackgroundFolders() {
        for session in openSessions() where session.isInBackground {
            session.pages.forEach { $0.close() }
        }
    }

    /// A tab its window is not showing.
    private static func isBackgroundTab(_ window: NSWindow?) -> Bool {
        guard let window, let group = window.tabGroup else { return false }
        return group.windows.count > 1 && group.selectedWindow !== window
    }

    // MARK: - The saved session

    /// The folder windows now, front window first, each with its tabs in tab-bar order,
    /// then the folders open in the background, the one shown most recently first.
    ///
    /// A repository's tabs are left out, and so is a window that holds no other: the saved
    /// session names folders by path (`SavedTab.root`), and its restore admits each path
    /// again (`RootAdmission`), which a repository's URL is not. A window whose shown tab
    /// is a repository's is saved, in its place among the windows, showing its first
    /// folder tab: a tab group is on screen as its shown window, so a group is kept when any
    /// of its windows is a folder's.
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
        for window in candidates where !seen.contains(ObjectIdentifier(window)) {
            let group = window.tabGroup?.windows ?? [window]
            guard group.contains(where: { owners[ObjectIdentifier($0)] != nil }) else { continue }
            group.forEach { seen.insert(ObjectIdentifier($0)) }
            let tabs = group.compactMap { owners[ObjectIdentifier($0)] }
            let shown = window.tabGroup?.selectedWindow ?? window
            windows.append(SavedWindow(
                tabs: tabs.map { SavedTab(root: $0.session.path, page: $0.controller.page.currentPage) },
                selected: tabs.firstIndex { $0.controller.window === shown } ?? 0,
                frame: shown.frameDescriptor))
        }
        let background = openFolders.byRecency.compactMap { path -> SavedTab? in
            guard let session = sessionForKey(path), session.isLocal, session.isInBackground,
                  let page = session.pages.first
            else { return nil }
            return SavedTab(root: session.path, page: page.currentPage)
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

    /// Recreates the last session's windows and tabs, unless Settings turned that off,
    /// and starts their servers one at a time, front tab first (`RestoreQueue`). Only
    /// each window's shown tab loads its page; the others load when they are shown.
    ///
    /// - Parameter makeSession: the folder's session, made without a window or a server,
    ///   or nil if the folder cannot be served or there is no runtime; also asked, later,
    ///   for the folder a selected tab's saved path leads to (`RestoreRun`).
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
        if limited.tabCount < saved.tabCount {
            AppLog.app.error(
                "the saved session has \(saved.windows.count) window(s) and \(saved.tabCount) tab(s); restoring the front \(limited.windows.count) and \(limited.tabCount), the restore budget")
        }
        let home = self.home
        let admitted = limited.admitted { RootAdmission.admit($0, home: home) }
        // A session left with folders in the background and no window shows one of them.
        let session = admitted.session.withFrontWindow
        if session.tabCount < limited.tabCount {
            AppLog.app.info(
                "not restoring \(limited.tabCount - session.tabCount) tab(s) whose folders are gone or whose saved paths are not canonical")
        }
        // Sessions first, so the folders open in the order the windows stand in, then the
        // background folders' (`SavedSession.roots`); the windows are then built back to front.
        for root in session.roots {
            _ = makeSession(URL(filePath: root, directoryHint: .isDirectory))
        }
        var front: BrowserWindowController?
        // Back to front, so that each window ordered in lands in front of the ones behind it.
        for (index, savedWindow) in session.windows.enumerated().reversed() {
            var tabs: [BrowserWindowController] = []
            var shown: BrowserWindowController?
            for (tabIndex, tab) in savedWindow.tabs.enumerated() {
                guard let folder = makeSession(URL(filePath: tab.root, directoryHint: .isDirectory)) else {
                    AppLog.app.error("not restoring a tab of \(tab.root, privacy: .public): it cannot be served")
                    continue
                }
                let isShown = tabIndex == savedWindow.selected
                let controller = folder.makeWindow(page: tab.page, discarded: !isShown)
                tabs.append(controller)
                if isShown { shown = controller }
            }
            guard let first = tabs.first?.window else { continue }
            if let frame = savedWindow.frame { first.setFrame(from: frame) }
            Self.orderInAlone(first)
            var previous = first
            for window in tabs.dropFirst().compactMap(\.window) {
                previous.addTabbedWindow(window, ordered: .above)
                previous = window
            }
            let shownTab = shown ?? tabs[0]
            if let window = shownTab.window { first.tabGroup?.selectedWindow = window }
            if index == 0 { front = shownTab }
        }
        // Folders in the background reopen with a page each and no window; each starts
        // when a window first shows it (`RestoreQueue`).
        for tab in session.background {
            guard let folder = makeSession(URL(filePath: tab.root, directoryHint: .isDirectory)) else {
                AppLog.app.error("not restoring \(tab.root, privacy: .public) in the background: it cannot be served")
                continue
            }
            _ = folder.makePage(page: tab.page, discarded: true)
        }
        let queue = RestoreQueue(session, isProtected: admitted.deferred.contains)
        for path in queue.deferred {
            sessionForKey(path)?.pages.forEach { $0.showWaitingForSelection() }
        }
        let run = RestoreRun(
            queue, folder: { [weak self] in self?.sessionForKey($0) },
            admit: { RootAdmission.admit($0, home: home) },
            moveTabs: { [weak self] in self?.moveTabs(of: $0, to: $1, making: makeSession) ?? false })
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
                "\(path, privacy: .public) changed since the launch admitted it; it starts when its tab is selected")
            sessionForKey(path)?.pages.forEach { $0.showWaitingForSelection() }
        case .changedWhileWaiting(let path):
            AppLog.app.info(
                "\(path, privacy: .public) changed while it waited to start; it starts when its tab is selected")
            sessionForKey(path)?.pages.forEach { $0.showWaitingForSelection() }
        case .waitingForRuntime(let pending):
            AppLog.app.info("the restore waits for a metab Metabrowser can run")
            for waiting in pending {
                sessionForKey(waiting)?.pages.forEach { $0.showWaitingForRuntime() }
            }
        case .moved(let saved, let canonical):
            AppLog.app.info(
                "\(saved, privacy: .public) now leads to \(canonical, privacy: .public); its tabs show that folder")
        }
    }

    /// Moves every page of the folder `saved` to the session of `canonical`, the open one or
    /// a new one (`RestoreRun`), as `MovedPage` decides: a page a window shows is replaced
    /// in place by a tab of that session showing the same page, and a page in the
    /// background by a page of that session in the background, unless it has a page there
    /// or is shown. `saved`'s session, left with no page, closes, which takes it out of the
    /// restore. False if no session can be made for `canonical` now, as without a runtime,
    /// which leaves the pages as they are.
    private func moveTabs(
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

    /// Puts a window of `session`, at the address of `old`'s page, where `old` is: the tab
    /// after it, selected and key if `old` was. Then closes `old`.
    private func replace(_ old: BrowserWindowController, with session: FolderSession) {
        guard let oldWindow = old.window else { return }
        let address = old.page.currentPage
        let isShown = !Self.isBackgroundTab(oldWindow)
        let wasKey = oldWindow.isKeyWindow
        let replacement = session.makeWindow(page: address, discarded: !isShown)
        guard let window = replacement.window else { return }
        oldWindow.addTabbedWindow(window, ordered: .above)
        if isShown {
            window.tabGroup?.selectedWindow = window
            // Joining a server that is ready loads nothing by itself. Without a page of its
            // own, the tab shows the folder's own page, the server's entry page.
            replacement.page.show(address ?? .view(of: ""))
        }
        lastShown[ObjectIdentifier(replacement.page)] = lastShown[ObjectIdentifier(old.page)]
        if wasKey { window.makeKeyAndOrderFront(nil) }
        oldWindow.close()
    }

    /// A restored folder's restart, such as Restart Server or the one after an upgrade, was
    /// refused by its root check (`RestoreRun.rootRefused`): a selected one is resolved at
    /// once, which moves its tabs to the folder its path now leads to.
    func rootRefused(_ session: FolderSession) {
        if restoreRun?.rootRefused(session.path) == true { startRestoredServers() }
    }

    /// A runtime was accepted: a restore that paused for want of one carries on.
    func runtimeAccepted() {
        if restoreRun?.runtimeAccepted() == true { startRestoredServers() }
    }
}

extension FolderSession: RestoredFolder {}
