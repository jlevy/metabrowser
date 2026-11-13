import CoreGraphics

/// The app icon's mark alone: the partial M and the B, without the squircle, rim, and
/// panel the icon sets them on. The title bar draws it beside the window's title.
///
/// The outlines and fills are the icon masters' own, copied from their glyph group by
/// `AppIcon/make-glyphs.swift` into `AppIconMarkGeometry.swift`, so the mark is the icon's
/// to the thousandth of a unit; the development and release masters draw the same mark
/// (`scripts/build-icon.sh` checks). The icon's pressed-in letter shadow belongs to the
/// panel the letters are pressed into, so the mark alone has none.
public nonisolated enum AppIconMark {
    public struct Glyph: Equatable, Sendable {
        /// SVG path data in the subset make-glyphs writes (absolute M, L, Q, C, and Z), in
        /// the master's 512-unit space with y down.
        public let path: String
        /// The fill, as #RRGGBB.
        public let fill: String
    }

    /// In drawing order: the partial M first, as the master draws it.
    public static var glyphs: [Glyph] { [partialM, b] }

    /// Each glyph's fill on the title bar, in `glyphs` order.
    ///
    /// On the dark title bar, #1E1E1E, the icon's own fills read well: the citrine M
    /// measures 10.0:1 and the amethyst B 7.4:1 (WCAG contrast). On the light one, #FFFFFF,
    /// they measure 1.7:1 and 2.3:1, under the 3:1 that graphics need (WCAG 1.4.11), so the
    /// light title bar alone draws deeper tints of the same hues: each fill's OKLCH
    /// lightness lowered in steps of half a percent, keeping its hue and its share of the
    /// most chroma sRGB holds there, to the first step that reaches 3:1.
    public static func titleBarFills(dark: Bool) -> [String] {
        dark ? glyphs.map(\.fill) : [lightTitleBarM, lightTitleBarB]
    }

    /// oklch(66.9% 0.1147 90.40), from the M's oklch(83.38% 0.1428 90.40) at 0.84 of the
    /// chroma sRGB holds: 3.02:1 against #FFFFFF.
    static let lightTitleBarM = "#B09135"
    /// oklch(69.0% 0.2049 304.96), from the B's oklch(76.03% 0.1539 304.96) at all of the
    /// chroma sRGB holds: 3.01:1 against #FFFFFF.
    static let lightTitleBarB = "#BA73FF"

    /// `data` as a path, or nil for data outside the subset make-glyphs writes.
    public static func path(_ data: String) -> CGPath? {
        let commands: Set<Character> = ["M", "L", "Q", "C", "Z"]
        let path = CGMutablePath()
        var rest = Substring(data)
        while let command = rest.first {
            guard commands.contains(command) else { return nil }
            rest = rest.dropFirst()
            let end = rest.firstIndex { commands.contains($0) } ?? rest.endIndex
            var numbers: [CGFloat] = []
            for field in rest[..<end].split(separator: " ") {
                guard let number = Double(field) else { return nil }
                numbers.append(CGFloat(number))
            }
            rest = rest[end...]
            func point(_ index: Int) -> CGPoint { CGPoint(x: numbers[index], y: numbers[index + 1]) }
            switch (command, numbers.count) {
            case ("M", 2): path.move(to: point(0))
            case ("L", 2): path.addLine(to: point(0))
            case ("Q", 4): path.addQuadCurve(to: point(2), control: point(0))
            case ("C", 6): path.addCurve(to: point(4), control1: point(0), control2: point(2))
            case ("Z", 0): path.closeSubpath()
            default: return nil
            }
        }
        return path.isEmpty ? nil : path
    }

    /// The red, green, and blue of `hex`, #RRGGBB, from 0 to 1 in sRGB, or nil.
    public static func rgb(_ hex: String) -> (red: CGFloat, green: CGFloat, blue: CGFloat)? {
        guard hex.count == 7, hex.first == "#", let value = UInt32(hex.dropFirst(), radix: 16) else { return nil }
        func channel(_ shift: UInt32) -> CGFloat { CGFloat((value >> shift) & 0xFF) / 255 }
        return (channel(16), channel(8), channel(0))
    }
}
