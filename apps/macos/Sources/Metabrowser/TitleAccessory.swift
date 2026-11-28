import AppKit
import ShellCore

/// The window title: the folder's short name, bold, and the folder chooser it opens.
///
/// AppKit draws a system title in one style, so the window hides it
/// (`titleVisibility = .hidden`) and shows this leading title-bar accessory instead,
/// which AppKit places beside the window buttons, where macOS 26 puts the system title.
/// The inset and font below reproduce that title as measured on macOS 26.5. The app
/// icon's mark stands at the other end of the title bar (`TitleBarMarkController`).
///
/// The title is a pop-up control: a click opens the folder chooser under it
/// (`FolderChooserMenu`), and a small chevron after it always says so.
///
/// With a leading accessory, AppKit also drops the proxy icon (measured on macOS 26.5),
/// so a folder's window has none to drag; Command-click or right-click on the title
/// opens the folder's path menu.
final class TitleAccessoryController: NSTitlebarAccessoryViewController {
    let navigation = NavigationTitleBar()
    private var titleView: TitleBarTitleView { navigation.chooser }

    init() {
        super.init(nibName: nil, bundle: nil)
        layoutAttribute = .leading
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    override func loadView() { view = navigation }

    /// `url` is the folder whose path menu the title opens, or nil when the window shows
    /// no local folder.
    func show(_ title: WindowTitle, representing url: URL?) {
        loadViewIfNeeded()
        titleView.show(title, representing: url)
        navigation.refit()
    }

    /// The folder chooser the title opens, built when it opens.
    var chooser: (() -> NSMenu?)? {
        get { titleView.chooser }
        set { titleView.chooser = newValue }
    }
}

/// The title as a pop-up control. A click opens the chooser, and a press that moves a few
/// points drags the window instead, as on the rest of the title bar, so a click never
/// moves the window and a drag never opens the chooser; what each event means is
/// `TitleBarPressInteraction`'s, tested in `ShellCore`, as the mark's is.
///
/// It is drawn as macOS draws a title-bar control, not as the page draws one: the system
/// title font, an SF Symbol chevron, and the system's fill for a control under the
/// pointer or while the chooser is open, behind the title and its fixed down chevron.
final class TitleBarTitleView: NSView {
    /// Where AppKit draws a plain window's title without a proxy icon, from the
    /// accessory's leading edge, x 78, a button gap after the zoom button: the label at
    /// x 82, and its first ink at x 84 (measured on macOS 26.5).
    private static let textInset: CGFloat = 4
    /// Space kept between the end of the title and what stands at the title bar's trailing
    /// end: the window's edge, or the mark's accessory.
    private static let trailingMargin: CGFloat = 12
    var sizesToTitle = true
    /// From the end of the title to the chevron, and from the chevron to the hover
    /// surface's end, which reaches as far past the chevron as it does before the title.
    private static let chevronGap: CGFloat = 4
    private static let chevronTrailing: CGFloat = textInset
    /// The hover surface's height and corners, a toolbar button's on macOS 26.5 in a
    /// title bar of `frame.height` 28.
    private static let hoverHeight: CGFloat = 22
    private static let hoverCornerRadius: CGFloat = 6

    private static let font = NSFont.titleBarFont(ofSize: 0)
    /// `chevron.down` at the size a pop-up button draws its indicator beside the system
    /// title font.
    private static let chevronImage: NSImage? = NSImage(
        systemSymbolName: "chevron.down", accessibilityDescription: nil)?
        .withSymbolConfiguration(.init(pointSize: font.pointSize * 0.7, weight: .semibold))

