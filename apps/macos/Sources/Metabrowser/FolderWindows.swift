import AppKit
import ShellCore

/// The folder windows as a whole: where a newly opened folder's window goes, which
/// background tabs keep their pages, and the session saved for the next launch and
/// restored from it.
///
/// The decisions are `ShellCore`'s (`FolderPlacement`, `TabDiscardPolicy`,
/// `RestoreQueue`, `RestoreRun`, `SavedSession`), where they are tested; this class reads
/// the windows and tabs from AppKit and applies them.
final class FolderWindows {
    /// How long a change waits before the session is saved, so a burst of changes, such
    /// as a restore or a run of clicks, writes the file once.
    static let saveDelay = Duration.milliseconds(500)

    let preferences = WindowPreferences()
    private let store: SessionStore
    private let discardPolicy = TabDiscardPolicy()
    private let home = FileChecks.canonicalPath(NSHomeDirectory())
    private let openSessions: () -> [FolderSession]
    private let sessionForPath: (String) -> FolderSession?
    /// When each window was last shown, on `shownCount`.
    private var lastShown: [ObjectIdentifier: UInt64] = [:]
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
        sessionForPath = session
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
        noteShown(controller)
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
        noteShown(controller)
        // A selection starts the folder as the user's choice. A restored start already
        // waiting at the launch gate gets a check that its path still names its folder
        // instead, so one that now leads elsewhere moves its tabs first (`RestoreRun.select`).
        session.launchCheck = nil
        if restoreRun?.select(session.path) == true { startRestoredServers() }
        discardBackgroundPages()
        scheduleSave()
    }

    private func noteShown(_ controller: BrowserWindowController) {
        shownCount += 1
        lastShown[ObjectIdentifier(controller)] = shownCount
    }

    /// Every tab of `session` has closed.
    func folderClosed(_ session: FolderSession) {
        restoreRun?.folderClosed(session.path)
    }

    private func discardBackgroundPages() {
        let controllers = openSessions().flatMap(\.windows)
        let ids = Set(controllers.map(ObjectIdentifier.init))
        lastShown = lastShown.filter { ids.contains($0.key) }
        let tabs = controllers.map { controller in
            TabActivity(
                id: ObjectIdentifier(controller), isBackground: Self.isBackgroundTab(controller.window),
                isLive: !controller.isDiscarded, lastShown: lastShown[ObjectIdentifier(controller)] ?? 0)
        }
        let discards = Set(discardPolicy.discards(tabs))
        for controller in controllers where discards.contains(ObjectIdentifier(controller)) {
            AppLog.app.info("discarding the page of background tab \(controller.window?.title ?? "", privacy: .public)")
            controller.discardPage()
        }
    }

    /// A tab its window is not showing.
    private static func isBackgroundTab(_ window: NSWindow?) -> Bool {
        guard let window, let group = window.tabGroup else { return false }
        return group.windows.count > 1 && group.selectedWindow !== window
    }

    // MARK: - The saved session

    /// The folder windows now, front window first, each with its tabs in tab-bar order.
    func snapshot() -> SavedSession {
        var owners: [ObjectIdentifier: (session: FolderSession, controller: BrowserWindowController)] = [:]
        for session in openSessions() {
            for controller in session.windows {
                if let window = controller.window { owners[ObjectIdentifier(window)] = (session, controller) }
            }
        }
        // orderedWindows lists the windows on screen, front to back; the rest (minimized
        // windows) follow in any order.
        let candidates = NSApp.orderedWindows + openSessions().flatMap(\.windows).compactMap(\.window)
        var seen = Set<ObjectIdentifier>()
        var windows: [SavedWindow] = []
        for window in candidates where owners[ObjectIdentifier(window)] != nil && !seen.contains(ObjectIdentifier(window)) {
            let group = window.tabGroup?.windows ?? [window]
            group.forEach { seen.insert(ObjectIdentifier($0)) }
            let tabs = group.compactMap { owners[ObjectIdentifier($0)] }
            let shown = window.tabGroup?.selectedWindow ?? window
            windows.append(SavedWindow(
                tabs: tabs.map { SavedTab(root: $0.session.path, page: $0.controller.currentPage) },
                selected: tabs.firstIndex { $0.controller.window === shown } ?? 0,
                frame: shown.frameDescriptor))
        }
        return SavedSession(windows: windows)
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
        let session = admitted.session
        if session.tabCount < limited.tabCount {
            AppLog.app.info(
                "not restoring \(limited.tabCount - session.tabCount) tab(s) whose folders are gone or whose saved paths are not canonical")
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
        let queue = RestoreQueue(session, isProtected: admitted.deferred.contains)
        for path in queue.deferred {
            sessionForPath(path)?.windows.forEach { $0.showWaitingForSelection() }
        }
        let run = RestoreRun(
            queue, folder: { [weak self] in self?.sessionForPath($0) },
            admit: { RootAdmission.admit($0, home: home) },
            moveTabs: { [weak self] in self?.moveTabs(of: $0, to: $1, making: makeSession) ?? false })
        run.onEvent = { [weak self] in self?.restoreChanged($0) }
        restoreRun = run
        AppLog.app.info(
            "restoring \(session.windows.count) window(s): \(queue.pending.count) server(s) to start, \(queue.deferred.count) waiting for their tabs")
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
            sessionForPath(path)?.windows.forEach { $0.showWaitingForSelection() }
        case .changedWhileWaiting(let path):
            AppLog.app.info(
                "\(path, privacy: .public) changed while it waited to start; it starts when its tab is selected")
            sessionForPath(path)?.windows.forEach { $0.showWaitingForSelection() }
        case .waitingForRuntime(let pending):
            AppLog.app.info("the restore waits for a metab Metabrowser can run")
            for waiting in pending {
                sessionForPath(waiting)?.windows.forEach { $0.showWaitingForRuntime() }
            }
        case .moved(let saved, let canonical):
            AppLog.app.info(
                "\(saved, privacy: .public) now leads to \(canonical, privacy: .public); its tabs show that folder")
        }
    }

    /// Moves every tab of the folder `saved` to the session of `canonical`, the open one or
    /// a new one (`RestoreRun`): each is replaced in place by a tab of that session showing
    /// the same page, and `saved`'s session, left with no window, closes, which takes it
    /// out of the restore. False if no session can be made for `canonical` now, as without
    /// a runtime, which leaves the tabs as they are.
    private func moveTabs(
        of saved: String, to canonical: String, making makeSession: (URL) -> FolderSession?
    ) -> Bool {
        guard let target = sessionForPath(canonical)
            ?? makeSession(URL(filePath: canonical, directoryHint: .isDirectory))
        else { return false }
        for old in sessionForPath(saved)?.windows ?? [] {
            replace(old, with: target)
        }
        return true
    }

    /// Puts a window of `session`, showing `old`'s page, where `old` is: the tab after it,
    /// selected and key if `old` was. Then closes `old`.
    private func replace(_ old: BrowserWindowController, with session: FolderSession) {
        guard let oldWindow = old.window else { return }
        let page = old.currentPage
        let isShown = !Self.isBackgroundTab(oldWindow)
        let wasKey = oldWindow.isKeyWindow
        let replacement = session.makeWindow(page: page, discarded: !isShown)
        guard let window = replacement.window else { return }
        oldWindow.addTabbedWindow(window, ordered: .above)
        if isShown {
            window.tabGroup?.selectedWindow = window
            // Joining a server that is ready loads nothing by itself. Without a page of its
            // own, the tab shows the folder's own page, the server's entry page.
            replacement.show(page ?? .view(of: ""))
        }
        lastShown[ObjectIdentifier(replacement)] = lastShown[ObjectIdentifier(old)]
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
