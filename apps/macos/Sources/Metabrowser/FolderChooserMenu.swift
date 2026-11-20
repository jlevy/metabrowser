import AppKit
import ShellCore
import ShellViews

/// The folder chooser a window's title opens: the open folders, `metab`'s recent targets
/// that are not open, and the commands that open or close folders.
///
/// It is native chrome (an `NSMenu`, with section headers, check marks, subtitles, and
/// Option alternates); its rows and what each choice does are `FolderChooser`'s, tested
/// in `ShellCore`. Each root's mark is the page's own glyph (`RootMark`), on the line of
/// the root's name, with the subtitle under the name, on one line (`NSMenuItem.setMark`),
/// and the window's own folder's check mark stands on that line too (`TitleLineMenuItem`).
/// The menu is built each time it opens, from the folders open then and the recent list's
/// last answer, which it asks `metab` to refresh for next time, as File > Open Recent does.
final class FolderChooserMenu: NSObject {
    /// What a row's item carries: the row's target and the window it was opened from,
    /// which a choice acts on, held weakly so an open menu keeps no closed window.
    private final class Carried: NSObject {
        let target: FolderChooser.Target
        weak var window: BrowserWindowController?

        init(_ target: FolderChooser.Target, window: BrowserWindowController) {
            self.target = target
            self.window = window
        }
    }

    private let openFolders: (BrowserWindowController) -> [FolderChooser.OpenFolder]
    private let recent: () -> [RecentTargets.Item]
    private let choose: (FolderChooser.Action, BrowserWindowController?) -> Void
    private let hasBackgroundFolders: () -> Bool
    private let closeBackgroundFolders: () -> Void

    /// `openFolders` lists the open folders, in the order they opened, as the window asking
    /// sees each; `recent` is the recent list's last answer, and asks for a newer one;
    /// `choose` carries out a choice for the window it was made in.
    init(
        openFolders: @escaping (BrowserWindowController) -> [FolderChooser.OpenFolder],
        recent: @escaping () -> [RecentTargets.Item],
        choose: @escaping (FolderChooser.Action, BrowserWindowController?) -> Void,
        hasBackgroundFolders: @escaping () -> Bool,
        closeBackgroundFolders: @escaping () -> Void
    ) {
        self.openFolders = openFolders
        self.recent = recent
        self.choose = choose
        self.hasBackgroundFolders = hasBackgroundFolders
        self.closeBackgroundFolders = closeBackgroundFolders
    }

    /// The chooser for `window`'s title.
    func menu(for window: BrowserWindowController) -> NSMenu {
        let menu = NSMenu(title: "Folders")
        menu.autoenablesItems = false
        let rows = FolderChooser.menuRows(open: openFolders(window), recent: recent())
        for section in [FolderChooser.Section.open, .recent] {
            let shown = rows.filter { $0.section == section }
            guard !shown.isEmpty else { continue }
            menu.addItem(.sectionHeader(title: section == .open ? "Open" : "Recent"))
            for row in shown { add(row, to: menu, window: window) }
        }
        menu.addItem(.separator())
        // Nil-targeted, so they reach the app delegate as the File menu's do, and Switch
        // Folder… the window's controller, as the View menu's does.
        menu.addItem(MainMenu.item("Open Folder…", #selector(AppDelegate.openFolder(_:)), "o"))
        menu.addItem(MainMenu.item("Open URL…", #selector(AppDelegate.showOpenURL(_:)), "l"))
        menu.addItem(
            MainMenu.item("Switch Folder…", #selector(BrowserWindowController.switchFolder(_:)), "o", [.command, .shift]))
        menu.addItem(.separator())
        let close = NSMenuItem(
            title: "Close Background Folders", action: #selector(closeBackground(_:)), keyEquivalent: "")
        close.target = self
        close.isEnabled = hasBackgroundFolders()
        menu.addItem(close)
        return menu
    }

    /// A row, and its Option alternate, which opens it in a new window.
    private func add(_ row: FolderChooser.Row, to menu: NSMenu, window: BrowserWindowController) {
        // A title-line item, so the check stands on the name's line, beside the mark.
        let item = TitleLineMenuItem(title: row.title, action: #selector(chose(_:)), keyEquivalent: "")
        item.state = row.isChecked ? .on : .off
        let alternate = MainMenu.item("Open \(row.title) in New Window", #selector(choseNewWindow(_:)), "", .option)
        alternate.isAlternate = true
        for each in [item, alternate] {
            each.target = self
            // Fitted under the row's own title, so the alternate shows the same subtitle.
            each.setMark(row.mark, subtitle: row.subtitle, fittedUnder: row.title)
            each.representedObject = Carried(row.target, window: window)
            menu.addItem(each)
        }
    }

    @objc private func chose(_ sender: NSMenuItem) { carryOut(sender, newWindow: false) }
    @objc private func choseNewWindow(_ sender: NSMenuItem) { carryOut(sender, newWindow: true) }

    private func carryOut(_ sender: NSMenuItem, newWindow: Bool) {
        guard let carried = sender.representedObject as? Carried else { return }
        choose(FolderChooser.action(for: carried.target, newWindow: newWindow), carried.window)
    }

    @objc private func closeBackground(_ sender: Any?) {
        closeBackgroundFolders()
    }
}
