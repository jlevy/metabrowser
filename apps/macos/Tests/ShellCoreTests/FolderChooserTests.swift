import Foundation
import Testing
@testable import ShellCore

@Suite struct RootMarkTests {
    /// `static/icons.js`, the page's icon registry.
    private static let icons: String = {
        let package = URL(filePath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent()
        let file = package.appending(path: "../../src/metabrowser/static/icons.js").standardizedFileURL
        return (try? String(contentsOf: file, encoding: .utf8)) ?? ""
    }()

    /// The path data of the entry `id` in `icons.js`: every `d="…"` from its key to the
    /// end of its SVG.
    private static func pagePaths(_ id: String) -> [String]? {
        guard let key = icons.range(of: "\n    \(id):"),
              let end = icons.range(of: "</svg>", range: key.upperBound..<icons.endIndex)
        else { return nil }
        let entry = String(icons[key.upperBound..<end.lowerBound])
        return entry.matches(of: /d="([^"]+)"/).map { String($0.output.1) }
    }

    @Test func everySharedMarkIsThePagesGlyph() throws {
        #expect(!Self.icons.isEmpty, "static/icons.js is readable from the test")
        #expect(Self.icons.contains("Lucide v1.17.0"), "the page's glyphs are the version the marks copy")
        for mark in RootMark.allCases where mark.isSharedWithPage {
            let page = try #require(Self.pagePaths(mark.lucideID), "icons.js has an entry \(mark.lucideID)")
            #expect(page == mark.paths, "RootMark.\(mark) matches icons.js's \(mark.lucideID)")
        }
    }

    @Test func theMarksDrawWithTheStrokeThePageGivesItsGlyphs() {
        for attribute in [
            #"viewBox="0 0 24 24""#, #"fill="none""#, #"stroke-width="2""#, #"stroke-linecap="round""#,
            #"stroke-linejoin="round""#,
        ] {
            #expect(Self.icons.contains(attribute), "icons.js draws with \(attribute)")
            for mark in RootMark.allCases { #expect(mark.svg.contains(attribute)) }
        }
    }

    @Test func eachKindOfRootHasItsMark() {
        #expect(RootMark(.folder) == .folder)
        #expect(RootMark(.mirror) == .repository)
        #expect(RootMark(SessionRoot.folder(URL(filePath: "/a"))) == .folder)
        #expect(RootMark(SessionRoot.repository(URL(string: "https://github.com/o/r")!)) == .repository)
        #expect(RootMark.folder.svg.hasPrefix("<svg") && RootMark.folder.svg.hasSuffix("</svg>"))
    }
}

@Suite struct FolderChooserTests {
    private static let home = "/Users/me"

    private func open(_ key: String, _ shown: FolderChooser.Shown, mark: RootMark = .folder) -> FolderChooser.OpenFolder {
        FolderChooser.OpenFolder(
            key: key, title: (key as NSString).lastPathComponent, location: key.replacingOccurrences(of: Self.home, with: "~"),
            mark: mark, shown: shown)
    }

    private func recent(_ root: String, mode: RecentTarget.Mode = .folder) -> RecentTargets.Item {
        let target = RecentTarget(mode: mode, root: root, openedAt: "2026-11-18T00:00:00Z")
        return RecentTargets.items([target], opensURLs: true, home: Self.home)[0]
    }

    @Test func theMenuListsOpenFoldersInOpenOrderThenRecentOnesThatAreNotOpen() {
        let rows = FolderChooser.menuRows(
            open: [open("/Users/me/b", .background), open("/Users/me/a", .here), open("/Users/me/c", .inAnotherWindow)],
            recent: [recent("/Users/me/a/"), recent("/Users/me/d"), recent("https://github.com/o/r", mode: .mirror)],
            home: Self.home)
        #expect(rows.map(\.title) == ["b", "a", "c", "d", "r"])
        #expect(rows.map(\.section) == [.open, .open, .open, .recent, .recent])
        #expect(rows.map(\.isChecked) == [false, true, false, false, false])
        #expect(rows.map(\.subtitle) == ["~/b", "~/a", FolderChooser.inAnotherWindow, "~/d", "github.com/o/r"])
        #expect(rows.map(\.mark) == [.folder, .folder, .folder, .folder, .repository])
        #expect(rows[3].target == .recent(URL(filePath: "/Users/me/d", directoryHint: .isDirectory)))
    }

    @Test func anOpenRepositoryIsNotListedAgainAmongTheRecent() {
        let rows = FolderChooser.menuRows(
            open: [open("https://github.com/o/r", .background, mark: .repository)],
            recent: [recent("https://github.com/o/r", mode: .mirror)], home: Self.home)
        #expect(rows.count == 1)
        #expect(rows[0].section == .open)
    }

