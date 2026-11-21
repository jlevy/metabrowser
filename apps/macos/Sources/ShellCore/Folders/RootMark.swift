import CoreGraphics
import Foundation

/// The mark that names a kind of root in the app's menus that list roots: the title's
/// folder chooser and path menu, the Switch Folder panel, File > Open Recent, and the Dock
/// menu.
///
/// There are three kinds of root, and each has a mark of its own: a cloud mirror, a local
/// Git checkout, and a local plain folder. The fourth case, `folder`, is not a root's mark
/// but the ordinary folder's: a folder above the root in the title's path menu. A root's
/// mark never reads as an ordinary folder, and the reverse, so the root of a path is the
/// one row of the menu that differs from the rows above it.
///
/// Each mark uses the page's own artwork, copied here from where the page has
/// it: a root's from `src/metabrowser/static/source-kind-glyphs.json`, which the server writes
/// into the page's first paint, and the ordinary folder's from `static/icons.js`. So the app's
/// menus and the nav column at the top of a page name a root alike, glyph for glyph;
/// `RootMarkTests` holds each copy to its source, and `docs/design-system-icons.md`
/// ("Source Kinds") lists the pairing. The
/// app draws each as a template image (`svg`), so it takes the menu's ink and highlight as
/// an SF Symbol does. No SF Symbol stands in for one: a symbol is a different drawing, and
/// the three kinds would then read differently here and on the page.
public nonisolated enum RootMark: String, CaseIterable, Sendable {
    /// An ordinary folder: a folder above the root, or any folder that is not a root. The
    /// page's `folder`.
    case folder
    /// A local folder that is not a Git checkout (`FolderKind.folder`): a folder with a dot.
    case plainFolder
    /// A local Git checkout (`FolderKind.git`): a folder with Git's branch.
    case gitCheckout
    /// A repository opened by its address and read from `metab`'s cached copy
    /// (`FolderKind.mirror`): a folder with a cloud.
    case mirror

    /// The mark of a root that `kind` names, as `GET /api/identity` says it.
    public init(_ kind: FolderKind) {
        switch kind {
        case .folder: self = .plainFolder
        case .git: self = .gitCheckout
        case .mirror: self = .mirror
        }
    }

    /// The mark of a recent target: its mode, and for a folder whether it was a checkout
    /// when it was opened (`RecentTarget.git`). A listed folder is never looked at, since a
    /// look can raise a privacy prompt for a folder nobody asked to see.
    public init(_ target: RecentTarget) {
        switch target.mode {
        case .folder: self = target.git ? .gitCheckout : .plainFolder
        case .mirror: self = .mirror
        }
    }

    /// The kind of root this is the mark of, as `GET /api/identity` says it, or nil for the
    /// ordinary folder, which is no root's.
    public var kind: FolderKind? {
        switch self {
        case .folder: nil
        case .plainFolder: .folder
        case .gitCheckout: .git
        case .mirror: .mirror
        }
    }

    /// The glyph's identifier in the icon catalog.
    public var glyphID: String {
        switch self {
        case .folder: "folder"
        case .plainFolder: "folderDot"
        case .gitCheckout: "folderGit2"
        case .mirror: "folderCloud"
        }
    }

    /// What VoiceOver says for the mark: the words `metab` has for the kind
    /// (`KIND_LABELS` in `root_identity.py`).
    public var label: String {
        switch self {
        case .folder: "Folder"
        case .plainFolder: "Local folder"
        case .gitCheckout: "Local Git checkout"
        case .mirror: "Cloud mirror"
        }
    }

    /// The page's SVG elements in a 24-point box.
    ///
    /// The three folder glyphs are Lucide's `folder`, `folder-dot`, and `folder-git-2`.
    /// The mirror combines an adapted `folder-git-2` outline and a scaled `cloud`.
    /// The source glyphs are from Lucide v1.17.0
    /// (https://github.com/lucide-icons/lucide/tree/896aba0d195a4fec38ad7c4a90d00cb3389ebfea/icons),
    /// under this license, which must accompany them:
    ///
    ///     ISC License
    ///     Copyright (c) 2026 Lucide Icons and Contributors
    ///     Permission to use, copy, modify, and/or distribute this software for any
    ///     purpose with or without fee is hereby granted, provided that the above
    ///     copyright notice and this permission notice appear in all copies.
    ///     THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
    ///     WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
    ///     MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
    ///     ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
    ///     WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
    ///     ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
    ///     OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
    public var markup: String {
        switch self {
        case .folder:
            // Lucide `folder`.
            #"<path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z"/>"#
        case .plainFolder:
            // Lucide `folder-dot`.
            #"<path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.93a2 2 0 0 1-1.66-.9l-.82-1.2A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13c0 1.1.9 2 2 2Z"/>"#
                + #"<circle cx="12" cy="13" r="1"/>"#
        case .gitCheckout:
            // Lucide `folder-git-2`.
            #"<path d="M18 19a5 5 0 0 1-5-5v8"/>"#
                + #"<path d="M9 20H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H20a2 2 0 0 1 2 2v5"/>"#
                + #"<circle cx="13" cy="12" r="2"/><circle cx="20" cy="19" r="2"/>"#
        case .mirror:
            // A cloud in the lower right, within the opening in the folder outline.
            #"<path d="M8 20H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.69.9l.81 1.2a2 2 0 0 0 1.67.9H20a2 2 0 0 1 2 2v3"/>"#
                + #"<path d="M19.6 21h-4.7a3.9 3.9 0 1 1 3.7-5h1a2.5 2.5 0 1 1 0 5Z"/>"#
        }
    }

    /// The glyph as a standalone SVG document, with the stroke Lucide's glyphs share
    /// (`SA` in `static/icons.js`) in black, which a template image reads as its shape.
    public var svg: String {
        let open = #"<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" fill="none" "#
            + #"stroke="black" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">"#
        return open + markup + "</svg>"
    }

    /// Where a menu item with a subtitle draws its mark, or its check mark: on the title's
    /// line, as an item with no subtitle does, so the subtitle reads as the next line after
    /// the mark.
    ///
    /// AppKit centers an item's image, and its state image (the check mark), on the whole
    /// item, title and subtitle together, which leaves a mark as tall as the title between
    /// the two lines. So the app draws the mark at the top of an image `2 × rise` taller
    /// than the mark: centered on the item, that image puts the mark's middle `rise` above
    /// the item's middle, on the title's line, and the title and subtitle still start after
    /// it, one above the other. The check is raised the same way
    /// (`TitleLineMenuItem.CheckMark`).
    public nonisolated struct TitleLineLayout: Equatable, Sendable {
        /// How far the middle of a subtitled item's title line is above the item's middle:
        /// 7 points, measured on macOS 26.5 by drawing a menu of a one-line item and two
        /// subtitled ones into a bitmap while it was open. Raised 7 points, the mark's ink
        /// sits on the title's ink exactly as on the one-line item, its middle half a point
        /// above the middle of the title's ink on both; 6 points leaves it a point low.
        /// The image is then 30 points tall, the tallest that leaves a subtitled item as
        /// tall as a 16-point image does: a 31-point one (7.5 points up) makes it taller.
        /// The check mark, raised the same 7 points, has the middle of its ink on the middle
        /// of the title's ink (macOS 26.5: both 40.25 points below the menu's top, in a
        /// capture of the chooser's open menu), where the unraised check is 7.0 points below.
        public static let rise: CGFloat = 7

        /// The image's size.
        public let size: CGSize
        /// The mark's frame in the image, y up: at its top, full width.
        public let mark: CGRect

        /// The layout for a mark `mark` in size, raised `rise`.
        public init(mark: CGSize, rise: CGFloat = Self.rise) {
            size = CGSize(width: mark.width, height: mark.height + 2 * rise)
            self.mark = CGRect(origin: CGPoint(x: 0, y: 2 * rise), size: mark)
        }
    }
}
