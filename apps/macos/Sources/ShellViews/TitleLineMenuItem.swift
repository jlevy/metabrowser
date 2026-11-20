import AppKit
import ShellCore

/// A menu item of two lines, a title and a subtitle, whose check mark stands on the
/// title's line, beside the item's mark (`RootMark.TitleLineLayout`), not centered
/// between the two lines, where AppKit draws it. It is the folder chooser's row.
///
/// AppKit centers an item's check, its `onStateImage`, on the whole item. So the item
/// gives it the cure the mark has: the check at the top of an image `2 × rise` taller than
/// its slot, which AppKit centers on the item, so the check's middle is `rise` above the
/// item's middle, on the title's line. An item with no subtitle keeps AppKit's own check,
/// already on its one line.
///
/// The item stays a native one, so its highlight, keyboard selection, Option alternates,
/// and click are AppKit's. That rules out the other ways to move the check, each tried on
/// macOS 26.5: `NSMenu.showsStateColumn = false` still draws the check; an `NSMenuItem.view`
/// draws every part of the row itself, so the highlight and the marks' tint are the view's
/// to redo, and the item never turns into its Option alternate; and the check is no part
/// of the title, so no paragraph or baseline setting of the title reaches it.
///
/// A custom check costs the item its accessibility checked state. AppKit answers
/// `AXMenuItemMarkChar`, the "✓" VoiceOver reads as "checked", only while the item's check
/// is its own image object: it is nil for any other image, even a copy of AppKit's (macOS
/// 26.5). So the item answers it, with what a stock item in the same state answers, and the
/// menu's accessibility children are these items themselves, so an accessibility client
/// reads the same attribute from the same objects as from a stock menu.
public nonisolated final class TitleLineMenuItem: NSMenuItem {
    // `nonisolated`, as `NSMenuItem`'s members are, so that this class can override them.

    /// The check AppKit gives an item: its own image object, which an item keeps its
    /// accessibility checked state with.
    private static let stockCheck = NSMenuItem().onStateImage

    /// A stock item, never in a menu, that says what AppKit answers for each state. Only the
    /// main thread uses it, where AppKit builds, draws, and reads menus, which is why it is
    /// `nonisolated(unsafe)`.
    nonisolated(unsafe) private static let reference = NSMenuItem()

    private static let markChar = NSAccessibility.Attribute(rawValue: kAXMenuItemMarkCharAttribute)

    /// The check the item draws with a subtitle: AppKit's, on the title's line.
    static let raisedCheck = CheckMark.image(raisedBy: RootMark.TitleLineLayout.rise)

    /// The check follows the lines the item has, so a subtitle set later, or cleared,
    /// cannot leave it on the wrong line.
    override public var subtitle: String? {
        didSet { onStateImage = (subtitle ?? "").isEmpty ? Self.stockCheck : Self.raisedCheck }
    }

    /// What AppKit says of a stock item's check, for this item's own check.
    @available(macOS, deprecated: 10.10, message: "The NSAccessibility protocol has no mark character")
    override public func accessibilityAttributeValue(_ attribute: NSAccessibility.Attribute) -> Any? {
        let answer = super.accessibilityAttributeValue(attribute)
        guard answer == nil, attribute == Self.markChar else { return answer }
        Self.reference.state = state
        return Self.reference.accessibilityAttributeValue(attribute)
    }

    /// The check mark AppKit draws in a menu's state column, as an image of its own.
    nonisolated enum CheckMark {
        /// The slot a menu's state column gives a check, whose width the column keeps: a
        /// wider image widens the menu (macOS 26.5: 18 points widen it by 5).
        static let slot = CGSize(width: 13, height: 16)

        /// Where the check's ink is centered in the slot, from its bottom left corner.
        static let inkCenter = CGPoint(x: 6.375, y: 7.5)

        /// What AppKit draws: the SF Symbol `checkmark` at the menu font's 13 points, bold,
        /// small. Drawn into the slot at that center it matches AppKit's check pixel for
        /// pixel, at 9 points of ink tall (macOS 26.5: the two menus' check cells differ by
        /// 0.1 in summed pixel ink, where the system's own image scaled into the slot
        /// differs by 41, and drawn at its own size makes the check 12 points tall).
        static var checkmark: NSImage {
            let symbol = NSImage(systemSymbolName: "checkmark", accessibilityDescription: nil) ?? NSImage()
            return symbol.withSymbolConfiguration(.init(pointSize: 13, weight: .bold, scale: .small)) ?? symbol
        }

        /// The check as a template image `2 × rise` taller than its slot, at the top, with
        /// bitmaps for 1x and 2x screens. It takes the menu's ink and highlight as AppKit's
        /// check does.
        static func image(raisedBy rise: CGFloat) -> NSImage {
            let layout = RootMark.TitleLineLayout(mark: slot, rise: rise)
            let symbol = checkmark
            let ink = inkBounds(of: symbol)
            // The symbol's origin that puts its ink's center at `inkCenter` in the slot.
            let origin = CGPoint(
                x: layout.mark.minX + inkCenter.x - ink.midX, y: layout.mark.minY + inkCenter.y - ink.midY)
            let image = NSImage(size: layout.size)
            for scale in [1, 2] {
                guard let bitmap = bitmap(size: layout.size, scale: scale) else { continue }
                draw(into: bitmap) { symbol.draw(in: CGRect(origin: origin, size: symbol.size)) }
                image.addRepresentation(bitmap)
            }
            image.isTemplate = true
            return image
        }

        /// The box of the symbol's ink, y up, with the symbol's origin at zero: found by
        /// drawing it at 4x, as the symbol's own bounds say nothing of where its stroke is.
        static func inkBounds(of symbol: NSImage) -> CGRect {
            let scale = 4
            let margin: CGFloat = 4
            let size = CGSize(width: symbol.size.width + 2 * margin, height: symbol.size.height + 2 * margin)
            guard let bitmap = bitmap(size: size, scale: scale) else { return CGRect(origin: .zero, size: symbol.size) }
            draw(into: bitmap) { symbol.draw(in: CGRect(origin: CGPoint(x: margin, y: margin), size: symbol.size)) }
            return CheckMark.inkBounds(in: bitmap).offsetBy(dx: -margin, dy: -margin)
        }

        /// The box of `bitmap`'s pixels that are more than a fifth opaque, in points, y up.
        static func inkBounds(in bitmap: NSBitmapImageRep) -> CGRect {
            var minX = Int.max, minY = Int.max, maxX = -1, maxY = -1
            for y in 0..<bitmap.pixelsHigh {
                for x in 0..<bitmap.pixelsWide where (bitmap.colorAt(x: x, y: y)?.alphaComponent ?? 0) > 0.2 {
                    minX = min(minX, x)
                    maxX = max(maxX, x)
                    minY = min(minY, y)
                    maxY = max(maxY, y)
                }
            }
            guard maxX >= 0 else { return .zero }
            let perPoint = CGFloat(bitmap.pixelsWide) / bitmap.size.width
            // `colorAt`'s y runs down from the top; the box's runs up from the bottom.
            return CGRect(
                x: CGFloat(minX) / perPoint, y: bitmap.size.height - CGFloat(maxY + 1) / perPoint,
                width: CGFloat(maxX - minX + 1) / perPoint, height: CGFloat(maxY - minY + 1) / perPoint)
        }

        private static func bitmap(size: CGSize, scale: Int) -> NSBitmapImageRep? {
            let bitmap = NSBitmapImageRep(
                bitmapDataPlanes: nil, pixelsWide: Int(size.width) * scale, pixelsHigh: Int(size.height) * scale,
                bitsPerSample: 8, samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB,
                bytesPerRow: 0, bitsPerPixel: 0)
            bitmap?.size = size
            return bitmap
        }

        private static func draw(into bitmap: NSBitmapImageRep, _ drawing: () -> Void) {
            NSGraphicsContext.saveGraphicsState()
            NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: bitmap)
            drawing()
            NSGraphicsContext.restoreGraphicsState()
        }
    }
}
