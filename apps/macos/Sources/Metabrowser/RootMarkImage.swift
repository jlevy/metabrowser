import AppKit
import ShellCore

extension RootMark {
    /// The size the menus that list roots draw a mark at, as File > Open Recent drew
    /// Finder's folder icon.
    static let menuSize = NSSize(width: 16, height: 16)

    /// The mark as a template image at `menuSize`, so a menu draws it in its own ink and
    /// highlight, as it does an SF Symbol. CoreSVG reads the glyph's stroked path, which is
    /// all a Lucide glyph holds (`RootMark.svg`).
    var image: NSImage {
        if let cached = Self.images[self] { return cached }
        let image = NSImage(data: Data(svg.utf8)) ?? NSImage()
        image.size = Self.menuSize
        image.isTemplate = true
        image.accessibilityDescription = label
        Self.images[self] = image
        return image
    }

    /// Each mark, drawn once. A menu item copies the image it is given, so one image
    /// serves every row.
    private static var images: [RootMark: NSImage] = [:]
}
