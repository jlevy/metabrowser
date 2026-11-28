import AppKit
import Foundation
import Testing
import WebKit
@testable import Metabrowser
@testable import ShellCore

/// Every folder opens in a window of its own, and no folder window takes a tab
/// (mb-4ek7), in real windows on screen. An earlier build could open a folder as a tab of
/// the front window, and did whenever its Settings or System Settings said so.
///
/// The sessions never start a server: the runtime they may start from is none, so each
/// waits for one, and no `metab` runs. `NoFolderTabsSourceTests` checks that no source
/// adds a tab or names a group for windows to tab into.
@Suite(.serialized) struct FolderWindowTests {
    nonisolated static let setup = RuntimeSetup(
        runtime: Runtime(executable: "/opt/metab/bin/metab", version: MetabRequirement.minimum, source: .chosen),
        tools: ToolPaths())

    /// The open folders, wired as `AppDelegate` wires them: a page that needs a window of
    /// its own goes to `FolderWindows.place`.
    final class Harness {
        let directory: URL
        let store: SessionStore
        private(set) var sessions: [String: FolderSession] = [:]
        private(set) var windows: FolderWindows!
        private let gate = LaunchGate()

        init(_ name: String = #function) throws {
            directory = try temporaryDirectory(name)
            store = SessionStore(directory: directory.appending(path: "support", directoryHint: .isDirectory))
            windows = FolderWindows(
                store: store, openSessions: { [unowned self] in Array(sessions.values) },
                session: { [unowned self] in sessions[$0] })
        }

        /// A folder below the harness's directory, which exists, by its canonical path.
        func folder(_ name: String) throws -> URL {
            let url = directory.appending(path: name, directoryHint: .isDirectory)
            try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
            return URL(filePath: FileChecks.canonicalPath(url.path(percentEncoded: false)), directoryHint: .isDirectory)
        }

        /// The open session of `root`, or a new one, as `AppDelegate.session(for:)` makes it.
        func session(_ root: URL) -> FolderSession {
            let key = SessionRoot.folder(root).key
            if let open = sessions[key] { return open }
            let session = FolderSession(root: .folder(root), setup: FolderWindowTests.setup, gate: gate, accepted: { nil })
            session.onPlaceWindow = { [unowned self] in windows.place($0) }
            session.onAllPagesClosed = { [unowned self] closed in
                sessions[closed.path] = nil
                windows.folderClosed(closed)
            }
            sessions[key] = session
            windows.folderOpened(session)
            return session
        }

        /// Every folder window of the harness's, of any session.
        var allWindows: [NSWindow] { sessions.values.flatMap(\.windows).compactMap(\.window) }

        func closeAll() async {
            for session in Array(sessions.values) {
                for controller in session.windows { controller.window?.close() }
                for page in session.pages { page.close() }
                await session.shutDown()
            }
            try? FileManager.default.removeItem(at: directory)
        }
    }

    /// No window is in a tab group with another, and each refuses to join one.
    private func expectAlone(_ windows: [NSWindow], sourceLocation: SourceLocation = #_sourceLocation) {
        for window in windows {
            #expect(window.tabbingMode == .disallowed, sourceLocation: sourceLocation)
            #expect((window.tabbedWindows?.count ?? 1) == 1, sourceLocation: sourceLocation)
            #expect((window.tabGroup?.windows.count ?? 1) == 1, sourceLocation: sourceLocation)
            #expect(window.tabGroup?.isTabBarVisible != true, sourceLocation: sourceLocation)
        }
    }

    /// The app turns AppKit's automatic tabbing off before it builds its menus, so the
    /// Window menu has no tab items and System Settings' "Prefer tabs" puts no new window
    /// in a tab.
    @Test func theAppRefusesAutomaticTabbing() async {
        await runAppKitEventLoop()
        let before = NSWindow.allowsAutomaticWindowTabbing
        defer { NSWindow.allowsAutomaticWindowTabbing = before }
        NSWindow.allowsAutomaticWindowTabbing = true
        BrowserWindowController.refuseTabs()
        #expect(!NSWindow.allowsAutomaticWindowTabbing)
    }

