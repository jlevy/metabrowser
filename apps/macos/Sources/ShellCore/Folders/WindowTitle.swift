import Foundation

/// Everything a folder's window says about which folder it shows.
///
/// The title bar shows the folder's short name alone, bold, so a glance at a window tells
/// which folder it is; the app icon's mark at the title bar's trailing end carries the
/// app's name, so the title does not repeat it. The Window menu, Mission Control, and the
/// window switcher read `window.title`, which is the short name too, unless another open
/// folder shares it (`windowTitles`). A tab shows the short name.
///
/// The served page's own title, "fdu • Metabrowser", names it in a browser's tab, where
/// nothing else says Metabrowser; the app does not use it.
public nonisolated struct WindowTitle: Equatable, Sendable {
    public var identity: FolderIdentity

    public init(_ identity: FolderIdentity) {
        self.identity = identity
    }

    /// The title bar's text.
    public var text: String { identity.shortName }
    /// The tab's title, compact so that several tabs fit.
    public var tabTitle: String { identity.shortName }
    /// The tab's tooltip.
    public var tabToolTip: String { identity.fullName }
    /// "~/wrk/github/fdu · Local folder": the title's tooltip and `window.subtitle`.
    public var subtitle: String { "\(identity.fullName) · \(identity.kindLabel)" }
    /// Only a local folder has a file URL, and so a path menu.
    public var hasPathMenu: Bool { identity.kind == .folder }

    /// `window.title` for each of `titles`, the open folders', in order: its short name,
    /// or its full name where another open folder shares the short name, so the Window
    /// menu, Mission Control, and the window switcher tell two such folders apart.
    public static func windowTitles(_ titles: [WindowTitle]) -> [String] {
        let counts = Dictionary(titles.map { ($0.identity.shortName, 1) }, uniquingKeysWith: +)
        return titles.map { counts[$0.identity.shortName, default: 0] > 1 ? $0.identity.fullName : $0.identity.shortName }
    }

    /// The path menu of a folder's window: the folder, then each folder that contains
    /// it, innermost first, ending at the first volume root (or `/`).
    public static func pathMenuFolders(
        for path: String, isVolumeRoot: (String) -> Bool = FileChecks.isVolumeRoot
    ) -> [String] {
        var folders: [String] = []
        var current = path
        while current.count > 1, current.hasSuffix("/") { current.removeLast() }
        while !current.isEmpty {
            folders.append(current)
            if current == "/" || isVolumeRoot(current) { break }
            current = (current as NSString).deletingLastPathComponent
        }
        return folders
    }
}

extension FileChecks {
    /// True for `/` and for the root of a mounted volume, such as `/Volumes/Backup`. A path
    /// whose volume cannot be read counts as none, so the path menu runs on up to `/`.
    public nonisolated static func isVolumeRoot(_ path: String) -> Bool {
        (try? URL(filePath: path).resourceValues(forKeys: [.isVolumeKey]).isVolume) ?? false
    }
}
