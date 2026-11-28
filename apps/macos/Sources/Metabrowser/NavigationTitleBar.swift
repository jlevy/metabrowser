import AppKit
import ShellCore

/// Owns the leading row's width so the chooser and address can shrink together.
final class NavigationTitleBar: NSView {
    let chooser = TitleBarTitleView()
    let back = NavigationArrow(.back)
    let forward = NavigationArrow(.forward)
    let copy = NSButton()
    private let address = NSButton()
    private let field = NSBox()
    private let backHint = NavigationKeycap("[")
    private let forwardHint = NavigationKeycap("]")
    private var details: NSPopover?
    private var currentURL: URL?
    private var hintsVisible = false
    private var copyFeedback: Task<Void, Never>?
    private var showingCopyFeedback = false
    var validatedURL: (() -> URL?)?

    init() {
        super.init(frame: NSRect(x: 0, y: 0, width: 0, height: 28))
        chooser.sizesToTitle = false
        field.boxType = .custom
        field.cornerRadius = 6
        field.borderWidth = 0.5
        field.borderColor = .separatorColor
        field.fillColor = .quaternarySystemFill
        field.setAccessibilityElement(false)

        copy.image = NSImage(systemSymbolName: "link", accessibilityDescription: nil)
        copy.imagePosition = .imageOnly
        copy.toolTip = "Internal Metabrowser server URL · Click to copy"
        copy.setAccessibilityLabel("Copy internal Metabrowser server URL")
        address.target = self
        address.action = #selector(showDetails)
        address.toolTip = "Show full internal Metabrowser server URL"
        address.setAccessibilityLabel("Show full internal Metabrowser server URL")
        address.alignment = .natural
        address.font = .monospacedSystemFont(ofSize: 11, weight: .regular)
        address.cell?.lineBreakMode = .byTruncatingMiddle
        (address.cell as? NSButtonCell)?.imageDimsWhenDisabled = false
        for button in [copy, address] {
            button.setButtonType(.momentaryChange)
            button.bezelStyle = .accessoryBarAction
        }
        address.isBordered = false
        for view in [chooser, back, forward, field, copy, address, backHint, forwardHint] {
            addSubview(view)
        }
        update(FolderNavigationState(url: nil, back: false, forward: false))
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    func arrow(_ direction: HistoryDirection) -> NavigationArrow { direction == .back ? back : forward }

    override func viewDidMoveToWindow() {
        super.viewDidMoveToWindow()
        refit()
    }

    func refit() {
        guard let window else { return }
        let own = convert(bounds, to: nil)
        let zoom = window.standardWindowButton(.zoomButton).map { $0.convert($0.bounds, to: nil) }
        let isRTL = userInterfaceLayoutDirection == .rightToLeft
        let leading: CGFloat
        if isRTL {
            leading = window.frame.width - min(own.maxX, zoom?.minX ?? own.maxX)
        } else {
            leading = max(own.minX, zoom?.maxX ?? 0)
        }
        let trailing = window.titlebarAccessoryViewControllers
            .filter { $0.layoutAttribute == .trailing }
            .reduce(0) { $0 + $1.view.frame.width }
        // The gap after the field serves as a window drag target beside the project mark.
        let width = floor(max(0, window.frame.width - leading - trailing - 30))
        if abs(width - frame.width) >= 1 { setFrameSize(NSSize(width: width, height: frame.height)) }
        needsLayout = true
    }

    override func layout() {
        super.layout()
        let chooserWidth = max(0, min(174, 126 + (bounds.width - 310) * 0.21, bounds.width - 110))
        let rtl = userInterfaceLayoutDirection == .rightToLeft
        func position(_ view: NSView, at x: CGFloat, y: CGFloat, width: CGFloat, height: CGFloat) {
            view.frame = NSRect(x: rtl ? bounds.width - x - width : x, y: y, width: width, height: height)
        }
        position(chooser, at: 0, y: 0, width: chooserWidth, height: 28)
        position(back, at: chooserWidth + 3, y: 3, width: 27, height: 22)
        position(forward, at: chooserWidth + 30, y: 3, width: 27, height: 22)
        let fieldX = chooserWidth + 62
        let fieldWidth = max(0, bounds.width - fieldX)
        position(field, at: fieldX, y: 3, width: fieldWidth, height: 22)
        position(copy, at: fieldX + 1, y: 3, width: 23, height: 22)
        position(address, at: fieldX + 24, y: 3, width: max(0, fieldWidth - 27), height: 22)
        position(backHint, at: chooserWidth + 16, y: 0, width: 14, height: 14)
        position(forwardHint, at: chooserWidth + 43, y: 0, width: 14, height: 14)
        updateAddressTitle()
    }

    func update(_ state: FolderNavigationState, interactive: Bool = true) {
        if currentURL?.absoluteString != state.url?.absoluteString {
            resetTransientUI(clearHints: false)
            currentURL = state.url
        }
        back.isEnabled = interactive && state.back
        forward.isEnabled = interactive && state.forward
        copy.isEnabled = interactive && currentURL != nil
        address.isEnabled = interactive && currentURL != nil
        updateAddressTitle()
        showHints(hintsVisible)
    }

    func resetTransientUI(clearHints: Bool = true) {
        details?.close()
        details = nil
        copyFeedback?.cancel()
        showingCopyFeedback = false
        updateAddressTitle()
        if clearHints { showHints(false) }
    }

    func showHints(_ visible: Bool) {
        hintsVisible = visible
        backHint.isHidden = !visible || !back.isEnabled
        forwardHint.isHidden = !visible || !forward.isEnabled
    }

    func showCopied() {
        copyFeedback?.cancel()
        showingCopyFeedback = true
        updateAddressTitle()
        NSAccessibility.post(
            element: copy, notification: .announcementRequested,
            userInfo: [.announcement: "URL copied"])
        copyFeedback = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(1200))
            guard !Task.isCancelled, let self else { return }
            showingCopyFeedback = false
            updateAddressTitle()
        }
    }

    private func updateAddressTitle() {
        address.image = nil
        address.imagePosition = .noImage
        if showingCopyFeedback {
            address.title = "URL copied"
        } else if let url = currentURL {
            if address.bounds.width < 65 {
                address.image = NSImage(systemSymbolName: "ellipsis", accessibilityDescription: nil)
                address.imagePosition = .imageOnly
                address.title = ""
            } else {
                let full = url.absoluteString
                let size = (full as NSString).size(withAttributes: [.font: address.font ?? NSFont.systemFont(ofSize: 11)])
                address.title = size.width <= address.bounds.width ? full : compactPath(of: url)
            }
        } else {
            address.title = ""
        }
    }

    private func compactPath(of url: URL) -> String {
        guard let parts = URLComponents(url: url, resolvingAgainstBaseURL: false) else {
            return url.absoluteString
        }
        let path = parts.percentEncodedPath.isEmpty ? "/" : parts.percentEncodedPath
        return path + (parts.percentEncodedQuery.map { "?" + $0 } ?? "")
            + (parts.percentEncodedFragment.map { "#" + $0 } ?? "")
    }

    @objc private func showDetails() {
        guard let url = validatedURL?(), url.absoluteString == currentURL?.absoluteString else { return }
        resetTransientUI()
        let full = NSTextField(string: url.absoluteString)
        full.isEditable = false
        full.isSelectable = true
        full.font = .monospacedSystemFont(ofSize: 12, weight: .regular)
        full.setAccessibilityLabel("Internal Metabrowser server URL")

        let width = min(680, max(290, (window?.frame.width ?? 480) - 36))
        let content = NSView(frame: NSRect(x: 0, y: 0, width: width, height: 76))
        full.frame = NSRect(x: 12, y: 43, width: width - 24, height: 22)
        content.addSubview(full)
        let open = NSButton(title: "Open in Default Browser", target: self, action: #selector(openAddress))
        open.sizeToFit()
        open.frame.origin = NSPoint(x: width - 12 - open.frame.width, y: 9)
        content.addSubview(open)
        let controller = NSViewController()
        controller.view = content
        let popover = NSPopover()
        popover.contentViewController = controller
        popover.contentSize = content.frame.size
        popover.behavior = .transient
        details = popover
        popover.show(relativeTo: address.bounds, of: address, preferredEdge: .minY)
        full.window?.makeFirstResponder(full)
    }

    @objc private func openAddress() {
        guard details?.isShown == true, let url = validatedURL?(),
              url.absoluteString == currentURL?.absoluteString
        else { return }
        NSWorkspace.shared.open(url)
        details?.performClose(nil)
    }

    var ownsFocus: Bool {
        guard let window else { return false }
        if window.firstResponder === window { return true }
        guard let view = window.firstResponder as? NSView, !(view is NSTextView) else { return false }
        return view.isDescendant(of: self)
    }
}

