import CoreGraphics

/// Where the app icon's mark sits in the title bar's trailing accessory, which links to
/// the project on GitHub. AppKit places a trailing accessory flush with the window's
/// trailing edge and as tall as the title bar, with or without a tab bar below it
/// (measured on macOS 26.5).
///
/// The mark is 13 points tall and centered in the title bar's height, as the window
/// buttons are. Its ink ends about 9 points before the window's trailing edge, as the
/// close button starts 9 points after the leading edge. A hover highlight reaches a few
/// points past it on every side.
public nonisolated struct TitleBarMarkLayout: Equatable, Sendable {
    public static let markHeight: CGFloat = 13
    /// From the mark's ink to the window's trailing edge: the leading side's 9 points,
    /// from the window's edge to the close button.
    public static let edgeGap: CGFloat = 9
    /// How far the hover highlight reaches past the mark's ink.
    public static let highlightPadding = CGSize(width: 4, height: 3)

    /// The accessory's width: the highlight's reach before the mark, the mark, and the
    /// edge gap, rounded up to a whole point, so the accessory, flush with the window's
    /// edge, starts on a whole point too.
    public let width: CGFloat
    /// The mark's frame in the accessory, y up. It starts on a whole point, so its
    /// leading stem is crisp, and the rounding leaves its ink a fraction of a point
    /// further than `edgeGap` from the window's edge.
    public let mark: CGRect
    /// The hover highlight's frame in the accessory.
    public let highlight: CGRect
    public let isRightToLeft: Bool

    /// - Parameters:
    ///   - markAspectRatio: the mark's ink width for its height.
    ///   - barHeight: the accessory's height, the title bar's.
    public init(markAspectRatio: CGFloat, barHeight: CGFloat, rightToLeft: Bool = false) {
        let size = CGSize(width: Self.markHeight * markAspectRatio, height: Self.markHeight)
        let padding = Self.highlightPadding
        width = (padding.width + size.width + Self.edgeGap).rounded(.up)
        isRightToLeft = rightToLeft
        let x = rightToLeft ? width - padding.width - size.width : padding.width
        // Centered to the nearest half point, a Retina pixel, since 13 points leave an
        // odd 19 of a 32-point title bar.
        let y = (barHeight - size.height).rounded() / 2
        mark = CGRect(x: x, y: y, width: size.width, height: size.height)
        highlight = mark.insetBy(dx: -padding.width, dy: -padding.height)
    }

    /// From the mark's ink to the window's trailing edge.
    public var trailingGap: CGFloat { isRightToLeft ? mark.minX : width - mark.maxX }
}
