import CoreGraphics

/// Where the app icon's mark sits in the title bar's trailing accessory, which links to
/// the project on GitHub. AppKit places a trailing accessory flush with the window's
/// trailing edge and as tall as the title bar, with or without a tab bar below it
/// (measured on macOS 26.5).
///
/// The mark is 13 points tall and centered in the title bar's height, as the window
/// buttons are. Its ink ends about 14 points before the window's trailing edge, and a
/// square-cornered hover highlight reaches 3 points past it on every side.
public nonisolated struct TitleBarMarkLayout: Equatable, Sendable {
    public static let markHeight: CGFloat = 13
    /// From the mark's ink to the window's trailing edge: 14 points. Compared by eye with
    /// 12 and 16 in renders on macOS 26.5, it balances the window buttons on the leading
    /// side, which start 9 points in, against a mark wider and denser than a button, and
    /// keeps the mark clear of the window's rounded top corner, which the 9 points it first
    /// had crowded.
    public static let edgeGap: CGFloat = 14
    /// How far the hover highlight reaches past the mark's ink, on every side.
    public static let highlightPadding = CGSize(width: 3, height: 3)
    /// The hover highlight's corner radius: none, square as the web page's hover on the
    /// heading that names the folder (`.header-path`, whose `border-radius` is the
    /// chrome radius, 0, measured in Chrome).
    public static let highlightCornerRadius: CGFloat = 0

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
    /// From the hover highlight to the window's trailing edge.
    public var highlightTrailingGap: CGFloat { isRightToLeft ? highlight.minX : width - highlight.maxX }
}
