/// What a folder window shows in place of its page: the server is starting, it failed
/// and here is why, it waits to be brought forward or for a `metab` the app can run, or
/// a discarded page reloads. The app's `StatusView` draws it.
public nonisolated enum WindowPhase: Equatable, Sendable {
    case starting
    case failed(ServerFailure)
    /// A restored folder in a protected location, whose server starts only once its window
    /// is brought forward, so that a launch raises no privacy prompt for it.
    case waitingForSelection
    /// A start waiting for a `metab` the app accepts.
    case waitingForRuntime
    /// A page that gave up its web view loads it again from the running server.
    case reloading
}

/// A folder window, as its menu items see it.
public nonisolated struct FolderWindowState: Equatable, Sendable {
    /// What the status view says, when it covers the page.
    public var phase: WindowPhase
    /// The page is on screen: the status view does not cover it.
    public var showsPage: Bool
    /// The web view has a page it can reload: one that committed and is still its current
    /// history entry. A fresh view, such as a discarded page's, has none, and nor has a
    /// window WebKit opened whose first load has not committed.
    public var hasPage: Bool
    /// The folder's server is ready, so the window can load a page from it.
    public var serverReady: Bool
    public var canGoBack: Bool
    public var canGoForward: Bool

    public init(
        phase: WindowPhase, showsPage: Bool, hasPage: Bool, serverReady: Bool, canGoBack: Bool = false,
        canGoForward: Bool = false
    ) {
        self.phase = phase
        self.showsPage = showsPage
        self.hasPage = hasPage
        self.serverReady = serverReady
        self.canGoBack = canGoBack
        self.canGoForward = canGoForward
    }
}

/// What View > Reload Page, Command-R, does in a folder window (mb-i1wy).
///
/// It does something in every state the window can be in, so the item is never disabled
/// while a folder window is key. With the page on screen it is a browser's Reload. Without
/// a page to reload, it does what the window offers instead: it loads the page again from
/// a ready server, it starts a stopped server or joins the start under way, it does what
/// the failure view's Retry does after the server failed, and it starts a restored folder
/// that waits to be brought forward. A sheet the page opened is cancelled first (`PageSheets`), so the
/// reload is never left behind the page's own question; the app's sheets stay.
public nonisolated enum PageReload: Equatable, Sendable {
    /// The page is shown and has committed: WebKit reloads it from the server.
    case reloadPage
    /// The server is ready and no page can be reloaded: a load still on its way before its
    /// commit, a discarded page loading again, a window WebKit opened whose first
    /// load has not committed, or a page that failed while the server stayed ready (a
    /// provisional failure, or a content process that kept dying). WebKit's reload does
    /// nothing in a view without a committed page, so the window loads its page again,
    /// once the server answers its health check: the one a load still on its way was
    /// loading, else the one asked for or shown last, else the server's entry page. A
    /// server that no longer answers fails, and every window of the folder says so.
    case loadPage
    /// No server to load from, and none failed: the window starts it, and a start already
    /// under way, such as the one "Starting…" shows, is joined rather than stopped
    /// (`FolderSession.startServer`), so pressing Command-R while a start looks slow never
    /// throws it away or sends it to the back of the launch queue.
    case startServer
    /// What the failure view's default action, Retry, and File > Restart Server do: a fresh
    /// server from the runtime accepted now, then the page (`FolderSession.retry`). For a
    /// server that failed, and for a start waiting for a runtime, which is asked again and,
    /// finding none, opens Settings, the waiting view's own button.
    case restartServer
    /// A restored folder in a protected location starts when its window is brought forward,
    /// and its window is the key window: Command-R does what bringing it forward does, which starts it
    /// through the restore as the user's choice (`RestoreRun.select`).
    case startAsSelected

    public static func route(in window: FolderWindowState) -> PageReload {
        if window.showsPage {
            if window.hasPage { return .reloadPage }
            return window.serverReady ? .loadPage : .startServer
        }
        switch window.phase {
        case .failed: return window.serverReady ? .loadPage : .restartServer
        case .waitingForRuntime: return .restartServer
        case .waitingForSelection: return .startAsSelected
        case .starting, .reloading: return window.serverReady ? .loadPage : .startServer
        }
    }
}

/// The folder window's menu items that act on its page, and when each is enabled.
public nonisolated enum PageMenu {
    public enum Item: CaseIterable, Sendable {
        case back, forward, reload, print, actualSize, zoomIn, zoomOut, find
    }

    /// Whether `item` is enabled in `window`. Reload always is (`PageReload`); the others
    /// act on the page itself, so they need it on screen.
    public static func isEnabled(_ item: Item, in window: FolderWindowState) -> Bool {
        switch item {
        case .reload: true
        case .back: window.showsPage && window.canGoBack
        case .forward: window.showsPage && window.canGoForward
        case .print, .actualSize, .zoomIn, .zoomOut, .find: window.showsPage
        }
    }
}

/// The sheets a folder window's page opened, which Command-R answers as Cancel before it
/// reloads (review A2 on #433): the page's `alert`, `confirm`, and `prompt`, its file
/// input's open panel, and the print panel. The window records each as it presents it and
/// forgets it when it is answered. The app's own sheets on the window, the runtime-upgrade
/// offer, a download's save panel, and a failed download's alert, are never recorded, so
/// Command-R leaves them, and the reload runs behind them.
public struct PageSheets<Sheet: AnyObject> {
    private var open: [Sheet] = []

    public init() {}

    public var count: Int { open.count }

    public mutating func opened(_ sheet: Sheet) {
        if !cancels(sheet) { open.append(sheet) }
    }

    public mutating func closed(_ sheet: Sheet) {
        open.removeAll { $0 === sheet }
    }

    /// Whether Command-R cancels `sheet`, the one attached to the window: only if the page
    /// opened it.
    public func cancels(_ sheet: Sheet?) -> Bool {
        guard let sheet else { return false }
        return open.contains { $0 === sheet }
    }
}
