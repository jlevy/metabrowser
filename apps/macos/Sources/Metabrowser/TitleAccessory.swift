import AppKit
import ShellCore

/// The window title: the folder's short name, bold.
///
/// AppKit draws a system title in one style, so the window hides it
/// (`titleVisibility = .hidden`) and shows this leading title-bar accessory instead,
/// which AppKit places beside the window buttons, where macOS 26 puts the system title.
/// The inset and font below reproduce that title as measured on macOS 26.5. The app
/// icon's mark stands at the other end of the title bar (`TitleBarMarkController`).
///
/// With a leading accessory, AppKit also drops the proxy icon (measured on macOS 26.5),
/// so a folder's window has none to drag; Command-click or right-click on the title
/// opens the folder's path menu.
final class TitleAccessoryController: NSTitlebarAccessoryViewController {
    private let titleView = TitleBarTitleView()

    init() {
        super.init(nibName: nil, bundle: nil)
        layoutAttribute = .leading
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    override func loadView() { view = titleView }

    /// `url` is the folder whose path menu the title opens, or nil when the window shows
    /// no local folder.
    func show(_ title: WindowTitle, representing url: URL?) {
        loadViewIfNeeded()
        titleView.show(title, representing: url)
    }
}

final class TitleBarTitleView: NSView {
    /// Where AppKit draws a plain window's title without a proxy icon, from the
    /// accessory's leading edge, x 78, a button gap after the zoom button: the label at
    /// x 82, and its first ink at x 84 (measured on macOS 26.5).
    private static let textInset: CGFloat = 4
    /// Space kept between the end of the title and what stands at the title bar's trailing
    /// end: the window's edge, or the mark's accessory.
    private static let trailingMargin: CGFloat = 12
    /// The path menu's folder icons, as the system title's path menu draws them.
    private static let menuIconSize: CGFloat = 16

    private static let font = NSFont.titleBarFont(ofSize: 0)

    private let label = NSTextField(labelWithString: "")
    /// Measures the title as `label` would draw it.
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
        addSubview(label)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    func show(_ title: WindowTitle, representing url: URL?) {
        self.title = title
        self.url = url
        toolTip = title.subtitle
        updateWidth()
        needsLayout = true
    }

    // MARK: - Layout

    private var isRightToLeft: Bool { userInterfaceLayoutDirection == .rightToLeft }

    override func layout() {
        super.layout()
        let height = ceil(measure(title?.text ?? "").height)
        let y = ((bounds.height - height) / 2).rounded()
        var text = NSRect(x: Self.textInset, y: y, width: max(0, bounds.width - Self.textInset), height: height)
        if isRightToLeft { text.origin.x = bounds.width - text.maxX }
        label.frame = text
        render()
    }

    /// As wide as the title, but never into the trailing accessories or past the window's
    /// trailing margin, so a narrow window truncates it.
    private func updateWidth() {
        guard let window, let title else { return }
        let ideal = Self.textInset + measure(title.text).width
        let trailing = window.titlebarAccessoryViewControllers
            .filter { $0.layoutAttribute == .trailing }
            .reduce(0) { $0 + $1.view.frame.width }
        let available = window.frame.width - leadingDistance(in: window) - trailing - Self.trailingMargin
        let width = ceil(max(Self.textInset, min(ideal, available)))
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
        label.attributedStringValue = attributed(title.text, active: isActive)
        label.alignment = isRightToLeft ? .right : .left
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

    @objc private func activeStateChanged(_ notification: Notification) { render() }
    @objc private func windowResized(_ notification: Notification) { updateWidth() }

    // MARK: - Mouse

    /// The title moves the window like the system title.
    override var mouseDownCanMoveWindow: Bool { true }

    override func hitTest(_ point: NSPoint) -> NSView? {
        super.hitTest(point) == nil ? nil : self
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
        let anchor = NSPoint(x: label.frame.minX - 10, y: label.frame.maxY + 4)
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