    private let label = NSTextField(labelWithString: "")
    private let chevron = NSImageView()
    /// Measures the title as `label` would draw it.
    private let scratch = NSTextField(labelWithString: "")
    private var title: WindowTitle?
    private var url: URL?
    private var trackingArea: NSTrackingArea?
    private var interaction = TitleBarPressInteraction() {
        didSet {
            if interaction.isHovered != oldValue.isHovered || interaction.isPressed != oldValue.isPressed {
                needsDisplay = true
                render()
            }
        }
    }
    private var chooserIsOpen = false {
        didSet {
            needsDisplay = true
            render()
        }
    }
    /// The press a drag starts from.
    private var pressEvent: NSEvent?
    /// Builds the folder chooser when it opens; nil until the window's controller sets it,
    /// and while it is nil the title is a plain title, with no chevron.
    var chooser: (() -> NSMenu?)? {
        didSet {
            chevron.isHidden = chooser == nil
            setAccessibilityRole(chooser == nil ? .staticText : .popUpButton)
            updateWidth()
            needsLayout = true
        }
    }
    /// Shows the path menu: pops it up under the title.
    var presentPathMenu: (NSMenu, NSPoint, NSView) -> Void = { menu, point, view in
        menu.popUp(positioning: menu.items.first, at: point, in: view)
    }
    /// Shows the chooser: drops it down from under the hover surface's leading corner.
    var presentChooser: (NSMenu, NSPoint, NSView) -> Void = { menu, point, view in
        menu.popUp(positioning: nil, at: point, in: view)
    }
    /// Drags the window from a mouse-down event, as the title bar does.
    var dragWindow: (NSEvent) -> Void = { $0.window?.performDrag(with: $0) }