    /// Two folders open as two windows, and Merge All Windows and Show Tab Bar leave each
    /// alone, even with AppKit's automatic tabbing on: each window disallows tabbing itself.
    @Test func twoFoldersAreTwoWindowsThatMergeAllWindowsLeavesAlone() async throws {
        await runAppKitEventLoop()
        let before = NSWindow.allowsAutomaticWindowTabbing
        defer { NSWindow.allowsAutomaticWindowTabbing = before }
        NSWindow.allowsAutomaticWindowTabbing = true
        let harness = try Harness()
        let a = harness.session(try harness.folder("a"))
        let b = harness.session(try harness.folder("b"))
        harness.windows.place(a.makeWindow())
        harness.windows.place(b.makeWindow())
        let first = try #require(a.windows.first?.window)
        let second = try #require(b.windows.first?.window)
        #expect(first !== second)
        #expect(first.isVisible && second.isVisible)
        expectAlone([first, second])

        second.mergeAllWindows(nil)
        first.toggleTabBar(nil)
        expectAlone([first, second])
        #expect(first.isVisible && second.isVisible)
        await harness.closeAll()
    }

    @Test func nativeHistoryKeepsDuplicateAddressesSeparateAndResetsOnNewOrigin() async throws {
        await runAppKitEventLoop()
        ignoreSIGPIPELikeTheApp()
        let html = Data("<h1>Navigation test</h1>".utf8)
        let before = try LocalHTTPServer(body: html, contentType: "text/html; charset=utf-8")
        let after = try LocalHTTPServer(body: html, contentType: "text/html; charset=utf-8")
        let originalOrigin = before.start()
        let newOrigin = after.start()
        defer { before.stop(); after.stop() }

        let harness = try Harness()
        let session = harness.session(try harness.folder("native-navigation"))
        let controller = session.makeWindow()
        let window = try #require(controller.window)
        defer { window.close(); try? FileManager.default.removeItem(at: harness.directory) }
        window.makeKeyAndOrderFront(nil)
        let page = controller.page
        let route = "/view/a%20b.md?tab=checks#L13"
        let originalAddress = try #require(URL(string: route, relativeTo: originalOrigin)?.absoluteURL)
        page.attach(ServerEndpoint(origin: originalOrigin, entryURL: originalAddress), authorization: .none)
        #expect(await eventually(within: .seconds(5)) { page.navigationState.url == originalAddress })
        #expect(!page.navigationState.back)
        let oldView = page.webView
        _ = try await oldView.evaluateJavaScript("""
            history.replaceState({ visit: 1 }, "", location.href);
            history.pushState({ visit: 2 }, "", location.href);
            history.pushState({ visit: 3 }, "", location.href);
            0;
            """)
        #expect(await eventually(within: .seconds(5)) { page.historyItems(.back).count == 2 })
        let items = page.historyItems(.back)
        let nearest = try #require(items.first)
        let oldest = try #require(items.last)
        #expect(nearest !== oldest)
        #expect(nearest.url == originalAddress)
        #expect(oldest.url == originalAddress)
        #expect(page.navigationState.back)
        #expect(await eventually(within: .seconds(5)) { window.isKeyWindow })
        let originalItem = oldView.backForwardList.currentItem
        page.traverseHistory(to: oldest, direction: .back, from: originalItem, in: oldView)
        #expect(await eventually(within: .seconds(5)) { oldView.backForwardList.currentItem === oldest })
        let restored = try await oldView.evaluateJavaScript("history.state.visit")
        #expect(restored as? Int == 1)
        #expect(page.historyItems(.forward).count == 2)

        page.showStarting()
        #expect(page.navigationState.url == nil)
        let newAddress = try #require(URL(string: route, relativeTo: newOrigin)?.absoluteURL)
        page.attach(ServerEndpoint(origin: newOrigin, entryURL: newOrigin), authorization: .none)
        #expect(await eventually(within: .seconds(5)) { page.navigationState.url == newAddress })
        #expect(page.webView !== oldView)
        #expect(!page.navigationState.back)
        #expect(!page.navigationState.forward)
    }

