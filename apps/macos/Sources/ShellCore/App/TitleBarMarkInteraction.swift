import CoreGraphics

/// What the title bar's mark does with the pointer: when it lights, and whether a press
/// opens the project's page or drags the window. `TitleBarMarkButton` feeds it AppKit's
/// events and carries out the effects it returns.
///
/// - A press that is released inside the mark's capsule opens the page, once.
/// - A press that moves `dragDistance` points or more drags the window instead, as the
///   rest of the title bar does, and its release opens nothing.
/// - A press is forgotten when its window resigns key or the app resigns active, so a
///   release after that opens nothing.
/// - The hover goes out when the pointer leaves, and on those same deactivations, which
///   stop the key-window tracking area from reporting the pointer's exit.
/// - A press counts the same whether or not the mark was lit: in a window that is not
///   key the tracking area reports no hover, and a first click there still opens the
///   page, as the window buttons act on a first click.
public nonisolated struct TitleBarMarkInteraction: Equatable, Sendable {
    public enum Effect: Equatable, Sendable {
        /// Open the project's page in the default browser.
        case open
        /// Drag the window from the press.
        case drag
    }

    /// How far a press moves before it is a drag.
    public static let dragDistance: CGFloat = 3

    /// Whether the capsule is lit for the pointer over it.
    public private(set) var isHovered = false
    /// Where a press that may still open the page began, in window coordinates.
    private var press: CGPoint?

    public init() {}

    /// Whether a press is held that would open the page on release; the capsule deepens.
    public var isPressed: Bool { press != nil }

    public mutating func pointerEntered() { isHovered = true }
    public mutating func pointerExited() { isHovered = false }

    /// The window resigned key or the app resigned active.
    public mutating func deactivated() {
        isHovered = false
        press = nil
    }

    /// A press began on the capsule at `point`.
    public mutating func pressed(at point: CGPoint) { press = point }

    /// The held press moved to `point`: `.drag`, once, when it has gone `dragDistance`.
    public mutating func moved(to point: CGPoint) -> Effect? {
        guard let start = press, hypot(point.x - start.x, point.y - start.y) >= Self.dragDistance else { return nil }
        press = nil
        return .drag
    }

    /// The press ended, inside the capsule or not: `.open` for a press still held that
    /// ends inside it.
    public mutating func released(inside: Bool) -> Effect? {
        defer { press = nil }
        guard press != nil, inside else { return nil }
        return opened()
    }

    /// VoiceOver's press, or any assistive app's.
    public mutating func accessibilityPressed() -> Effect {
        press = nil
        return opened()
    }

    /// The page opens in another app, which takes the pointer's attention: the capsule
    /// goes out.
    private mutating func opened() -> Effect {
        isHovered = false
        return .open
    }
}
