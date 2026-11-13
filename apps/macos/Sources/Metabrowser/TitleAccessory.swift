import AppKit
import ShellCore

/// The window title, drawn in two weights: the folder's short name bold, then a bullet
/// and "Metabrowser" in a secondary style.
///
/// AppKit draws a system title in one style, so the window hides it
/// (`titleVisibility = .hidden`) and shows this leading title-bar accessory instead,
/// which AppKit places beside the window buttons, where macOS 26 puts the system title.
/// The insets and fonts below reproduce that title as measured on macOS 26.5.
///
/// With a leading accessory, AppKit also drops the proxy icon (measured on macOS 26.5),
/// so the accessory draws one: drag it to use the folder elsewhere, and Command-click
/// or right-click it, or the title, for the path menu.
final class TitleAccessoryController: NSTitlebarAccessoryViewController {
    private let titleView = TitleBarTitleView()

    init() {
        super.init(nibName: nil, bundle: nil)
        layoutAttribute = .leading
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    override func loadView() { view = titleView }

    /// `url` is the folder the proxy icon stands for, or nil for no icon.
    func show(_ title: WindowTitle, representing url: URL?) {
        loadViewIfNeeded()
        titleView.show(title, representing: url)
    }
}

final class TitleBarTitleView: NSView {
    /// Where AppKit draws a plain window's proxy icon and title, from the accessory's
    /// leading edge (78 points from the window's, after the window buttons).
    private static let iconInset: CGFloat = 4
    private static let iconSize: CGFloat = 16
    private static let textInsetWithIcon: CGFloat = 22
    private static let textInsetWithoutIcon: CGFloat = 4
    /// Space kept between the end of the title and the window's trailing edge.
    private static let windowMargin: CGFloat = 12

    private static let primaryFont = NSFont.titleBarFont(ofSize: 0)
    private static let secondaryFont = NSFont.systemFont(ofSize: primaryFont.pointSize)

    private let label = NSTextField(labelWithString: "")
    private let proxyIcon = ProxyIconView()
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
        proxyIcon.onPathMenu = { [weak self] in self?.showPathMenu() }
        proxyIcon.isHidden = true
        addSubview(proxyIcon)
        addSubview(label)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    func show(_ title: WindowTitle, representing url: URL?) {
        self.title = title
        self.url = url
        proxyIcon.url = url
        toolTip = title.subtitle
        proxyIcon.toolTip = title.subtitle
        updateWidth()
        needsLayout = true
    }

    // MARK: - Layout

    private var textInset: CGFloat { url == nil ? Self.textInsetWithoutIcon : Self.textInsetWithIcon }
    private var isRightToLeft: Bool { userInterfaceLayoutDirection == .rightToLeft }

    override func layout() {
        super.layout()
        let height = ceil(measure(title?.segments ?? []).height)
        let y = ((bounds.height - height) / 2).rounded()
        var text = NSRect(x: textInset, y: y, width: max(0, bounds.width - textInset), height: height)
        var icon = NSRect(x: Self.iconInset, y: y + 1, width: Self.iconSize, height: Self.iconSize)
        if isRightToLeft {
            text.origin.x = bounds.width - text.maxX
            icon.origin.x = bounds.width - icon.maxX
        }
        label.frame = text
        proxyIcon.frame = icon
        render()
    }

    /// As wide as the whole title, but never past the window's trailing margin, so a
    /// narrow window truncates it.
    private func updateWidth() {
        guard let window, let title else { return }
        let ideal = textInset + measure(title.segments).width
        let available = window.frame.width - leadingDistance(in: window) - Self.windowMargin
        let width = ceil(max(textInset + Self.iconSize, min(ideal, available)))
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

    /// The title moves the window like the system title; only the proxy icon keeps its
    /// clicks, for dragging.
    override var mouseDownCanMoveWindow: Bool { true }

    override func hitTest(_ point: NSPoint) -> NSView? {
        guard let hit = super.hitTest(point) else { return nil }
        return hit === proxyIcon ? proxyIcon : self
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
            item.image?.size = NSSize(width: Self.iconSize, height: Self.iconSize)
            menu.addItem(item)
        }
        let anchor = NSPoint(x: proxyIcon.frame.minX - 10, y: label.frame.maxY + 4)
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

/// The folder's icon at the start of the title, standing in for the proxy icon AppKit
/// drops beside a leading accessory.
final class ProxyIconView: NSImageView, NSDraggingSource {
    var onPathMenu: (() -> Void)?
    private var pressed: NSEvent?

    var url: URL? {
        didSet {
            image = url.map { NSWorkspace.shared.icon(forFile: $0.path(percentEncoded: false)) }
            isHidden = url == nil
        }
    }

    init() {
        super.init(frame: .zero)
        imageScaling = .scaleProportionallyUpOrDown
        isEditable = false
        unregisterDraggedTypes()
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

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
        item.setDraggingFrame(bounds, contents: image)
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
