import AppKit
import ShellCore

extension RootMark {
    /// The size the menus that list roots draw a mark at, as File > Open Recent drew
    /// Finder's folder icon.
    static let menuSize = NSSize(width: 16, height: 16)
    /// The screen scales each mark is drawn for: a Mac's displays are 1x or 2x.
    private static let scales = [1, 2]

    /// The mark as a template image at `menuSize`, so a menu draws it in its own ink and
    /// highlight, as it does an SF Symbol. CoreSVG reads the glyph's stroked path, which is
    /// all a Lucide glyph holds (`RootMark.svg`).
    ///
    /// The image holds bitmaps drawn from that SVG at each of `scales`, not the SVG
    /// itself. The Dock reads its menu in its own process, and AppKit's SVG image
    /// representation is private: archived without secure coding, it is a class a secure
    /// reader refuses, which would drop the Dock menu's marks. Bitmaps survive either way
    /// (checked on macOS 26.5 by archiving both images each way and reading them back with
    /// `NSKeyedUnarchiver.unarchivedObject(ofClass:from:)`), and each bitmap matches the
    /// SVG drawn at its scale pixel for pixel.
    var image: NSImage {
        if let cached = Self.images[self] { return cached }
        let svg = NSImage(data: Data(svg.utf8)) ?? NSImage()
        let image = NSImage(size: Self.menuSize)
        for scale in Self.scales {
            guard
                let bitmap = NSBitmapImageRep(
                    bitmapDataPlanes: nil, pixelsWide: Int(Self.menuSize.width) * scale,
                    pixelsHigh: Int(Self.menuSize.height) * scale, bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true,
                    isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)
            else { continue }
            bitmap.size = Self.menuSize
            NSGraphicsContext.saveGraphicsState()
            NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
            svg.draw(in: NSRect(origin: .zero, size: Self.menuSize))
            NSGraphicsContext.restoreGraphicsState()
            image.addRepresentation(bitmap)
        }
        image.isTemplate = true
        image.accessibilityDescription = label
        Self.images[self] = image
        return image
    }

    /// Each mark, drawn once. Every menu item that shows a mark holds this same image
    /// (`NSMenuItem.image` keeps the image it is given, uncopied), so a caller must never
    /// change it: its size and template flag are set once, here.
    private static var images: [RootMark: NSImage] = [:]
}
