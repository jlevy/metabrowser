import AppKit
import ShellCore
import UniformTypeIdentifiers

/// File > Open Recent, drawn from `metab`'s recent targets (`RecentTargets`).
///
/// `metab` keeps the list, so the menu holds what any `metab` served lately, from this
/// app, from Terminal, or from the other build of the app, up to `metab`'s own cap, and
/// the app decides nothing about membership or order. The menu shows the last answer at
/// once and asks again whenever it opens or the app becomes active; an answer that
/// arrives while the menu is open redraws it.
///
/// The Dock icon's menu is macOS's: the app still registers each folder it opens with
/// `NSDocumentController`, and macOS keeps that list, with its own order and length, for
/// each build, and shows it when the app is not running too.
final class RecentTargetsMenu: NSObject, NSMenuDelegate {
    private static let iconSize = NSSize(width: 16, height: 16)
    private let setup: () -> RuntimeSetup?
    private let open: (URL) -> Void
    private let opensURLs = RecentTargets.opensURLs(infoDictionary: Bundle.main.infoDictionary ?? [:])
    private var items: [RecentTargets.Item] = []
    /// Why `metab` lists nothing, when it says so: the empty menu's tooltip.
    private var problem: String?
    private var isAsking = false
    private var askedAt: ContinuousClock.Instant?
    /// The menu to redraw when an answer arrives.
    private weak var menu: NSMenu?

    /// `setup` is the `metab` the app may run now, nil while there is none; `open` is
    /// handed what an entry opens, as a folder dropped on the app is.
    init(setup: @escaping () -> RuntimeSetup?, open: @escaping (URL) -> Void) {
        self.setup = setup
        self.open = open
    }

    /// `root` was asked for. macOS lists it in the Dock menu: a folder qualifies because
    /// `Info.plist` declares `public.folder` as a document type. `metab` lists it when
    /// its server starts, so the app tells `metab` itself only for a folder that
    /// `isOpen` already, which starts none.
    func noteOpened(_ root: URL, isOpen: Bool) {
        NSDocumentController.shared.noteNewRecentDocumentURL(root)
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
        if let menu { draw(menu) }
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

    // MARK: - NSMenuDelegate

    func menuNeedsUpdate(_ menu: NSMenu) {
        self.menu = menu
        draw(menu)
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

    private func draw(_ menu: NSMenu) {
        menu.removeAllItems()
        for (index, entry) in items.enumerated() {
            let item = NSMenuItem(title: entry.title, action: #selector(openRecent(_:)), keyEquivalent: "")
            item.target = self
            item.tag = index
            item.toolTip = entry.toolTip
            item.image = Self.icon(for: entry.target.mode)
            item.image?.size = Self.iconSize
            menu.addItem(item)
        }
        if items.isEmpty {
            let none = NSMenuItem(title: "No Recent Items", action: nil, keyEquivalent: "")
            none.toolTip = problem
            menu.addItem(none)
        }
        menu.addItem(.separator())
        let clear = NSMenuItem(title: "Clear Menu", action: #selector(clearRecent(_:)), keyEquivalent: "")
        clear.target = self
        menu.addItem(clear)
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
        guard items.indices.contains(sender.tag) else { return }
        let entry = items[sender.tag]
        // Looked at only now that the user chose it. A folder that is gone gets the app's
        // usual message from `open`, and leaves the list.
        let gone = entry.target.mode == .folder && !FileChecks.isDirectory(entry.target.root)
        open(entry.url)
        if gone { change(RecentTargets.forgetArguments(entry.target.root)) }
    }

    @objc private func clearRecent(_ sender: Any?) {
        NSDocumentController.shared.clearRecentDocuments(sender)
        items = []
        problem = nil
        change(RecentTargets.clearArguments)
    }
}
