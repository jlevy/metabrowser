import CoreGraphics

/// Where a new folder window opens, and how large, on the screen it opens on.
///
/// A new window is about 80% of the screen's usable height, whatever the screen's size,
/// and wider than tall up to a cap. The first one is centered as AppKit's `center()`
/// centers a window; each next one steps down and to the right of the one before, and
/// starts over at the first position once a step would put any of it off the screen.
///
/// Frames are in AppKit's screen coordinates, whose y axis points up, and `visible` is
/// the screen's `visibleFrame`: without the menu bar, and without the Dock when it shows.
public nonisolated enum NewWindowFrame {
    /// The window's height, as a share of the visible height: the user asked for about
    /// 80% of the screen's height, whatever its size.
    public static let heightFraction: CGFloat = 0.8
    /// The window's width, as a share of the visible width, so a narrow screen still has
    /// room beside it to step the next window right.
    public static let widthFraction: CGFloat = 0.9
    /// The widest a new window opens: a little wider than the 1,200 points it opened at
    /// before, and no wider than reading a page needs on a large display.
    public static let maximumWidth: CGFloat = 1440
    /// How far each next window steps right and down: AppKit's `cascadeTopLeft(from:)`
    /// step for a titled window, measured on macOS 26.5.
    public static let cascadeStep: CGFloat = 29

    /// A new window's frame size on a screen whose visible frame is `visible`, never
    /// smaller than `minimum`, the window's `minSize`. A screen too small for `minimum`
    /// gets `minimum`, and the window runs past the screen's bottom or right edge.
    public static func size(visible: CGRect, minimum: CGSize) -> CGSize {
        let width = min(maximumWidth, visible.width * widthFraction).rounded(.down)
        let height = (visible.height * heightFraction).rounded(.down)
        return CGSize(width: max(minimum.width, width), height: max(minimum.height, height))
    }

    /// The first window's frame: centered across the screen, with a quarter of the free
    /// height above it and three quarters below, as AppKit's `center()` places a window
    /// (measured on macOS 26.5). A window taller or wider than the screen keeps its top
    /// left corner on it, so its title bar can be reached.
    public static func first(size: CGSize, visible: CGRect) -> CGRect {
        let freeWidth = visible.width - size.width
        let freeHeight = visible.height - size.height
        let x = freeWidth >= 0 ? visible.minX + (freeWidth / 2).rounded(.down) : visible.minX
        let y = freeHeight >= 0 ? visible.minY + (freeHeight * 3 / 4).rounded(.down) : visible.maxY - size.height
        return CGRect(origin: CGPoint(x: x, y: y), size: size)
    }

    /// The frame for a new window after `previous`, the frame of the window placed last,
    /// if any: one step down and to the right of it if all of the new window then fits on
    /// the screen, and otherwise the first position. A `previous` on another screen does
    /// not fit, so the window starts at the first position on this one.
    public static func next(size: CGSize, visible: CGRect, after previous: CGRect?) -> CGRect {
        if let previous {
            let stepped = CGRect(
                x: previous.minX + cascadeStep, y: previous.maxY - cascadeStep - size.height,
                width: size.width, height: size.height)
            if visible.contains(stepped) { return stepped }
        }
        return first(size: size, visible: visible)
    }
}
