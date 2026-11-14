/// What a folder window shows in place of its page: the server is starting, it failed
/// and here is why, it waits for its tab to be selected or for a `metab` the app can run,
/// or a discarded tab reloads. The app's `StatusView` draws it.
public nonisolated enum WindowPhase: Equatable, Sendable {
    case starting
    case failed(ServerFailure)
    /// A restored folder in a protected location, whose server starts only once its tab
    /// is selected, so that a launch raises no privacy prompt for it.
    case waitingForSelection
    /// A start waiting for a `metab` the app accepts.
    case waitingForRuntime
    /// A tab that gave up its page loads it again from the running server.
    case reloading
}

/// A folder window, as its menu items see it.
public nonisolated struct FolderWindowState: Equatable, Sendable {
    /// What the status view says, when it covers the page.
    public var phase: WindowPhase
    /// The page is on screen: the status view does not cover it.
    public var showsPage: Bool
    /// The web view has a page it can reload: one that committed and is still its current
    /// history entry. A fresh view, such as a discarded tab's, has none, and nor has a
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
/// a ready server, it does what the status view's Retry does when there is none, and it
/// selects a tab that waits to be selected. A sheet on the window is cancelled first, so
/// the reload is never left behind a question about the page it replaces.
public nonisolated enum PageReload: Equatable, Sendable {
    /// The page is shown and has committed: WebKit reloads it from the server.
    case reloadPage
    /// The server is ready and no page can be reloaded: a load still on its way before its
    /// commit, a discarded tab loading its page again, or a window WebKit opened whose
    /// first load has not committed. WebKit's reload does nothing in a view without a
    /// committed page, so the window loads its page again: the one a load still on its way
    /// was loading, else the one asked for or shown last, else the server's entry page.
    case loadPage
    /// What the status view's Retry and File > Restart Server do: a fresh server from the
    /// runtime accepted now, then the page. For a failure, whatever failed, since that is
    /// the failure view's one action; for a window with no server to load from; and for a
    /// start waiting for a runtime, which is asked again and, finding none, opens Settings,
    /// the waiting view's own button (`FolderSession.retry`).
    case restartServer
    /// A restored folder in a protected location starts when its tab is selected, and its
    /// tab is the key window: Command-R does what selecting it does, which starts it
    /// through the restore as the user's choice (`RestoreRun.select`).
    case startAsSelected

    public static func route(in window: FolderWindowState) -> PageReload {
        if window.showsPage {
            if window.hasPage { return .reloadPage }
            return window.serverReady ? .loadPage : .restartServer
        }
        switch window.phase {
        case .failed, .waitingForRuntime: return .restartServer
        case .waitingForSelection: return .startAsSelected
        case .starting, .reloading: return window.serverReady ? .loadPage : .restartServer
        }
    }
}

/// The folder window's menu items that act on its page, and when each is enabled.
public nonisolated enum PageMenu {
    public enum Item: CaseIterable, Sendable {
        case back, forward, reload, print, actualSize, zoomIn, zoomOut, find
    }

    /// Whether `item` is enabled in `window`. Reload always is (`PageReload`); the others
    /// act on the page itself, so they need it on screen. Find also asks the window's text
    /// finder.
    public static func isEnabled(_ item: Item, in window: FolderWindowState) -> Bool {
        switch item {
        case .reload: true
        case .back: window.showsPage && window.canGoBack
        case .forward: window.showsPage && window.canGoForward
        case .print, .actualSize, .zoomIn, .zoomOut, .find: window.showsPage
        }
    }
}
