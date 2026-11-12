import AppKit
import ShellCore

/// The folder windows as a whole: where a newly opened folder's window goes, which
/// background tabs keep their pages, and the session saved for the next launch and
/// restored from it.
///
/// The decisions are `ShellCore`'s (`FolderPlacement`, `TabDiscardPolicy`,
/// `RestoreQueue`, `SavedSession`), where they are tested; this class reads the windows
/// and tabs from AppKit and applies them.
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
    private var restoreQueue: RestoreQueue?
    private var isStartingRestoredServers = false
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
        // A selection starts the folder as the user's choice, even one already waiting at
        // the launch gate.
        session.launchCheck = nil
        if restoreQueue?.select(session.path) == true { startRestoredServers() }
        discardBackgroundPages()
        scheduleSave()
    }

    private func noteShown(_ controller: BrowserWindowController) {
        shownCount += 1
        lastShown[ObjectIdentifier(controller)] = shownCount
    }

    /// Every tab of `session` has closed.
    func folderClosed(_ session: FolderSession) {
        restoreQueue?.remove(session.path)
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
    ///   or nil if the folder cannot be served.
    func restore(using makeSession: (URL) -> FolderSession?) {
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
        restoreQueue = queue
        AppLog.app.info(
            "restoring \(session.windows.count) window(s): \(queue.pending.count) server(s) to start, \(queue.deferred.count) waiting for their tabs")
        front?.window?.makeKeyAndOrderFront(nil)
        startRestoredServers()
    }

    /// Starts the restored folders' servers one at a time, each after the one before it is
    /// ready or has failed, while the restore queue has any.
    private func startRestoredServers() {
        guard !isStartingRestoredServers else { return }
        isStartingRestoredServers = true
        Task {
            while let path = nextRestoredRoot() {
                guard let session = sessionForPath(path) else { continue }
                if await !session.startServer() {
                    restoreQueue?.hold(path)
                    AppLog.app.info(
                        "\(path, privacy: .public) changed while it waited to start; it starts when its tab is selected")
                    session.windows.forEach { $0.showWaitingForSelection() }
                }
            }
            isStartingRestoredServers = false
        }
    }

    /// The next root to start. A background root is admitted again now, since it can
    /// change while the servers before it start, and once more just before its server
    /// spawns, since it can change while it waits at the launch gate; one that no longer
    /// is admitted waits for its tab. A selected root is not checked.
    private func nextRestoredRoot() -> String? {
        let home = self.home
        let waiting = Set(restoreQueue?.deferred ?? [])
        let next = restoreQueue?.next { RootAdmission.admit($0, home: home) == .open($0) }
        for path in restoreQueue?.deferred ?? [] where !waiting.contains(path) {
            AppLog.app.info(
                "\(path, privacy: .public) changed since the launch admitted it; it starts when its tab is selected")
            sessionForPath(path)?.windows.forEach { $0.showWaitingForSelection() }
        }
        if let next, let session = sessionForPath(next) {
            session.launchCheck = restoreQueue?.selected.contains(next) == true
                ? nil : { RootAdmission.admit(next, home: home) == .open(next) }
        }
        return next
    }
}
