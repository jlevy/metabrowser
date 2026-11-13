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
    /// The logo, the icon's mark (`TitleBarLogoView`), stands on the title's baseline, 21
    /// points below the title bar's top, a tenth taller than the title font's capitals,
    /// rounded to a Retina pixel: 10 points beside the 13-point title-bar font's 9.16. So
    /// it spans 11 to 21 points down, centered on the buttons' row, and from the
    /// accessory's leading edge, a button gap after the zoom button, it is 14.47 points
    /// wide, to x 92.47.
    private static let markHeight = (primaryFont.capHeight * 1.1 * 2).rounded() / 2
    private static let markWidth = markHeight * TitleBarLogoView.aspectRatio
    /// Where AppKit draws a plain window's title text beside its proxy icon, from the
    /// accessory's leading edge: x 100, so the text's first glyph, at x 102, falls 9.5
    /// points, about a button gap, after the mark.
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
        toolTip = title.subtitle
        logo.represent(url, title: title)
        updateWidth()
        needsLayout = true
    }

    // MARK: - Layout

    private var isRightToLeft: Bool { userInterfaceLayoutDirection == .rightToLeft }

    override func layout() {
        super.layout()
        let height = ceil(measure(title?.segments ?? []).height)
        let y = ((bounds.height - height) / 2).rounded()
        var text = NSRect(x: Self.textInset, y: y, width: max(0, bounds.width - Self.textInset), height: height)
        if isRightToLeft { text.origin.x = bounds.width - text.maxX }
        label.frame = text
        render()
        // On the title's baseline, which the label places once it holds the title.
        let baseline = text.maxY - label.firstBaselineOffsetFromTop
        var mark = NSRect(x: 0, y: baseline, width: Self.markWidth, height: Self.markHeight)
        if isRightToLeft { mark.origin.x = bounds.width - mark.maxX }
        logo.frame = mark
    }

    /// As wide as the whole title, but never past the window's trailing margin, so a
    /// narrow window truncates it.
    private func updateWidth() {
        guard let window, let title else { return }
        let ideal = Self.textInset + measure(title.segments).width
        let available = window.frame.width - leadingDistance(in: window) - Self.windowMargin
        let width = ceil(max(Self.textInset + Self.markWidth, min(ideal, available)))
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

/// The app's logo at the start of the title: the icon's mark alone, the citrine partial M
/// and the amethyst B without the squircle, rim, and panel they sit on in the app icon
/// (`AppIconMark`). It is drawn from the icon masters' own outlines at whatever size and
/// scale the screen needs, so it is as crisp at 1x as on a Retina screen. Both variants'
/// icons draw the same mark, so a development build shows the same logo as a release.
///
/// In a local folder's window it also stands in for the proxy icon AppKit drops beside
/// a leading accessory; elsewhere, as in a cached mirror's window, it is only a logo.
final class TitleBarLogoView: NSImageView, NSDraggingSource {
    /// The mark's width for its height: its ink is 241.654 by 166.977 master units.
    static let aspectRatio = AppIconMark.ink.width / AppIconMark.ink.height
    /// The folder icon a drag shows, the proxy icon's size.
    private static let dragImageSize: CGFloat = 16
    /// The mark's outlines, in the master's units, in drawing order.
    private static let paths = AppIconMark.glyphs.compactMap { AppIconMark.path($0.path) }

    var onPathMenu: (() -> Void)?
    /// The folder the logo stands for, or nil.
    private(set) var url: URL?
    private var pressed: NSEvent?

    init() {
        super.init(frame: .zero)
        imageScaling = .scaleProportionallyUpOrDown
        isEditable = false
        unregisterDraggedTypes()
        // The view, not its image cell, is the accessibility element, so what it says
        // and does is set here, never read from the image it draws: the cell named itself
        // after its image, "AppIcon" for the icon file and nothing for a drawn image
        // (measured on macOS 26.5).
        cell?.setAccessibilityElement(false)
        setAccessibilityRole(.image)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    /// Makes the logo stand for the local folder `url`, which `title` names, or, for nil,
    /// for nothing. A folder's logo is an accessibility element named for the folder,
    /// whose help says what it does; a logo that stands for nothing is decoration, left
    /// out, since the title beside it already says Metabrowser.
    func represent(_ url: URL?, title: WindowTitle) {
        self.url = url
        toolTip = title.subtitle
        setAccessibilityElement(url != nil)
        setAccessibilityLabel(url == nil ? nil : "Folder: \(title.identity.shortName)")
        setAccessibilityHelp(
            url == nil
                ? nil
                : "\(title.identity.fullName). Drag it to copy or alias the folder in another app. "
                + "Command-click, right-click, or Show Menu opens the folder's path menu.")
    }

    /// VoiceOver's Show Menu opens the path menu, as Command-click does.
    override func accessibilityPerformShowMenu() -> Bool {
        guard url != nil, let onPathMenu else { return false }
        onPathMenu()
        return true
    }

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
    /// tints of the same hues on a light one. It needs no shadow or edge on either.
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
        // The folder's own icon, since the folder is what is dragged, centered on the mark.
        let side = Self.dragImageSize
        let frame = NSRect(x: bounds.midX - side / 2, y: bounds.midY - side / 2, width: side, height: side)
        item.setDraggingFrame(frame, contents: NSWorkspace.shared.icon(forFile: url.path(percentEncoded: false)))
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
