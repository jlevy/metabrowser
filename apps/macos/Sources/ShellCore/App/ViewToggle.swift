import CoreGraphics

/// The two marks of the view toggle in the bar above a window's GitHub view, as SVG: the
/// same images the view header's toggle masks (`.view-header-toggle-mark` in
/// `src/metabrowser/static/styles.css`), which `ViewToggleTests` checks against the
/// stylesheet. The app draws each as a template, in the segment's color.
public nonisolated enum ViewToggleMarks {
    /// GitHub's mark, 16 by 16 units.
    public static let github = """
        <svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'><path d='M6.766 11.328c-2.063-.25-3.516-1.734-3.516-3.656 0-.781.281-1.625.75-2.188-.203-.515-.172-1.609.063-2.062.625-.078 1.468.25 1.968.703.594-.187 1.219-.281 1.985-.281.765 0 1.39.094 1.953.265.484-.437 1.344-.765 1.969-.687.218.422.25 1.515.046 2.047.5.593.766 1.39.766 2.203 0 1.922-1.453 3.375-3.547 3.64.531.344.89 1.094.89 1.954v1.625c0 .468.391.734.86.547C13.781 14.359 16 11.53 16 8.03 16 3.61 12.406 0 7.984 0 3.563 0 0 3.61 0 8.031a7.88 7.88 0 0 0 5.172 7.422c.422.156.828-.125.828-.547v-1.25c-.219.094-.5.156-.75.156-1.031 0-1.64-.562-2.078-1.609-.172-.422-.36-.672-.719-.719-.187-.015-.25-.093-.25-.187 0-.188.313-.328.625-.328.453 0 .844.281 1.25.86.313.452.64.655 1.031.655s.641-.14 1-.5c.266-.265.47-.5.657-.656'/></svg>
        """

    /// The app icon's mark, the partial M and the B, in the icon masters' units: the
    /// outlines `AppIconMark.glyphs` holds, in a view box of its ink.
    public static let metabrowser = """
        <svg xmlns='http://www.w3.org/2000/svg' viewBox='142.676 172.023 241.654 166.977'>\
        <path d='\(AppIconMark.glyphs[0].path)'/><path d='\(AppIconMark.glyphs[1].path)'/></svg>
        """
}

/// Where the bar above a window's GitHub view puts its parts, y up. The bar is as short as
/// the toggle allows, and the toggle is the view header's, drawn to its measures
/// (`.view-header-toggle` in `src/metabrowser/static/styles.css`) and placed where the
/// header puts it, the page's content padding from the window's trailing edge, so a switch
/// between the views does not move it sideways. The rest of the bar is a one-line label of
/// the page's location.
public nonisolated struct ViewToggleLayout: Equatable, Sendable {
    /// A segment: `--view-header-toggle-option-width` by `--view-header-up-size`.
    public static let segment = CGSize(width: 28, height: 20)
    /// The pill's border, `--chip-border`, and the line between the segments.
    public static let border: CGFloat = 1
    /// The toggle's 22 points and 3 above and below, matching the 3 points the title bar's
    /// own controls keep from its edges.
    public static let barHeight: CGFloat = 28
    /// From the window's edges to the toggle and the label: `--content-padding-x`, the view
    /// header's own inline padding.
    public static let inset: CGFloat = 24
    /// Between the label and the toggle.
    public static let gap: CGFloat = 12
    /// GitHub's mark, `--icon-glyph` square.
    public static let githubMark = CGSize(width: 14, height: 14)
    /// The box the Metabrowser mark is contained in: `--icon-box` by `--icon-glyph`.
    public static let metabrowserMarkBox = CGSize(width: 16, height: 14)

    /// The toggle, its two segments, and their marks, in the bar.
    public let toggle: CGRect
    public let metabrowser: CGRect
    public let github: CGRect
    public let metabrowserMark: CGRect
    public let githubMark: CGRect
    /// The label's span, the bar's height; the label centers its line in it.
    public let label: CGRect

    /// - Parameters:
    ///   - width: the bar's width, the window's.
    ///   - markAspectRatio: the Metabrowser mark's width for its height.
    ///   - rightToLeft: mirrors the bar, as the page mirrors its header.
    public init(width: CGFloat, markAspectRatio: CGFloat, rightToLeft: Bool = false) {
        let segment = Self.segment, border = Self.border
        let size = CGSize(width: 2 * segment.width + 2 * border, height: segment.height + 2 * border)
        let x = rightToLeft ? Self.inset : width - Self.inset - size.width
        toggle = CGRect(origin: CGPoint(x: x, y: ((Self.barHeight - size.height) / 2).rounded()), size: size)
        let first = CGRect(
            x: toggle.minX + border, y: toggle.minY + border, width: segment.width, height: segment.height)
        let second = first.offsetBy(dx: segment.width, dy: 0)
        // The Metabrowser segment leads, in reading order.
        metabrowser = rightToLeft ? second : first
        github = rightToLeft ? first : second
        let box = Self.metabrowserMarkBox
        let fitted = markAspectRatio >= box.width / box.height
            ? CGSize(width: box.width, height: box.width / markAspectRatio)
            : CGSize(width: box.height * markAspectRatio, height: box.height)
        metabrowserMark = Self.centered(fitted, in: metabrowser)
        githubMark = Self.centered(Self.githubMark, in: github)
        let labelWidth = max(0, width - 2 * Self.inset - Self.gap - size.width)
        label = CGRect(
            x: rightToLeft ? toggle.maxX + Self.gap : Self.inset, y: 0, width: labelWidth, height: Self.barHeight)
    }

    /// `size` centered in `rect`, on whole points, so the marks are crisp.
    static func centered(_ size: CGSize, in rect: CGRect) -> CGRect {
        CGRect(
            x: (rect.midX - size.width / 2).rounded(), y: (rect.midY - size.height / 2).rounded(),
            width: size.width, height: size.height)
    }
}
