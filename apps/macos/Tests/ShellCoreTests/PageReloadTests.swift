import Testing
@testable import ShellCore

/// View > Reload Page, Command-R, in every state a folder window can be in (mb-i1wy).
///
/// It was enabled only while the page was on screen, so while the status view covered
/// it (the server starting, failed, or waiting, a discarded tab loading its page again,
/// a page that did not load) Command-R did nothing, and where it was enabled it always
/// asked WebKit to reload, which does nothing in a web view without a committed page.
@Suite struct PageReloadTests {
    private static let failure = ServerFailure(summary: "exited", recentOutput: [])
    private static let phases: [WindowPhase] = [
        .starting, .failed(failure), .waitingForSelection, .waitingForRuntime, .reloading,
    ]

    /// Every combination of what the window shows, what its web view holds, and whether
    /// its server is ready, with history in both directions or none.
    private static var everyWindow: [FolderWindowState] {
        phases.flatMap { phase in
            [false, true].flatMap { showsPage in
                [false, true].flatMap { hasPage in
                    [false, true].flatMap { serverReady in
                        [false, true].map { history in
                            FolderWindowState(
                                phase: phase, showsPage: showsPage, hasPage: hasPage, serverReady: serverReady,
                                canGoBack: history, canGoForward: history)
                        }
                    }
                }
            }
        }
    }

    @Test func reloadIsEnabledInEveryWindowState() {
        let disabled = Self.everyWindow.filter { !PageMenu.isEnabled(.reload, in: $0) }
        #expect(disabled.count == 0, "Reload Page disabled in \(disabled.count) states, first: \(String(describing: disabled.first))")
    }

    /// Only Reload changed: the items that act on the page itself still need it on screen.
    @Test func theOtherPageItemsStillNeedThePageShown() {
        for window in Self.everyWindow {
            for item in [PageMenu.Item.print, .actualSize, .zoomIn, .zoomOut, .find] {
                #expect(PageMenu.isEnabled(item, in: window) == window.showsPage, "\(item) in \(window)")
            }
            #expect(PageMenu.isEnabled(.back, in: window) == (window.showsPage && window.canGoBack))
            #expect(PageMenu.isEnabled(.forward, in: window) == (window.showsPage && window.canGoForward))
        }
    }

    private func route(
        _ phase: WindowPhase, showsPage: Bool, hasPage: Bool = false, serverReady: Bool
    ) -> PageReload {
        PageReload.route(in: FolderWindowState(
            phase: phase, showsPage: showsPage, hasPage: hasPage, serverReady: serverReady))
    }

    @Test func aShownPageIsReloadedByWebKit() {
        for phase in Self.phases {
            #expect(route(phase, showsPage: true, hasPage: true, serverReady: true) == .reloadPage)
            #expect(route(phase, showsPage: true, hasPage: true, serverReady: false) == .reloadPage)
        }
    }

    /// A ready server and no page to reload: a load still on its way before its commit,
    /// a discarded tab loading its page again, or a window WebKit opened whose first load
    /// has not committed. WebKit's reload would do nothing, so the window loads its page
    /// again.
    @Test func aReadyServerWithoutAPageLoadsThePageAgain() {
        #expect(route(.starting, showsPage: false, serverReady: true) == .loadPage)
        #expect(route(.reloading, showsPage: false, serverReady: true) == .loadPage)
        #expect(route(.starting, showsPage: true, hasPage: false, serverReady: true) == .loadPage)
        // A discarded tab's fresh view never had a page; the status view covers it.
        #expect(route(.reloading, showsPage: false, hasPage: false, serverReady: true) == .loadPage)
    }

    /// With no server to load from, Command-R does what the status view's Retry and
    /// File > Restart Server do: a fresh server, then the page.
    @Test func noServerRestartsIt() {
        #expect(route(.starting, showsPage: false, serverReady: false) == .restartServer)
        #expect(route(.reloading, showsPage: false, serverReady: false) == .restartServer)
        #expect(route(.starting, showsPage: true, hasPage: false, serverReady: false) == .restartServer)
    }

    /// The failure view offers Retry, whatever failed: the server, the page's load, or the
    /// web content process, again and again. Its page is behind it, even with a ready server.
    @Test func aFailureRetriesAsItsButtonDoes() {
        for serverReady in [false, true] {
            for hasPage in [false, true] {
                #expect(
                    route(.failed(Self.failure), showsPage: false, hasPage: hasPage, serverReady: serverReady)
                        == .restartServer)
            }
        }
    }

    /// A start waiting for a runtime is asked again, which starts the server if one is now
    /// accepted, and otherwise opens Settings, the status view's own button.
    @Test func aStartWaitingForARuntimeIsAskedAgain() {
        for serverReady in [false, true] {
            #expect(route(.waitingForRuntime, showsPage: false, serverReady: serverReady) == .restartServer)
        }
    }

    /// A restored folder in a protected location starts when its tab is selected: Command-R
    /// in that tab does what selecting it does, which starts it through the restore as the
    /// user's choice (`RestoreRun.select`).
    @Test func aFolderWaitingForItsTabStartsAsIfSelected() {
        for serverReady in [false, true] {
            #expect(route(.waitingForSelection, showsPage: false, serverReady: serverReady) == .startAsSelected)
        }
    }
}
