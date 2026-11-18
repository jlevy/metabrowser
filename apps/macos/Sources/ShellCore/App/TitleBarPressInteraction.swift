import CoreGraphics

/// What a title-bar control that opens something on a click does with the pointer: when
/// it lights, and whether a press opens or drags the window. Two controls use it, and
/// feed it AppKit's events and carry out the effects it returns: the mark
/// (`TitleBarMarkButton`), which opens the project's page, and the title
/// (`TitleBarTitleView`), which opens the folder chooser.
///
/// - A press that is released inside the control's highlight opens, once.
/// - A press that moves `dragDistance` points or more drags the window instead, as the
///   rest of the title bar does, and its release opens nothing.
/// - A press is forgotten when its window resigns key or the app resigns active, so a
///   release after that opens nothing.
/// - The hover goes out when the pointer leaves, and on those same deactivations, which
///   stop the key-window tracking area from reporting the pointer's exit.
/// - A press counts the same whether or not the control was lit: in a window that is not
///   key the tracking area reports no hover, and a press the control is given there
///   still opens.
public nonisolated struct TitleBarPressInteraction: Equatable, Sendable {
    public enum Effect: Equatable, Sendable {
        /// Open what the control opens: the project's page, or the chooser.
        case open
        /// Drag the window from the press.
        case drag
    }

    /// How far a press moves before it is a drag.
    public static let dragDistance: CGFloat = 3

    /// Whether the highlight is lit for the pointer over it.
    public private(set) var isHovered = false
    /// Where a press that may still open began, in window coordinates.
    private var press: CGPoint?

    public init() {}

    /// Whether a press is held that would open on release; the highlight deepens.
    public var isPressed: Bool { press != nil }

    public mutating func pointerEntered() { isHovered = true }
    public mutating func pointerExited() { isHovered = false }

    /// The window resigned key or the app resigned active.
    public mutating func deactivated() {
        isHovered = false
        press = nil
    }

    /// A press began on the highlight at `point`.
    public mutating func pressed(at point: CGPoint) { press = point }

    /// The held press moved to `point`: `.drag`, once, when it has gone `dragDistance`.
    public mutating func moved(to point: CGPoint) -> Effect? {
        guard let start = press, hypot(point.x - start.x, point.y - start.y) >= Self.dragDistance else { return nil }
        press = nil
        return .drag
    }

    /// The press ended, inside the highlight or not: `.open` for a press still held that
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

    /// The page opens in another app, or a menu opens and tracks the pointer itself; either
    /// takes the pointer's attention, so the highlight goes out.
    private mutating func opened() -> Effect {
        isHovered = false
        return .open
    }
}
