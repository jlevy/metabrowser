import AppKit
import ShellCore

/// The app icon's mark at the title bar's trailing end: a link to the project on GitHub
/// (`ProjectLinks.repository`), which a click opens in the default browser. AppKit keeps
/// a trailing accessory at the window's trailing edge in the title bar's row, with or
/// without a tab bar below it and in full screen (`TitleBarMarkLayout`).
final class TitleBarMarkController: NSTitlebarAccessoryViewController {
    private let button = TitleBarMarkButton()

    init() {
        super.init(nibName: nil, bundle: nil)
        layoutAttribute = .trailing
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    override func loadView() { view = button }
}

/// The mark as a button: a gentle highlight while the pointer is over it, the pointing
/// hand, and a click that opens the project's page. A press that moves a few points
/// becomes a window drag instead, as on the rest of the title bar, so a click never
/// moves the window and a drag never opens the page.
///
/// What each event means is `TitleBarMarkInteraction`'s, tested in `ShellCore`; this view
/// feeds it AppKit's events and carries out the effects it returns, through `openPage`
/// and `dragWindow`.
final class TitleBarMarkButton: NSView {
    private let mark = TitleBarMarkImageView()
    private var trackingArea: NSTrackingArea?
    private var interaction = TitleBarMarkInteraction() {
        didSet {
            if interaction.isHovered != oldValue.isHovered || interaction.isPressed != oldValue.isPressed {
                needsDisplay = true
            }
        }
    }
    /// The press a drag starts from.
    private var pressEvent: NSEvent?
    /// Opens the project's page in the default browser.
    var openPage: () -> Void = { NSWorkspace.shared.open(ProjectLinks.repository) }
    /// Drags the window from a mouse-down event, as the title bar does.
    var dragWindow: (NSEvent) -> Void = { $0.window?.performDrag(with: $0) }

    /// While the pointer is over the highlight's area, in a key window.
    var isHovered: Bool { interaction.isHovered }
    /// While a press that may still open the page is held.
    var isPressed: Bool { interaction.isPressed }

    init() {
        let layout = TitleBarMarkLayout(markAspectRatio: TitleBarMarkImageView.aspectRatio, barHeight: 32)
        super.init(frame: NSRect(x: 0, y: 0, width: layout.width, height: 32))
        addSubview(mark)
        toolTip = ProjectLinks.repositoryLabel
        setAccessibilityElement(true)
        setAccessibilityRole(.button)
        setAccessibilityLabel(ProjectLinks.repositoryLabel)
        setAccessibilityHelp("Opens \(ProjectLinks.repository.absoluteString) in your browser.")
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    private var placement: TitleBarMarkLayout {
        TitleBarMarkLayout(
            markAspectRatio: TitleBarMarkImageView.aspectRatio, barHeight: bounds.height,
            rightToLeft: userInterfaceLayoutDirection == .rightToLeft)
    }

    override func layout() {
        super.layout()
        mark.frame = placement.mark
        updateTrackingAreas()
    }

    // MARK: - Hover

    /// A faint square-cornered box behind the mark (`TitleBarMarkLayout`), in the
    /// system's fill for a control under the pointer, and a little deeper while pressed. The fills are resolved in the plain
    /// light or dark appearance: the title bar's own is the vibrant one, whose fills are
    /// opaque grays meant for a visual effect view to blend (its dark secondary fill
    /// measured gray 0.08, darker than the title bar it would lighten).
    override func draw(_ dirtyRect: NSRect) {
        guard isHovered || isPressed else { return }
        let dark = effectiveAppearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua
        var fill = NSColor.secondarySystemFill
        let pressed = isPressed
        NSAppearance(named: dark ? .darkAqua : .aqua)?.performAsCurrentDrawingAppearance {
            let system: NSColor = pressed ? .systemFill : .secondarySystemFill
            fill = NSColor(cgColor: system.cgColor) ?? fill
        }
        fill.setFill()
        let highlight = placement.highlight
        let radius = TitleBarMarkLayout.highlightCornerRadius
        NSBezierPath(roundedRect: highlight, xRadius: radius, yRadius: radius).fill()
    }

    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        if let trackingArea { removeTrackingArea(trackingArea) }
        let area = NSTrackingArea(
            rect: placement.highlight, options: [.mouseEnteredAndExited, .cursorUpdate, .activeInKeyWindow],
            owner: self, userInfo: nil)
        addTrackingArea(area)
        trackingArea = area
    }

    override func mouseEntered(with event: NSEvent) { interaction.pointerEntered() }
    override func mouseExited(with event: NSEvent) { interaction.pointerExited() }
    override func cursorUpdate(with event: NSEvent) { NSCursor.pointingHand.set() }