    @Test func eachChoiceDoesWhatTheTableSays() {
        typealias C = FolderChooser
        let url = URL(filePath: "/d", directoryHint: .isDirectory)
        #expect(C.action(for: .open("/a", .here), newWindow: false) == .nothing)
        #expect(C.action(for: .open("/b", .background), newWindow: false) == .showHere("/b"))
        #expect(C.action(for: .open("/c", .inAnotherWindow), newWindow: false) == .bringForward("/c"))
        #expect(C.action(for: .recent(url), newWindow: false) == .openHere(url))
        #expect(C.action(for: .open("/a", .here), newWindow: true) == .newWindow("/a"))
        #expect(C.action(for: .open("/b", .background), newWindow: true) == .newWindow("/b"))
        #expect(C.action(for: .open("/c", .inAnotherWindow), newWindow: true) == .newWindow("/c"))
        #expect(C.action(for: .recent(url), newWindow: true) == .openInNewWindow(url))
    }

    @Test func thePanelPutsTheFolderShownLastFirstAndThisWindowsFolderLast() {
        let folders = [
            open("/Users/me/a", .here), open("/Users/me/b", .background), open("/Users/me/c", .inAnotherWindow),
            open("/Users/me/never", .background),
        ]
        let rows = FolderChooser.panelRows(
            open: folders, byRecency: ["/Users/me/a", "/Users/me/c", "/Users/me/b"], recent: [recent("/Users/me/d")],
            home: Self.home)
        #expect(rows.map(\.title) == ["c", "b", "never", "d", "a"])
        #expect(rows.last?.isChecked == true)
    }

    @Test func thePanelMatchesEveryWordInTheTitleOrTheLocation() {
        let rows = FolderChooser.menuRows(
            open: [open("/Users/me/wrk/métabrowser", .here), open("/Users/me/notes", .inAnotherWindow)],
            recent: [recent("https://github.com/jlevy/kpress", mode: .mirror)], home: Self.home)
        #expect(FolderChooser.matching(rows, query: "").count == 3)
        #expect(FolderChooser.matching(rows, query: "META").map(\.title) == ["métabrowser"])
        #expect(FolderChooser.matching(rows, query: "wrk meta").map(\.title) == ["métabrowser"])
        // A folder another window shows is found by its location, not its subtitle.
        #expect(FolderChooser.matching(rows, query: "~/notes").map(\.title) == ["notes"])
        #expect(FolderChooser.matching(rows, query: "another").isEmpty)
        #expect(FolderChooser.matching(rows, query: "github jlevy").map(\.title) == ["kpress"])
    }
}

@Suite struct FolderSwitcherTests {
    private func row(_ title: String, _ target: FolderChooser.Target) -> FolderChooser.Row {
        FolderChooser.Row(
            section: .open, title: title, subtitle: "~/\(title)", location: "~/\(title)", mark: .folder,
            isChecked: target == .open("/\(title)", .here), target: target)
    }

    private var rows: [FolderChooser.Row] {
        [
            row("beta", .open("/beta", .background)), row("gamma", .open("/gamma", .inAnotherWindow)),
            row("delta", .recent(URL(filePath: "/delta", directoryHint: .isDirectory))), row("alpha", .open("/alpha", .here)),
        ]
    }

    @Test func itOpensOnTheFirstRowAndReturnGoesBackToTheFolderShownBefore() {
        let switcher = FolderSwitcher(rows: rows)
        #expect(switcher.selected == 0)
        #expect(switcher.choice(newWindow: false) == .showHere("/beta"))
        #expect(switcher.choice(newWindow: true) == .newWindow("/beta"))
        #expect(FolderSwitcher(rows: []).selected == nil)
        #expect(FolderSwitcher(rows: []).choice(newWindow: false) == nil)
    }

    @Test func theSelectionMovesAndStopsAtEitherEnd() {
        var switcher = FolderSwitcher(rows: rows)
        switcher.move(by: -1)
        #expect(switcher.selected == 0)
        switcher.move(by: 2)
        #expect(switcher.choice(newWindow: false) == .openHere(URL(filePath: "/delta", directoryHint: .isDirectory)))
        switcher.move(by: 5)
        #expect(switcher.selected == 3)
        #expect(switcher.choice(newWindow: false) == FolderChooser.Action.nothing)
        switcher.select(1)
        #expect(switcher.choice(newWindow: false) == .bringForward("/gamma"))
        switcher.select(9)
        #expect(switcher.selected == 1)
    }

    @Test func aSearchSelectsItsFirstMatch() {
        var switcher = FolderSwitcher(rows: rows)
        switcher.move(by: 2)
        switcher.search("ALPHA")
        #expect(switcher.shown.map(\.title) == ["alpha"])
        #expect(switcher.selected == 0)
        switcher.search("nothing like it")
        #expect(switcher.selected == nil)
        #expect(switcher.closable == nil)
        switcher.search("")
        #expect(switcher.shown.count == 4)
    }

    @Test func onlyAnOpenFolderCanBeClosedAndTheListKeepsItsPlace() {
        var switcher = FolderSwitcher(rows: rows)
        #expect(switcher.closable == "/beta")
        switcher.select(2)
        #expect(switcher.closable == nil)
        switcher.select(3)
        #expect(switcher.closable == "/alpha")
        switcher.reload(Array(rows.dropLast()))
        #expect(switcher.selected == 2)
        switcher.search("a")
        switcher.select(1)
        switcher.reload(rows.filter { $0.title != "gamma" })
        #expect(switcher.query == "a")
        #expect(switcher.shown.map(\.title) == ["beta", "delta", "alpha"])
        #expect(switcher.selected == 1)
    }
}
