import Foundation

/// The mark that names a kind of root in the app's menus that list roots: the title's
/// folder chooser, the Switch Folder panel, File > Open Recent, and the Dock menu.
///
/// A mark the page also draws is the page's glyph, copied here from its entry in
/// `src/metabrowser/static/icons.js` (Lucide v1.17.0), so the app's menus and the page
/// name a folder alike; `RootMarkTests` holds each copy to its entry.
/// The app draws each as a template image (`svg`), so it takes the menu's ink and
/// highlight as an SF Symbol does.
public nonisolated enum RootMark: String, CaseIterable, Sendable {
    /// A folder on this Mac.
    case folder
    /// A repository opened by its address and read from `metab`'s cached copy.
    case repository

    public init(_ mode: RecentTarget.Mode) {
        switch mode {
        case .folder: self = .folder
        case .mirror: self = .repository
        }
    }

    public init(_ root: SessionRoot) {
        self = root.isLocal ? .folder : .repository
    }

    /// The Lucide icon id of its glyph.
    public var lucideID: String {
        switch self {
        case .folder: "folder"
        case .repository: "cloud"
        }
    }

    /// Whether the page draws the same glyph, under the same id in `static/icons.js`. The
    /// page draws no mark for a repository opened by its address, so that one is the app's
    /// alone.
    public var isSharedWithPage: Bool { self == .folder }

    /// What VoiceOver says for the mark.
    public var label: String {
        switch self {
        case .folder: "Folder"
        case .repository: "Repository"
        }
    }

    /// The glyph's path data, as Lucide v1.17.0 draws it in its 24-point box.
    public var paths: [String] {
        switch self {
        case .folder:
            // Lucide `folder`, as `static/icons.js` draws it.
            [
                "M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"
            ]
        case .repository:
            // Lucide `cloud`.
            ["M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"]
        }
    }

    /// The glyph as a standalone SVG document, with the stroke Lucide's glyphs share
    /// (`SA` in `static/icons.js`) in black, which a template image reads as its shape.
    public var svg: String {
        let open = #"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" "#
            + #"stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">"#
        return open + paths.map { #"<path d="\#($0)"/>"# }.joined() + "</svg>"
    }
}
