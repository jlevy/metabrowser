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
    /// Every item is read, so one added later is held to a rule here too.
    @Test func theOtherPageItemsStillNeedThePageShown() {
        for window in Self.everyWindow {
            for item in PageMenu.Item.allCases {
                let expected =
                    switch item {
                    case .reload: true
                    case .back: window.showsPage && window.canGoBack
                    case .forward: window.showsPage && window.canGoForward
                    case .print, .actualSize, .zoomIn, .zoomOut, .find: window.showsPage
                    }
                #expect(PageMenu.isEnabled(item, in: window) == expected, "\(item) in \(window)")
            }
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

    /// With no server to load from and no failure shown, Command-R starts the server, which
    /// joins a start already under way rather than stopping it (review A1 on #433): pressed
    /// on "Starting…", it never throws the start away or sends it to the back of the
    /// launch queue.
    @Test func noServerStartsOneOrJoinsTheStartUnderWay() {
        #expect(route(.starting, showsPage: false, serverReady: false) == .startServer)
        #expect(route(.reloading, showsPage: false, serverReady: false) == .startServer)
        #expect(route(.starting, showsPage: true, hasPage: false, serverReady: false) == .startServer)
        for hasPage in [false, true] {
            #expect(route(.starting, showsPage: false, hasPage: hasPage, serverReady: false) == .startServer)
        }
    }

    /// The server failed: the failure view's default action, Retry, restarts it.
    @Test func aServerFailureRetriesAsItsDefaultButtonDoes() {
        for hasPage in [false, true] {
            #expect(route(.failed(Self.failure), showsPage: false, hasPage: hasPage, serverReady: false) == .restartServer)
        }
    }

    /// Only the page failed, while the server is still ready: a provisional load failure, or
    /// a content process that kept dying. Command-R loads this tab's page again, after the
    /// health check, and restarts nothing under the folder's other tabs (review A6 on #433).
    /// A server that no longer answers the check fails, every tab says so, and the next
    /// Command-R restarts it.
    @Test func aPageFailureLoadsThePageAgain() {
        for hasPage in [false, true] {
            #expect(route(.failed(Self.failure), showsPage: false, hasPage: hasPage, serverReady: true) == .loadPage)
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

/// The sheets Command-R cancels before it reloads: only the ones the page opened (review A2
/// on #433). A sheet the app put on the window, such as the runtime-upgrade offer or a
/// download's save panel, is never recorded, so it stays, and the reload runs behind it.
@Suite struct PageSheetsTests {
    private final class Sheet {}

    @Test func onlyASheetThePageOpenedIsCancelled() {
        var sheets = PageSheets<Sheet>()
        let alert = Sheet()
        let upgradeOffer = Sheet()
        sheets.opened(alert)
        #expect(sheets.cancels(alert))
        #expect(!sheets.cancels(upgradeOffer))
        #expect(!sheets.cancels(nil))
    }

    @Test func aSheetAnsweredIsForgotten() {
        var sheets = PageSheets<Sheet>()
        let prompt = Sheet()
        let openPanel = Sheet()
        sheets.opened(prompt)
        sheets.opened(openPanel)
        sheets.closed(prompt)
        #expect(!sheets.cancels(prompt))
        #expect(sheets.cancels(openPanel))
        #expect(sheets.count == 1)
        sheets.opened(openPanel)  // recorded once
        #expect(sheets.count == 1)
    }
}
