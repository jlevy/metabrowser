import AppKit
import ShellCore

/// The app's logo and the window title, drawn in two weights: the folder's short name
/// bold, then a bullet and "Metabrowser" in a secondary style.
///
/// AppKit draws a system title in one style, so the window hides it
/// (`titleVisibility = .hidden`) and shows this leading title-bar accessory instead,
/// which AppKit places beside the window buttons, where macOS 26 puts the system title.
/// The text's inset and fonts below reproduce that title as measured on macOS 26.5.
///
/// With a leading accessory, AppKit also drops the proxy icon (measured on macOS 26.5).
/// In its place the accessory draws the app's logo, which stands in for the proxy icon
/// when the window shows a local folder: drag it to use the folder elsewhere, and
/// Command-click or right-click it, or the title, for the path menu.
final class TitleAccessoryController: NSTitlebarAccessoryViewController {
    private let titleView = TitleBarTitleView()

    init() {
        super.init(nibName: nil, bundle: nil)
        layoutAttribute = .leading
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    override func loadView() { view = titleView }

    /// `url` is the folder the logo stands for, or nil when the window shows no local
    /// folder, so the logo is only a logo.
    func show(_ title: WindowTitle, representing url: URL?) {
        loadViewIfNeeded()
        titleView.show(title, representing: url)
    }
}

final class TitleBarTitleView: NSView {
    /// The title bar as measured on macOS 26.5: 32 points tall, with the window buttons
    /// 14-point circles, 9 points apart, from 9 to 23 points below its top, and the
    /// accessory's leading edge at x 78, a button gap after the zoom button.
    ///
    /// The logo, at the accessory's leading edge and centered in its height, is 16
    /// points (`TitleBarLogoView.size`), and its squircle fills the middle 14, a window
    /// button's size. So the squircle sits in the buttons' row: x 79 to 93, 10 points
    /// after the zoom button, and 9 to 23 points below the title bar's top, as they are.
    private static let logoSize = TitleBarLogoView.size
    /// Where AppKit draws a plain window's title text beside its proxy icon, from the
    /// accessory's leading edge: x 100, so the text's first glyph falls about 9 points,
    /// a button gap, after the logo's squircle.
    private static let textInset: CGFloat = 22
    /// Space kept between the end of the title and the window's trailing edge.
    private static let windowMargin: CGFloat = 12
    /// The path menu's folder icons, as the system title's path menu draws them.
    private static let menuIconSize: CGFloat = 16

    private static let primaryFont = NSFont.titleBarFont(ofSize: 0)
    private static let secondaryFont = NSFont.systemFont(ofSize: primaryFont.pointSize)

    private let label = NSTextField(labelWithString: "")
    private let logo = TitleBarLogoView()
    /// Measures runs of segments as `label` would draw them.
    private let scratch = NSTextField(labelWithString: "")
    private var title: WindowTitle?
    private var url: URL?

