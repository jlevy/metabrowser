import AppKit
import ShellCore
import UniformTypeIdentifiers

/// File > Open Recent and the Dock icon's menu, both drawn from `metab`'s recent targets
/// (`RecentTargets`).
///
/// `metab` keeps the list, so the menus hold what the user opened lately, in this app, in
/// the other build of it, or with `metab` in Terminal, up to `metab`'s own cap, and the
/// app decides nothing about membership or order. Both menus are drawn from one answer,
/// so they list the same targets in the same order (`RecentTargets.rows`).
///
/// A menu shows the last answer at once. The app asks again when it becomes active, when
/// File > Open Recent opens, and when the Dock menu is asked for; an answer that arrives
/// while Open Recent is open redraws it, and the Dock, which takes a copy of its menu,
/// shows a newer answer the next time it is opened.
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

    private static let iconSize = NSSize(width: 16, height: 16)
    private let setup: () -> RuntimeSetup?
    private let open: (URL) -> Void
    private let opensURLs = RecentTargets.opensURLs(infoDictionary: Bundle.main.infoDictionary ?? [:])
    private var items: [RecentTargets.Item] = []
    /// Why `metab` lists nothing, when it says so: the empty menu's tooltip.
    private var problem: String?
    private var isAsking = false
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

    /// `root` was asked for, by the user. Its server records it as it starts, so the app
    /// tells `metab` itself only for a folder that `isOpen` already, which starts none.
    func noteOpened(_ root: URL, isOpen: Bool) {
        if isOpen { change(RecentTargets.addArguments(root.path(percentEncoded: false))) }
    }

    /// Asks `metab` for the list, unless an answer is on its way or is newer than
    /// `RecentTargets.refreshInterval`.
    func refresh() {
        if let askedAt, askedAt.duration(to: .now) < RecentTargets.refreshInterval { return }
        ask()
    }

    private func ask() {
        guard !isAsking, let setup = setup() else { return }
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
        case .unsupported:
            items = []
            problem = "This metab has no --recent; upgrade it to list recent folders."
            AppLog.app.error("\(metab, privacy: .public) has no --recent, so Open Recent is empty")
        case .unreadable(let reason):
            // The last list stays: one failed answer should not empty the menu.
            AppLog.app.error("could not list recent targets: metab --recent \(reason, privacy: .public)")
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
                item.image = Self.icon(for: entry.target.mode)
                item.image?.size = Self.iconSize
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

    /// The generic folder icon, and a cloud for a mirror, neither read from the entry's
    /// own path: a look at a listed folder can raise a privacy prompt nobody asked for.
    private static func icon(for mode: RecentTarget.Mode) -> NSImage? {
        switch mode {
        case .folder: NSWorkspace.shared.icon(for: .folder)
        case .mirror: NSImage(systemSymbolName: "cloud", accessibilityDescription: "Mirror")
        }
    }

    @objc private func openRecent(_ sender: NSMenuItem) {
        guard let entry = (sender.representedObject as? Carried)?.entry else { return }
        // Looked at only now that the user chose it. A folder that is gone gets the app's
        // usual message from `open`, and leaves the list.
        let gone = entry.target.mode == .folder && !FileChecks.isDirectory(entry.target.root)
        // From the Dock's menu the app may be in the background.
        NSApp.activate()
        open(entry.url)
        if gone { change(RecentTargets.forgetArguments(entry.target.root)) }
    }

    @objc private func clearRecent(_ sender: Any?) {
        items = []
        problem = nil
        change(RecentTargets.clearArguments)
    }
}