    /// The tracking area stops reporting when the window resigns key, so the highlight
    /// would stay lit; it goes out then, and when the app resigns active, and a press held
    /// meanwhile opens nothing.
    @objc private func deactivated(_ notification: Notification) {
        interaction.deactivated()
        pressEvent = nil
    }

    override func viewWillMove(toWindow newWindow: NSWindow?) {
        super.viewWillMove(toWindow: newWindow)
        NotificationCenter.default.removeObserver(self)
    }

    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        guard let window else { return }
        let center = NotificationCenter.default
        center.addObserver(self, selector: #selector(deactivated(_:)), name: NSWindow.didResignKeyNotification, object: window)
        center.addObserver(
            self, selector: #selector(deactivated(_:)), name: NSApplication.didResignActiveNotification, object: NSApp)
    }

    // MARK: - Clicks

    /// Only the highlight's area is the button; the rest of the accessory is title bar.
    override func hitTest(_ point: NSPoint) -> NSView? {
        placement.highlight.contains(convert(point, from: superview)) ? self : nil
    }

    override var mouseDownCanMoveWindow: Bool { false }
    /// A click in a window that is not key opens the page at once, as the window buttons
    /// act on a first click.
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { true }

    override func mouseDown(with event: NSEvent) {
        pressEvent = event
        interaction.pressed(at: event.locationInWindow)
    }

    override func mouseDragged(with event: NSEvent) {
        guard let start = pressEvent, interaction.moved(to: event.locationInWindow) == .drag else { return }
        pressEvent = nil
        dragWindow(start)
    }

    override func mouseUp(with event: NSEvent) {
        pressEvent = nil
        let inside = placement.highlight.contains(convert(event.locationInWindow, from: nil))
        if interaction.released(inside: inside) == .open { openPage() }
    }

    override func accessibilityPerformPress() -> Bool {
        if interaction.accessibilityPressed() == .open { openPage() }
        return true
    }
}

/// The icon's mark alone, the citrine partial M and the amethyst B without the squircle,
/// rim, and panel they sit on in the app icon (`AppIconMark`). It is drawn from the icon
/// masters' own outlines at whatever size and scale the screen needs, so it is as crisp
/// at 1x as on a Retina screen. Both variants' icons draw the same mark.
///
/// An image view, so that AppKit dims it in an inactive window's title bar as it dims a
/// system title's proxy icon. The button around it is the accessibility element and takes
/// every click.
final class TitleBarMarkImageView: NSImageView {
    /// The mark's width for its height: its ink is 241.654 by 166.977 master units.
    static let aspectRatio = AppIconMark.ink.width / AppIconMark.ink.height
    /// The mark's outlines, in the master's units, in drawing order.
    private static let paths = AppIconMark.glyphs.compactMap { AppIconMark.path($0.path) }

    init() {
        super.init(frame: .zero)
        imageScaling = .scaleProportionallyUpOrDown
        isEditable = false
        unregisterDraggedTypes()
        setAccessibilityElement(false)
        cell?.setAccessibilityElement(false)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    override func hitTest(_ point: NSPoint) -> NSView? { nil }

    override func viewDidChangeEffectiveAppearance() {
        super.viewDidChangeEffectiveAppearance()
        updateImage()
    }

    override func setFrameSize(_ newSize: NSSize) {
        let changed = newSize != frame.size
        super.setFrameSize(newSize)
        if changed { updateImage() }
    }

    /// The mark, filling the view, in the title bar's fills for the view's appearance
    /// (`AppIconMark.titleBarFills`): the icon's own on a dark title bar, and deeper
    /// tints of the same hues on a light one.
    private func updateImage() {
        let size = bounds.size
        guard size.width > 0, size.height > 0 else {
            image = nil
            return
        }
        let dark = effectiveAppearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua
        let colors = AppIconMark.titleBarFills(dark: dark).compactMap(AppIconMark.rgb).map {
            CGColor(srgbRed: $0.red, green: $0.green, blue: $0.blue, alpha: 1)
        }
        let paths = Self.paths, ink = AppIconMark.ink
        // Flipped, as the master's y runs down.
        image = NSImage(size: size, flipped: true) { rect in
            guard let context = NSGraphicsContext.current?.cgContext else { return false }
            let scale = min(rect.width / ink.width, rect.height / ink.height)
            context.scaleBy(x: scale, y: scale)
            context.translateBy(x: -ink.minX, y: -ink.minY)
            for (path, color) in zip(paths, colors) {
                context.addPath(path)
                context.setFillColor(color)
                context.fillPath()
            }
            return true
        }
    }
}
