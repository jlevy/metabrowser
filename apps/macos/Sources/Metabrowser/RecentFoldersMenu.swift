import AppKit

/// File > Open Recent, drawn each time it opens from the recent documents list macOS
/// keeps through `NSDocumentController`, the list the Dock menu shows too.
///
/// The app only adds the folders it opens. macOS decides the membership, order, and
/// length (System Settings > Desktop & Dock > Recent documents), so the app keeps no
/// recents of its own: this is the platform exemption the server-topology brief
/// records, and recent roots kept in `metab` are a later phase. An entry whose folder
/// is gone stays listed, as macOS keeps it, and opening it says the folder is gone.
final class RecentFoldersMenu: NSObject, NSMenuDelegate {
    private static let iconSize = NSSize(width: 16, height: 16)
    private let open: (URL) -> Void

    init(open: @escaping (URL) -> Void) {
        self.open = open
    }

    /// `root` was opened; macOS lists it under Open Recent and in the Dock menu. A folder
    /// qualifies because `Info.plist` declares `public.folder` as a document type.
    static func noteOpened(_ root: URL) {
        NSDocumentController.shared.noteNewRecentDocumentURL(root)
    }

    func menuNeedsUpdate(_ menu: NSMenu) {
        menu.removeAllItems()
        for url in NSDocumentController.shared.recentDocumentURLs where url.isFileURL {
            let path = url.path(percentEncoded: false)
            let item = NSMenuItem(
                title: FileManager.default.displayName(atPath: path), action: #selector(openRecent(_:)),
                keyEquivalent: "")
            item.target = self
            item.representedObject = url
            item.toolTip = (path as NSString).abbreviatingWithTildeInPath
            item.image = NSWorkspace.shared.icon(forFile: path)
            item.image?.size = Self.iconSize
            menu.addItem(item)
        }
        if menu.items.isEmpty {
            menu.addItem(NSMenuItem(title: "No Recent Folders", action: nil, keyEquivalent: ""))
        }
        menu.addItem(.separator())
        let clear = NSMenuItem(title: "Clear Menu", action: #selector(clearRecent(_:)), keyEquivalent: "")
        clear.target = self
        menu.addItem(clear)
    }

    @objc private func openRecent(_ sender: NSMenuItem) {
        guard let url = sender.representedObject as? URL else { return }
        open(url)
    }

    @objc private func clearRecent(_ sender: Any?) {
        NSDocumentController.shared.clearRecentDocuments(sender)
    }
}
