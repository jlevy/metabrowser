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
        drawn(in: Self.menuSize, at: NSRect(origin: .zero, size: Self.menuSize), cache: &Self.images)
    }

    /// The mark for a menu item with a subtitle: `image`'s mark at the top of a taller
    /// image (`RootMark.TitleLineLayout`), which AppKit, centering it on the item, draws
    /// on the title's line, with the subtitle under the title.
    var titleLineImage: NSImage {
        let layout = TitleLineLayout(mark: Self.menuSize)
        return drawn(in: layout.size, at: layout.mark, cache: &Self.titleLineImages)
    }

    /// The mark drawn at `frame` in a template image `size` in size, kept in `cache`.
    private func drawn(in size: NSSize, at frame: NSRect, cache: inout [RootMark: NSImage]) -> NSImage {
        if let cached = cache[self] { return cached }
        let svg = NSImage(data: Data(svg.utf8)) ?? NSImage()
        let image = NSImage(size: size)
        for scale in Self.scales {
            guard
                let bitmap = NSBitmapImageRep(
                    bitmapDataPlanes: nil, pixelsWide: Int(size.width) * scale, pixelsHigh: Int(size.height) * scale,
                    bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
                    bytesPerRow: 0, bitsPerPixel: 0)
            else { continue }
            bitmap.size = size
            NSGraphicsContext.saveGraphicsState()
            NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
            svg.draw(in: frame)
            NSGraphicsContext.restoreGraphicsState()
            image.addRepresentation(bitmap)
        }
        image.isTemplate = true
        image.accessibilityDescription = label
        cache[self] = image
        return image
    }

    /// Each mark, drawn once at each size. Every menu item that shows a mark holds one of
    /// these same images (`NSMenuItem.image` keeps the image it is given, uncopied), so a
    /// caller must never change it: its size and template flag are set once, here.
    private static var images: [RootMark: NSImage] = [:]
    private static var titleLineImages: [RootMark: NSImage] = [:]
}

extension NSMenuItem {
    /// Gives the item a root's mark and `subtitle` together, so the mark always matches
    /// the lines the item has. Every menu that lists roots sets its rows' marks with this.
    ///
    /// The subtitle is kept to one line: one that AppKit would wrap is cut in the middle
    /// (`FolderChooser.oneLine`), measured as AppKit lays the item out, and the whole of it
    /// is the item's tooltip. With a subtitle the mark stands on the title's line
    /// (`RootMark.titleLineImage`); without one it is centered on the item (`image`).
    ///
    /// AppKit wraps a subtitle at about 300 points, or at the title's width where that is
    /// wider (measured on macOS 26.5: 57 characters of a path fit under a short title, 92
    /// under a 64-character one), so the fit is measured under the title: set it first. An
    /// Option alternate, whose title is longer, passes its primary's as `fittedUnder`, so
    /// the two show the same subtitle.
    ///
    /// The check mark stays AppKit's, centered on the item: a custom `onStateImage` drops
    /// the item's `AXMenuItemMarkChar` (checked on macOS 26.5), so VoiceOver would no
    /// longer report the row as checked.
    func setMark(_ mark: RootMark, subtitle: String? = nil, fittedUnder title: String? = nil) {
        let shown = subtitle.map { SubtitleFit.oneLine($0, under: title ?? self.title) }
        self.subtitle = shown
        if let subtitle, shown != subtitle { toolTip = subtitle }
        image = (shown ?? "").isEmpty ? mark.image : mark.titleLineImage
    }
}

/// Which subtitles fit on one line under a menu item's title, measured by AppKit: a menu of
/// one item is as tall with the subtitle as with a one-character one.
private enum SubtitleFit {
    /// What `oneLine` answered, by title and subtitle: a row's first opening measures it,
    /// about 0.25 ms for each `NSMenu.size` on macOS 26.5 and a few for a long subtitle,
    /// and later openings take the answer. Emptied when it reaches `limit` entries.
    private static var answers: [String: String] = [:]
    private static let limit = 256

    /// A menu of one subtitled item, the mark raised, with one line of subtitle.
    private static let oneLineHeight = height(title: "x", subtitle: "x")

    static func oneLine(_ subtitle: String, under title: String) -> String {
        let key = title + "\u{0}" + subtitle
        if let answer = answers[key] { return answer }
        let answer = FolderChooser.oneLine(subtitle) { height(title: title, subtitle: $0) == oneLineHeight }
        if answers.count >= limit { answers.removeAll() }
        answers[key] = answer
        return answer
    }

    private static func height(title: String, subtitle: String) -> CGFloat {
        let item = NSMenuItem(title: title, action: nil, keyEquivalent: "")
        item.subtitle = subtitle
        item.image = RootMark.folder.titleLineImage
        let menu = NSMenu()
        menu.addItem(item)
        return menu.size.height
    }
}
