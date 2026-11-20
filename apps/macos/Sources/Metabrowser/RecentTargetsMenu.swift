import AppKit
import ShellCore

/// File > Open Recent and the Dock icon's menu, both drawn from `metab`'s recent targets
/// (`RecentTargets`).
///
/// `metab` keeps the list, so the menus hold what the user opened lately, in this app, in
/// the other build of it, or with `metab` in Terminal, up to `metab`'s own cap, and the
/// app decides nothing about membership or order. Both menus are drawn from one answer,
/// so they list the same targets in the same order (`RecentTargets.rows`).
///
/// A menu shows the last answer at once. The app asks again when it becomes active, when
/// File > Open Recent opens, when the Dock menu is asked for, and once the server it
/// started for an open has started; an answer that arrives while Open Recent is open
/// redraws it, and the Dock, which takes a copy of its menu, shows a newer answer the
/// next time it is opened.
///
/// The app no longer registers folders with `NSDocumentController`: macOS would add its
/// own recent-documents list to the Dock menu beside this one. What an earlier build
/// registered is cleared once, at launch.
final class RecentTargetsMenu: NSObject, NSMenuDelegate {
    /// What a menu item opens. An item carries it, not its place in the list: the Dock
    /// keeps its copy of the menu after the list has changed.
    private final class Carried: NSObject {
        let entry: RecentTargets.Item

        init(_ entry: RecentTargets.Item) {
            self.entry = entry
        }
    }

    private let setup: () -> RuntimeSetup?
    private let open: (URL) -> Void
    private let opensURLs = RecentTargets.opensURLs(infoDictionary: Bundle.main.infoDictionary ?? [:])
    private var items: [RecentTargets.Item] = []
    /// Why `metab` lists nothing, when it says so: the empty menu's tooltip.
    private var problem: String?
    private var isAsking = false
    /// Whether to ask once more when the answer under way arrives.
    private var asksAgain = false
    private var askedAt: ContinuousClock.Instant?
    /// The Open Recent menu to redraw when an answer arrives.
    private weak var menu: NSMenu?

    /// `setup` is the `metab` the app may run now, nil while there is none; `open` is
    /// handed what an entry opens, as a folder dropped on the app is.
    init(setup: @escaping () -> RuntimeSetup?, open: @escaping (URL) -> Void) {
        self.setup = setup
        self.open = open
        super.init()
        NSDocumentController.shared.clearRecentDocuments(nil)
    }

    /// `root` was asked for, by the user: a folder, or a repository by its address. Its
    /// server records it as it starts, so the app tells `metab` itself only for one that
    /// `isOpen` already, which starts none.
    func noteOpened(_ root: URL, isOpen: Bool) {
        if isOpen { change(RecentTargets.addArguments(RecentTargets.target(root))) }
    }

    /// Asks `metab` for the list, unless an answer is on its way or is newer than
    /// `RecentTargets.refreshInterval`.
    func refresh() {
        if let askedAt, askedAt.duration(to: .now) < RecentTargets.refreshInterval { return }
        ask()
    }

    /// Asks `metab` for the list now, whatever the last answer's age: an open the app
    /// started has a server that recorded it, so the Dock menu, which nothing else
    /// refreshes until the app is activated or a menu opens, lists it next.
    func refreshAfterOpen() {
        ask()
    }

    private func ask() {
        guard !isAsking else {
            // The answer on its way may predate what was just changed.
            asksAgain = true
            return
        }
        guard let setup = setup() else { return }
        isAsking = true
        let spec = RecentTargets.spec(
            RecentTargets.listArguments, with: setup, inherited: ProcessInfo.processInfo.environment)
        Task { [weak self] in
            let answer = RecentTargets.answer(await CommandRunner.run(spec, timeout: RecentTargets.timeout))
            self?.took(answer, from: setup.runtime.executable)
        }
    }