final class NavigationArrow: NSButton {
    let direction: HistoryDirection
    var openHistory: (() -> Void)?

    init(_ direction: HistoryDirection) {
        self.direction = direction
        super.init(frame: .zero)
        let isBack = direction == .back
        let title = isBack ? "Back" : "Forward"
        let key = isBack ? "[" : "]"
        image = NSImage(systemSymbolName: isBack ? "chevron.backward" : "chevron.forward", accessibilityDescription: nil)
        imagePosition = .imageOnly
        bezelStyle = .accessoryBarAction
        setButtonType(.momentaryChange)
        toolTip = "\(title) (⌘\(key) or \(key)) · Hold for history"
        setAccessibilityLabel(title)
        setAccessibilityHelp(toolTip)
        setAccessibilityCustomActions([
            NSAccessibilityCustomAction(name: "Show Menu") { [weak self] in
                self?.accessibilityPerformShowMenu() ?? false
            }
        ])
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    override func isAccessibilitySelectorAllowed(_ selector: Selector) -> Bool {
        if selector == #selector(accessibilityPerformShowMenu) { return isEnabled }
        return super.isAccessibilitySelectorAllowed(selector)
    }

    override func accessibilityPerformShowMenu() -> Bool {
        guard isEnabled else { return false }
        let runLoop = CFRunLoopGetMain()
        CFRunLoopPerformBlock(runLoop, CFRunLoopMode.defaultMode.rawValue) { [weak self] in
            MainActor.assumeIsolated { self?.openHistory?() }
        }
        CFRunLoopWakeUp(runLoop)
        return true
    }

    override func rightMouseDown(with event: NSEvent) {
        if isEnabled { openHistory?() }
    }

    override func mouseDown(with event: NSEvent) {
        guard isEnabled else { return }
        if event.modifierFlags.contains(.control) {
            openHistory?()
            return
        }
        window?.makeFirstResponder(self)
        highlight(true)
        defer { highlight(false) }
        let deadline = Date(timeIntervalSinceNow: 0.42)
        while isEnabled, window?.isKeyWindow == true {
            guard let next = window?.nextEvent(
                matching: [.leftMouseDragged, .leftMouseUp], until: deadline, inMode: .eventTracking, dequeue: true)
            else {
                openHistory?()
                return
            }
            let inside = bounds.contains(convert(next.locationInWindow, from: nil))
            if next.type == .leftMouseUp {
                if inside { sendAction(action, to: target) }
                return
            }
            if !inside { return }
        }
    }
}

private final class NavigationKeycap: NSTextField {
    init(_ key: String) {
        super.init(frame: .zero)
        stringValue = key
        isEditable = false
        isSelectable = false
        isBordered = false
        drawsBackground = false
        font = .systemFont(ofSize: 10, weight: .bold)
        alignment = .center
        wantsLayer = true
        layer?.cornerRadius = 3
        layer?.borderWidth = 1
        setAccessibilityElement(false)
        updateColors()
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    override func hitTest(_ point: NSPoint) -> NSView? { nil }

    override func viewDidChangeEffectiveAppearance() {
        super.viewDidChangeEffectiveAppearance()
        updateColors()
    }

    private func updateColors() {
        let dark = effectiveAppearance.bestMatch(from: [.aqua, .darkAqua]) == .darkAqua
        textColor = dark ? .white : NSColor(white: 0.12, alpha: 1)
        layer?.backgroundColor = dark
            ? NSColor(srgbRed: 0.30, green: 0.26, blue: 0.12, alpha: 1).cgColor
            : NSColor(srgbRed: 0.99, green: 0.94, blue: 0.70, alpha: 1).cgColor
        layer?.borderColor = dark
            ? NSColor(srgbRed: 0.67, green: 0.57, blue: 0.24, alpha: 1).cgColor
            : NSColor(srgbRed: 0.77, green: 0.69, blue: 0.25, alpha: 1).cgColor
    }
}