    init() {
        super.init(frame: NSRect(x: 0, y: 0, width: 0, height: 28))
        for field in [label, scratch] {
            field.lineBreakMode = .byTruncatingTail
            field.usesSingleLineMode = true
            field.maximumNumberOfLines = 1
        }
        label.cell?.truncatesLastVisibleLine = true
        addSubview(label)
        chevron.image = Self.chevronImage
        chevron.isHidden = true
        addSubview(chevron)
        // This view is the title's accessibility element: a pop-up button whose value is
        // the title, once it opens the chooser, and until then static text that reads it.
        // The label, its cell, and the chevron are not elements.
        for element in [label, chevron] as [NSView] { element.setAccessibilityElement(false) }
        label.cell?.setAccessibilityElement(false)
        setAccessibilityElement(true)
        setAccessibilityRole(.staticText)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    func show(_ title: WindowTitle, representing url: URL?) {
        self.title = title
        self.url = url
        toolTip = title.subtitle
        setAccessibilityValue(title.text)
        setAccessibilityHelp(title.subtitle)
        setAccessibilityCustomActions(
            url == nil
                ? []
                : [NSAccessibilityCustomAction(name: "Show Path") { [weak self] in
                    self?.afterAccessibilityAction { $0.showPathMenu() }
                    return true
                }])
        updateWidth()
        needsLayout = true
    }

    // MARK: - Accessibility

    /// VoiceOver's Press and Show Menu open the chooser; a local folder's path menu, which
    /// Command-click opens, is the custom action Show Path. A title with no chooser yet
    /// offers the path menu as Show Menu, as the plain title did.
    override func accessibilityPerformShowMenu() -> Bool {
        if chooser != nil {
            if interaction.accessibilityPressed() == .open { afterAccessibilityAction { $0.showChooser() } }
            return true
        }
        guard url != nil else { return false }
        afterAccessibilityAction { $0.showPathMenu() }
        return true
    }

    override func accessibilityPerformPress() -> Bool {
        guard chooser != nil else { return false }
        if interaction.accessibilityPressed() == .open { afterAccessibilityAction { $0.showChooser() } }
        return true
    }

    /// Opens a menu for an accessibility action on the run loop's next turn, in its
    /// default mode. The action returns first, so VoiceOver is not left waiting inside the
    /// call while the menu tracks, and can follow into the menu once it opens. The block
    /// runs from the run loop, not the main queue: a menu's modal loop entered from a
    /// main-actor job stops every other main-actor job until it closes
    /// (`AppDelegate.onRunLoop`). The default mode keeps it from opening inside another
    /// menu's tracking.
    private func afterAccessibilityAction(_ body: @escaping (TitleBarTitleView) -> Void) {
        let main = CFRunLoopGetMain()
        CFRunLoopPerformBlock(main, CFRunLoopMode.defaultMode.rawValue) { [weak self] in
            MainActor.assumeIsolated {
                if let self { body(self) }
            }
        }
        CFRunLoopWakeUp(main)
    }

    /// Show Menu is offered by a title that opens something: the chooser, or a local
    /// folder's path menu; Press only by one that opens the chooser.
    override func isAccessibilitySelectorAllowed(_ selector: Selector) -> Bool {
        if selector == #selector(accessibilityPerformShowMenu) { return chooser != nil || url != nil }
        if selector == #selector(accessibilityPerformPress) { return chooser != nil }
        return super.isAccessibilitySelectorAllowed(selector)
    }

    // MARK: - Layout

    private var isRightToLeft: Bool { userInterfaceLayoutDirection == .rightToLeft }

    /// The chevron's room after the title, none while there is no chooser: the gap, the
    /// chevron, and the hover surface's reach past it.
    private var chevronRoom: CGFloat {
        guard chooser != nil, let size = Self.chevronImage?.size else { return 0 }
        return Self.chevronGap + size.width + Self.chevronTrailing
    }

    override func layout() {
        super.layout()
        let measured = measure(title?.text ?? "")
        let height = ceil(measured.height)
        let y = ((bounds.height - height) / 2).rounded()
        // The title truncates before the chevron, never under it.
        let width = max(0, min(ceil(measured.width), bounds.width - Self.textInset - chevronRoom))
        var text = NSRect(x: Self.textInset, y: y, width: width, height: height)
        let size = Self.chevronImage?.size ?? .zero
        var mark = NSRect(
            x: text.maxX + Self.chevronGap, y: bounds.midY - size.height / 2, width: size.width,
            height: size.height)
        if isRightToLeft {
            text.origin.x = bounds.width - text.maxX
            mark.origin.x = bounds.width - mark.maxX
        }
        label.frame = text
        chevron.frame = mark
        render()
        updateTrackingAreas()
    }

    /// The hover surface: from the view's leading edge to the chevron's reach past it, at
    /// a toolbar button's height, centered.
    private var hoverRect: NSRect {
        let width = min(bounds.width, Self.textInset + label.frame.width + chevronRoom)
        var rect = NSRect(x: 0, y: ((bounds.height - Self.hoverHeight) / 2).rounded(), width: width, height: Self.hoverHeight)
        if isRightToLeft { rect.origin.x = bounds.width - rect.maxX }
        return rect
    }

    /// As wide as the title and its chevron, but never into the trailing accessories or
    /// past the window's trailing margin, so a narrow window truncates the title.
    private func updateWidth() {
        guard sizesToTitle, let window, let title else { return }
        let ideal = Self.textInset + ceil(measure(title.text).width) + chevronRoom
        let trailing = window.titlebarAccessoryViewControllers
            .filter { $0.layoutAttribute == .trailing }
            .reduce(0) { $0 + $1.view.frame.width }
        let available = window.frame.width - leadingDistance(in: window) - trailing - Self.trailingMargin
        let width = ceil(max(Self.textInset + chevronRoom, min(ideal, available)))
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
        let active = isActive
        label.attributedStringValue = attributed(title.text, active: active)
        label.alignment = isRightToLeft ? .right : .left
        // Match the shell's muted resting ink and stronger ink on hover or while open.
        chevron.contentTintColor =
            !active ? .tertiaryLabelColor
            : interaction.isHovered || interaction.isPressed || chooserIsOpen
                ? .labelColor : .secondaryLabelColor
    }

    /// The system's fill for a control under the pointer, deeper while pressed, resolved in
    /// the plain light or dark appearance as the mark's is (`TitleBarMarkButton.draw`): the
    /// title bar's own vibrant appearance gives fills meant for a visual effect view.
    override func draw(_ dirtyRect: NSRect) {
        guard chooser != nil, interaction.isHovered || interaction.isPressed || chooserIsOpen else { return }
        let dark = effectiveAppearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua
        var fill = NSColor.secondarySystemFill
        let pressed = interaction.isPressed
        NSAppearance(named: dark ? .darkAqua : .aqua)?.performAsCurrentDrawingAppearance {
            let system: NSColor = pressed ? .systemFill : .secondarySystemFill
            fill = NSColor(cgColor: system.cgColor) ?? fill
        }
        fill.setFill()
        NSBezierPath(roundedRect: hoverRect, xRadius: Self.hoverCornerRadius, yRadius: Self.hoverCornerRadius).fill()
    }

    private func measure(_ text: String) -> NSSize {
        scratch.attributedStringValue = attributed(text, active: true)
        return scratch.cell?.cellSize ?? .zero
    }

    private func attributed(_ text: String, active: Bool) -> NSAttributedString {
        let paragraph = NSMutableParagraphStyle()
        paragraph.lineBreakMode = .byTruncatingTail
        return NSAttributedString(string: text, attributes: [
            .font: Self.font,
            .foregroundColor: active ? NSColor.labelColor : NSColor.tertiaryLabelColor,
            .paragraphStyle: paragraph,
        ])
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

    /// The tracking area stops reporting when the window resigns key, so the hover would
    /// stay lit; it goes out then, and when the app resigns active, and a press held
    /// meanwhile opens nothing.
    @objc private func activeStateChanged(_ notification: Notification) {
        if [NSWindow.didResignKeyNotification, NSApplication.didResignActiveNotification].contains(notification.name) {
            interaction.deactivated()
            pressEvent = nil
        }
        render()
    }

    @objc private func windowResized(_ notification: Notification) { updateWidth() }

    // MARK: - Mouse

    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        if let trackingArea { removeTrackingArea(trackingArea) }
        trackingArea = nil
        guard chooser != nil else { return }
        let area = NSTrackingArea(
            rect: hoverRect, options: [.mouseEnteredAndExited, .activeInKeyWindow], owner: self, userInfo: nil)
        addTrackingArea(area)
        trackingArea = area
    }

    override func mouseEntered(with event: NSEvent) { interaction.pointerEntered() }
    override func mouseExited(with event: NSEvent) { interaction.pointerExited() }

    /// A plain title moves the window like the system title; a chooser's title drags it
    /// itself, once a press has moved far enough not to be a click.
    override var mouseDownCanMoveWindow: Bool { chooser == nil }

    /// A chooser's title takes the press that makes its window key, as the mark does: it
    /// is not a window-drag region, so a press it is not given would neither move the
    /// window nor open the chooser. That press opens or drags as in a key window
    /// (`TitleBarPressInteraction`). A plain title leaves the first click to AppKit.
    override func acceptsFirstMouse(for event: NSEvent?) -> Bool { chooser != nil }

    /// A plain title is all title. A chooser's title is a control only where it lights,
    /// the hover surface; the strips above and below it stay title bar, with the title
    /// bar's own drag and double-click.
    override func hitTest(_ point: NSPoint) -> NSView? {
        guard super.hitTest(point) != nil else { return nil }
        guard chooser != nil else { return self }
        return hoverRect.contains(convert(point, from: superview)) ? self : nil
    }

    override func mouseDown(with event: NSEvent) {
        if url != nil, !event.modifierFlags.isDisjoint(with: [.command, .control]) {
            showPathMenu()
        } else if chooser == nil {
            super.mouseDown(with: event)
        } else if event.modifierFlags.contains(.control) {
            // Control-click is a right-click, which opens nothing on a title with no path
            // menu (`rightMouseDown`).
            return
        } else {
            pressEvent = event
            interaction.pressed(at: event.locationInWindow)
        }
    }

    override func mouseDragged(with event: NSEvent) {
        guard chooser != nil else { return super.mouseDragged(with: event) }
        guard let start = pressEvent, interaction.moved(to: event.locationInWindow) == .drag else { return }
        pressEvent = nil
        dragWindow(start)
    }

    override func mouseUp(with event: NSEvent) {
        guard chooser != nil else { return super.mouseUp(with: event) }
        pressEvent = nil
        let inside = hoverRect.contains(convert(event.locationInWindow, from: nil))
        if interaction.released(inside: inside) == .open { showChooser() }
    }

    /// Opens the chooser under the hover surface, its leading corner at the surface's.
    private func showChooser() {
        guard !chooserIsOpen, let menu = chooser?() else { return }
        chooserIsOpen = true
        defer { chooserIsOpen = false }
        let hover = hoverRect
        let anchor = NSPoint(x: isRightToLeft ? hover.maxX : hover.minX, y: hover.minY - 2)
        presentChooser(menu, anchor, self)
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
        // The first row is the root, so it carries its kind's mark; each row above it is an
        // ordinary folder, which is no root's mark.
        let rootMark = RootMark(title?.identity.kind ?? .folder)
        let menu = NSMenu()
        for (index, path) in folders.enumerated() {
            let item = NSMenuItem(
                title: FileManager.default.displayName(atPath: path), action: #selector(openPathMenuItem(_:)),
                keyEquivalent: "")
            item.target = self
            item.representedObject = index == 0 ? [path] : [path, folders[index - 1]]
            // The marks Open Recent and the chooser draw (`RootMark`), not Finder's colored
            // icon for that path: the root's own kind, then the ordinary folder.
            item.setMark(index == 0 ? rootMark : .folder)
            menu.addItem(item)
        }
        let anchor = NSPoint(x: label.frame.minX - 10, y: label.frame.maxY + 4)
        presentPathMenu(menu, anchor, self)
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