    private func took(_ answer: RecentTargets.Answer, from metab: String) {
        isAsking = false
        askedAt = .now
        let shown = (items, problem)
        switch answer {
        case .listing(let listing):
            items = RecentTargets.items(listing.targets, opensURLs: opensURLs)
            problem = listing.problem
            if let problem { AppLog.app.error("metab lists no recent targets: \(problem, privacy: .public)") }
        case .unreadable(let reason):
            // The last list stays: one failed answer should not empty the menu. With no
            // list to show, the empty menu's tooltip says why, since `metab`'s reason names
            // the remedy.
            if items.isEmpty { problem = "metab --recent \(reason)" }
            AppLog.app.error(
                "could not list recent targets from \(metab, privacy: .public): metab --recent \(reason, privacy: .public)")
        }
        if asksAgain {
            asksAgain = false
            ask()
        }
        // An open menu is redrawn only for a list that changed, so its rows do not move
        // under the pointer for an answer that says what it already shows.
        if let menu, shown.0 != items || shown.1 != problem { draw(.openRecent, into: menu) }
    }

    /// Runs a command that changes the list, then asks for the list again.
    private func change(_ arguments: [String]) {
        guard let setup = setup() else { return }
        let spec = RecentTargets.spec(arguments, with: setup, inherited: ProcessInfo.processInfo.environment)
        Task { [weak self] in
            let result = await CommandRunner.run(spec, timeout: RecentTargets.timeout)
            if !result.succeeded {
                let said = result.transcript(timeout: RecentTargets.timeout).suffix(2).joined(separator: " ")
                AppLog.app.error(
                    "metab \(arguments.last ?? "", privacy: .public) failed: \(said, privacy: .public)")
            }
            self?.ask()
        }
    }

    // MARK: - The two menus

    func menuNeedsUpdate(_ menu: NSMenu) {
        self.menu = menu
        draw(.openRecent, into: menu)
        refresh()
    }

    /// A key equivalent is never one of these items', so AppKit need not ask `metab` for
    /// the list each time a key is pressed.
    func menuHasKeyEquivalent(
        _ menu: NSMenu, for event: NSEvent, target: AutoreleasingUnsafeMutablePointer<AnyObject?>,
        action: UnsafeMutablePointer<Selector?>
    ) -> Bool {
        false
    }

    /// The Dock icon's menu, or nil with nothing to list. The Dock takes it as it is now,
    /// so the list is asked for again for the next time.
    func dockMenu() -> NSMenu? {
        refresh()
        guard !items.isEmpty else { return nil }
        let menu = NSMenu()
        draw(.dock, into: menu)
        return menu
    }

    private func draw(_ kind: RecentTargets.Menu, into menu: NSMenu) {
        menu.removeAllItems()
        for row in RecentTargets.rows(for: kind, count: items.count) {
            switch row {
            case .target(let index):
                let entry = items[index]
                let item = NSMenuItem(title: entry.title, action: #selector(openRecent(_:)), keyEquivalent: "")
                item.target = self
                item.representedObject = Carried(entry)
                item.toolTip = entry.toolTip
                // The shared mark, the page's own glyph (`RootMark`), never read from the
                // entry's path: a look at a listed folder can raise a privacy prompt nobody
                // asked for.
                item.image = RootMark(entry.target.mode).image(for: item)
                menu.addItem(item)
            case .empty:
                let none = NSMenuItem(title: "No Recent Items", action: nil, keyEquivalent: "")
                none.toolTip = problem
                menu.addItem(none)
            case .separator:
                menu.addItem(.separator())
            case .clear:
                let clear = NSMenuItem(title: "Clear Menu", action: #selector(clearRecent(_:)), keyEquivalent: "")
                clear.target = self
                menu.addItem(clear)
            }
        }
    }

    @objc private func openRecent(_ sender: NSMenuItem) {
        guard let entry = (sender.representedObject as? Carried)?.entry else { return }
        // From the Dock's menu the app may be in the background.
        NSApp.activate()
        openListed(entry.url, with: open)
    }

    /// The list's last answer, which the folder chooser lists; a newer one is asked for,
    /// for the next time.
    func listed() -> [RecentTargets.Item] {
        refresh()
        return items
    }

    /// Opens `url`, an entry of the list, with `opening`. The folder is looked at only now
    /// that the user chose it: one that is gone gets the app's usual message from
    /// `opening`, and leaves the list.
    func openListed(_ url: URL, with opening: (URL) -> Void) {
        let folder = url.isFileURL ? FolderSession.path(of: url) : nil
        let gone = folder.map { !FileChecks.isDirectory($0) } ?? false
        opening(url)
        if gone, let folder { change(RecentTargets.forgetArguments(folder)) }
    }

    @objc private func clearRecent(_ sender: Any?) {
        items = []
        problem = nil
        change(RecentTargets.clearArguments)
    }
}