    init() {
        super.init(frame: NSRect(x: 0, y: 0, width: 0, height: 28))
        for field in [label, scratch] {
            field.lineBreakMode = .byTruncatingTail
            field.usesSingleLineMode = true
            field.maximumNumberOfLines = 1
        }
        label.cell?.truncatesLastVisibleLine = true
        logo.onPathMenu = { [weak self] in self?.showPathMenu() }
        addSubview(logo)
        addSubview(label)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    func show(_ title: WindowTitle, representing url: URL?) {
        self.title = title
        self.url = url
        logo.url = url
        toolTip = title.subtitle
        logo.toolTip = title.subtitle
        updateWidth()
        needsLayout = true
    }

    // MARK: - Layout

    private var isRightToLeft: Bool { userInterfaceLayoutDirection == .rightToLeft }

    override func layout() {
        super.layout()
        let height = ceil(measure(title?.segments ?? []).height)
        let y = ((bounds.height - height) / 2).rounded()
        let logoY = ((bounds.height - Self.logoSize) / 2).rounded()
        var text = NSRect(x: Self.textInset, y: y, width: max(0, bounds.width - Self.textInset), height: height)
        var icon = NSRect(x: 0, y: logoY, width: Self.logoSize, height: Self.logoSize)
        if isRightToLeft {
            text.origin.x = bounds.width - text.maxX
            icon.origin.x = bounds.width - icon.maxX
        }
        label.frame = text
        logo.frame = icon
        render()
    }

    /// As wide as the whole title, but never past the window's trailing margin, so a
    /// narrow window truncates it.
    private func updateWidth() {
        guard let window, let title else { return }
        let ideal = Self.textInset + measure(title.segments).width
        let available = window.frame.width - leadingDistance(in: window) - Self.windowMargin
        let width = ceil(max(Self.textInset + Self.logoSize, min(ideal, available)))
        if abs(frame.width - width) > 0.5 { setFrameSize(NSSize(width: width, height: frame.height)) }
    }

    /// From the window's leading edge to this view's. Until AppKit first places the
    /// accessory, the end of the window buttons stands in for it.
    private func leadingDistance(in window: NSWindow) -> CGFloat {
        let own = convert(bounds, to: nil)
        let buttons = window.standardWindowButton(.zoomButton).map { $0.convert($0.bounds, to: nil) }
        if isRightToLeft {
            return window.frame.width - min(own.maxX, buttons?.minX ?? own.maxX)
        }
        return max(own.minX, buttons?.maxX ?? 0)
    }

    // MARK: - Drawing

    /// A system title dims when its window is not the main window of the active app;
    /// drawn inactive, it measured close to the tertiary label color.
    private var isActive: Bool {
        guard let window else { return false }
        return NSApp.isActive && (window.isMainWindow || window.isKeyWindow)
    }

    private func render() {
        guard let title else { return }
        let shown = title.segments(fitting: Double(label.frame.width)) { Double(measure($0).width) }
        label.attributedStringValue = attributed(shown, active: isActive)
        label.alignment = isRightToLeft ? .right : .left
    }

    private func measure(_ segments: [WindowTitle.Segment]) -> NSSize {
        scratch.attributedStringValue = attributed(segments, active: true)
        return scratch.cell?.cellSize ?? .zero
    }

    private func attributed(_ segments: [WindowTitle.Segment], active: Bool) -> NSAttributedString {
        let paragraph = NSMutableParagraphStyle()
        paragraph.lineBreakMode = .byTruncatingTail
        let result = NSMutableAttributedString()
        for segment in segments {
            let primary = segment.style == .primary
            let color: NSColor = !active ? .tertiaryLabelColor : primary ? .labelColor : .secondaryLabelColor
            result.append(NSAttributedString(string: segment.text, attributes: [
                .font: primary ? Self.primaryFont : Self.secondaryFont,
                .foregroundColor: color,
                .paragraphStyle: paragraph,
            ]))
        }
        return result
    }

    override func viewDidChangeEffectiveAppearance() {
        super.viewDidChangeEffectiveAppearance()
        render()
    }

    // MARK: - Window state

    override func viewWillMove(toWindow newWindow: NSWindow?) {
        super.viewWillMove(toWindow: newWindow)
        NotificationCenter.default.removeObserver(self)
    }

    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        guard let window else { return }
        let center = NotificationCenter.default
        for name in [
            NSWindow.didBecomeMainNotification, NSWindow.didResignMainNotification,
            NSWindow.didBecomeKeyNotification, NSWindow.didResignKeyNotification,
        ] {
            center.addObserver(self, selector: #selector(activeStateChanged(_:)), name: name, object: window)
        }
        for name in [NSApplication.didBecomeActiveNotification, NSApplication.didResignActiveNotification] {
            center.addObserver(self, selector: #selector(activeStateChanged(_:)), name: name, object: NSApp)
        }
        center.addObserver(self, selector: #selector(windowResized(_:)), name: NSWindow.didResizeNotification, object: window)
        updateWidth()
        needsLayout = true
    }

    @objc private func activeStateChanged(_ notification: Notification) { render() }
    @objc private func windowResized(_ notification: Notification) { updateWidth() }

    // MARK: - Mouse

    /// The title moves the window like the system title; only the logo of a folder's
    /// window keeps its clicks, for dragging the folder.
    override var mouseDownCanMoveWindow: Bool { true }

    override func hitTest(_ point: NSPoint) -> NSView? {
        guard let hit = super.hitTest(point) else { return nil }
        return hit === logo && url != nil ? logo : self
    }

    override func mouseDown(with event: NSEvent) {
        if url != nil, !event.modifierFlags.isDisjoint(with: [.command, .control]) {
            showPathMenu()
        } else {
            super.mouseDown(with: event)
        }
    }

    override func rightMouseDown(with event: NSEvent) {
        if url != nil { showPathMenu() } else { super.rightMouseDown(with: event) }
    }

    /// The folder, then each folder that contains it, as the system title's path menu
    /// lists them. Choosing the folder opens it in Finder; choosing an ancestor opens
    /// that one with the next folder down selected.
    private func showPathMenu() {
        guard let url else { return }
        let folders = WindowTitle.pathMenuFolders(for: url.path(percentEncoded: false))
        let menu = NSMenu()
        for (index, path) in folders.enumerated() {
            let item = NSMenuItem(
                title: FileManager.default.displayName(atPath: path), action: #selector(openPathMenuItem(_:)),
                keyEquivalent: "")
            item.target = self
            item.representedObject = index == 0 ? [path] : [path, folders[index - 1]]
            item.image = NSWorkspace.shared.icon(forFile: path)
            item.image?.size = NSSize(width: Self.menuIconSize, height: Self.menuIconSize)
            menu.addItem(item)
        }
        let anchor = NSPoint(x: logo.frame.minX - 10, y: label.frame.maxY + 4)
        menu.popUp(positioning: menu.items.first, at: anchor, in: self)
    }

    @objc private func openPathMenuItem(_ item: NSMenuItem) {
        guard let paths = item.representedObject as? [String], let folder = paths.first else { return }
        if paths.count > 1 {
            NSWorkspace.shared.selectFile(paths[1], inFileViewerRootedAtPath: folder)
        } else {
            NSWorkspace.shared.selectFile(nil, inFileViewerRootedAtPath: folder)
        }
    }
}

/// The app's logo at the start of the title: the bundle's own icon, the one the Dock
/// shows, so a development build shows the canary icon and a release the published one.
/// The icon brings its own background, the squircle with its rim and panel.
///
/// In a local folder's window it also stands in for the proxy icon AppKit drops beside
/// a leading accessory; elsewhere, as in a cached mirror's window, it is only a logo.
final class TitleBarLogoView: NSImageView, NSDraggingSource {
    /// The icon's smallest size, whose own 16- and 32-pixel images a 1x and a Retina
    /// screen draw unscaled. Its squircle fills the middle 14 points (14 of 16 pixels,
    /// and 28 of 32, measured), and the transparent point around it holds the shadow.
    static let size: CGFloat = 16
    private static let squircleSize: CGFloat = 14
    /// A rounded rectangle's corner radius that follows the squircle's corners at that
    /// size. The rim's corner is 94 of its 434 units at 60% smoothing
    /// (`AppIcon/README.md`), 3 points unsmoothed; the smoothing carries the curve
    /// further, and of 3, 3.5, and 4 points, 4 followed the corners most closely,
    /// leaving no gap there (compared at 8 times on macOS 26.5).
    private static let squircleRadius: CGFloat = 4
    /// A very slight drop shadow, close by eye and by pixel to the one macOS 26.5 draws
    /// under the same icon at this size (`NSImage.applicationIconName`): it darkens the
    /// light title bar beside the squircle by at most a few percent, and a little more
    /// below it.
    private static let shadowOffset = NSSize(width: 0, height: -0.5)
    private static let shadowBlurRadius: CGFloat = 1
    private static let shadowAlpha: CGFloat = 0.3
    /// In dark mode the icon's near-black panel and dark rim almost match the title bar:
    /// the release icon's rim measured 1.2:1 against it on macOS 26.5, where the panel
    /// measured 16:1 against the light one. So in dark mode a hairline just outside the
    /// squircle draws its edge, as macOS 26 lights icons' edges in dark mode, and the
    /// shadow, which would not show, is left off.
    private static let darkEdgeWidth: CGFloat = 0.5

    /// The icon file `CFBundleIconFile` names, with every size the icon has: drawn from
    /// its bitmaps at once. `NSApp.applicationIconImage` is a single 256-pixel snapshot,
    /// and `NSImage(named: NSImage.applicationIconName)`, which IconServices renders,
    /// first drew as an empty placeholder (both measured on macOS 26.5). Outside a bundle,
    /// as in `swift run`, the application icon stands in.
    private static let icon: NSImage? = {
        let name = Bundle.main.object(forInfoDictionaryKey: "CFBundleIconFile") as? String
        return name.flatMap { Bundle.main.image(forResource: $0) } ?? NSApp.applicationIconImage
    }()

    var onPathMenu: (() -> Void)?
    /// The folder the logo stands for, or nil.
    var url: URL?
    private var pressed: NSEvent?

    init() {
        super.init(frame: .zero)
        imageScaling = .scaleProportionallyUpOrDown
        isEditable = false
        unregisterDraggedTypes()
        updateImage()
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    override func viewDidChangeEffectiveAppearance() {
        super.viewDidChangeEffectiveAppearance()
        updateImage()
    }

    private func updateImage() {
        guard let icon = Self.icon else { return }
        guard effectiveAppearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua else {
            let shadow = NSShadow()
            shadow.shadowOffset = Self.shadowOffset
            shadow.shadowBlurRadius = Self.shadowBlurRadius
            shadow.shadowColor = NSColor.black.withAlphaComponent(Self.shadowAlpha)
            self.shadow = shadow
            image = icon
            return
        }
        shadow = nil
        // The tertiary label color, white at a quarter, resolved in the plain dark
        // appearance: the title bar's own is the vibrant one, whose label colors are
        // opaque grays meant for a visual effect view to blend (its tertiary measured
        // gray 0.25), and this image is drawn without vibrancy.
        var edge = NSColor.tertiaryLabelColor
        NSAppearance(named: .darkAqua)?.performAsCurrentDrawingAppearance {
            edge = NSColor(cgColor: NSColor.tertiaryLabelColor.cgColor) ?? edge
        }
        let side = Self.squircleSize, radius = Self.squircleRadius, width = Self.darkEdgeWidth
        image = NSImage(size: NSSize(width: Self.size, height: Self.size), flipped: false) { rect in
            icon.draw(in: rect)
            let squircle = rect.insetBy(dx: (rect.width - side) / 2, dy: (rect.height - side) / 2)
            let hairline = NSBezierPath(
                roundedRect: squircle.insetBy(dx: -width / 2, dy: -width / 2),
                xRadius: radius + width / 2, yRadius: radius + width / 2)
            hairline.lineWidth = width
            edge.setStroke()
            hairline.stroke()
            return true
        }
    }

    override var mouseDownCanMoveWindow: Bool { false }

    override func mouseDown(with event: NSEvent) {
        if !event.modifierFlags.isDisjoint(with: [.command, .control]) {
            onPathMenu?()
        } else {
            pressed = event
        }
    }

    override func rightMouseDown(with event: NSEvent) { onPathMenu?() }
    override func mouseUp(with event: NSEvent) { pressed = nil }

    override func mouseDragged(with event: NSEvent) {
        guard let start = pressed, let url else { return }
        let dx = event.locationInWindow.x - start.locationInWindow.x
        let dy = event.locationInWindow.y - start.locationInWindow.y
        guard dx * dx + dy * dy >= 9 else { return }
        pressed = nil
        let item = NSDraggingItem(pasteboardWriter: url as NSURL)
        // The folder's own icon, since the folder is what is dragged.
        item.setDraggingFrame(bounds, contents: NSWorkspace.shared.icon(forFile: url.path(percentEncoded: false)))
        beginDraggingSession(with: [item], event: start, source: self)
    }

    /// Copy or alias only, and only to other apps. A move (Finder's default for a drag
    /// within a volume) would pull the folder out from under its server, and a drop on
    /// this app's own windows would only reopen the folder.
    func draggingSession(
        _ session: NSDraggingSession, sourceOperationMaskFor context: NSDraggingContext
    ) -> NSDragOperation {
        context == .outsideApplication ? [.copy, .link] : []
    }
}
