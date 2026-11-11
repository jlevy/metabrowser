import Foundation

/// Everything a folder's window says about which folder it shows.
///
/// The title bar shows the short name prominent and bold, then a bullet and
/// "Metabrowser" in a secondary style, so a glance at a window tells which folder it
/// is. Everything else that names the window (the Window menu, Mission Control, the
/// Dock, accessibility) reads the plain title. A tab shows the short name alone.
public nonisolated struct WindowTitle: Equatable, Sendable {
    public enum Style: Equatable, Sendable {
        /// Bold, in the primary label color.
        case primary
        /// Regular, in the secondary label color.
        case secondary
    }

    public struct Segment: Equatable, Sendable {
        public var text: String
        public var style: Style

        public init(_ text: String, _ style: Style) {
            self.text = text
            self.style = style
        }
    }

    public var identity: FolderIdentity

    public init(_ identity: FolderIdentity) {
        self.identity = identity
    }

    /// `window.title`.
    public var plain: String { identity.title }

    /// What the title bar draws, in order.
    public var segments: [Segment] {
        [Segment(identity.shortName, .primary), Segment(" • ", .secondary), Segment(FolderIdentity.appName, .secondary)]
    }

    /// The tab's title, compact so that several tabs fit.
    public var tabTitle: String { identity.shortName }
    /// The tab's tooltip.
    public var tabToolTip: String { identity.fullName }
    /// "~/wrk/github/fdu · Local folder": the title's tooltip and `window.subtitle`.
    public var subtitle: String { "\(identity.fullName) · \(identity.kindLabel)" }
    /// Only a local folder has a file URL, and so a proxy icon and a path menu.
    public var hasProxyIcon: Bool { identity.kind == .folder }

    /// The segments to draw in `width` points, given how wide a run of segments is.
    ///
    /// The short name truncates last: when everything does not fit, the bullet and
    /// "Metabrowser" go first, and whole, since a clipped "Metab…" tells nothing. The
    /// short name is always drawn, and its label truncates it if even it does not fit.
    public func segments(fitting width: Double, measure: ([Segment]) -> Double) -> [Segment] {
        let all = segments
        return measure(all) <= width ? all : Array(all.prefix(1))
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
    /// True for `/` and for the root of a mounted volume, such as `/Volumes/Backup`.
    public nonisolated static func isVolumeRoot(_ path: String) -> Bool {
        (try? URL(filePath: path).resourceValues(forKeys: [.isVolumeKey]).isVolume) ?? false
    }
}