    /// A Command-click on a link to the folder's server, and `target=_blank`, open another
    /// window of the same folder, which shares its server.
    @Test func aPagesNewWindowIsAnotherWindowOfItsFolder() async throws {
        await runAppKitEventLoop()
        let harness = try Harness()
        let a = harness.session(try harness.folder("a"))
        harness.windows.place(a.makeWindow())
        a.openWindow(at: try #require(URL(string: "http://127.0.0.1:8650/view/notes.md")))
        _ = a.openChildWindow(configuration: WKWebViewConfiguration())
        #expect(harness.sessions.count == 1)
        let windows = a.windows.compactMap(\.window)
        #expect(windows.count == 3)
        #expect(Set(windows.map(ObjectIdentifier.init)).count == 3)
        #expect(windows.allSatisfy { $0.isVisible })
        expectAlone(windows)
        await harness.closeAll()
    }

    /// A folder in the background, opened again, gets a window of its own, not the window
    /// that switched away from it.
    @Test func aFolderInTheBackgroundOpensInAWindowOfItsOwn() async throws {
        await runAppKitEventLoop()
        let harness = try Harness()
        let a = harness.session(try harness.folder("a"))
        let b = harness.session(try harness.folder("b"))
        harness.windows.place(a.makeWindow())
        let window = try #require(a.windows.first)
        #expect(harness.windows.switchWindow(window, to: b))
        #expect(a.isInBackground)
        #expect(window.page.session === b)

        a.showFrontWindow()
        let reopened = try #require(a.windows.first?.window)
        #expect(reopened !== window.window)
        #expect(reopened.isVisible)
        #expect(!a.isInBackground)
        expectAlone(harness.allWindows)
        await harness.closeAll()
    }

    /// An earlier build's window of two folder tabs reopens as two windows: the tab it
    /// showed loads, at the saved frame and in front, and the other waits to be brought
    /// forward. The session saved then has a window, with one page, for each, under the
    /// file's same keys.
    @Test func anEarlierBuildsWindowOfTabsReopensAsAWindowPerTab() async throws {
        await runAppKitEventLoop()
        let harness = try Harness()
        let a = SessionRoot.folder(try harness.folder("a")).key
        let b = SessionRoot.folder(try harness.folder("b")).key
        // As an earlier build wrote it: one window, its two tabs in tab-bar order, the second shown.
        let earlier = #"{"windows":[{"tabs":[{"root":"\#(a)"},{"root":"\#(b)"}],"selected":1,"frame":"100 100 640 480 0 0 1024 768 "}],"background":[]}"#
        try FileManager.default.createDirectory(
            at: harness.store.url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try Data(earlier.utf8).write(to: harness.store.url)

        harness.windows.restore { harness.session($0) }
        let sessionA = try #require(harness.sessions[a])
        let sessionB = try #require(harness.sessions[b])
        #expect(sessionA.windows.count == 1 && sessionB.windows.count == 1)
        let windowA = try #require(sessionA.windows.first)
        let windowB = try #require(sessionB.windows.first)
        #expect(windowA.window !== windowB.window)
        #expect(windowA.window?.isVisible == true && windowB.window?.isVisible == true)
        expectAlone(harness.allWindows)
        #expect(windowA.page.isDiscarded)
        #expect(!windowB.page.isDiscarded)
        #expect(windowB.window?.frame.size == CGSize(width: 640, height: 480))

        let snapshot = harness.windows.snapshot()
        #expect(snapshot.windows.count == 2)
        #expect(snapshot.windows.allSatisfy { $0.pages.count == 1 && $0.selected == 0 })
        #expect(Set(snapshot.windows.flatMap { $0.pages.map(\.root) }) == [a, b])
        try harness.store.save(snapshot)
        let written = try String(contentsOf: harness.store.url, encoding: .utf8)
        #expect(written.contains(#""tabs""#), "the file keeps the key an earlier build reads")
        await harness.closeAll()
    }
}
