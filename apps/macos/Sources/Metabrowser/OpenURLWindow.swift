import AppKit
import ShellCore

/// File > Open URL…: a panel with one field for a GitHub URL. What it takes, what it says,
/// and when it closes are `OpenURLPanel`'s; this window shows that state and passes on
/// the user's edits, Open, and Cancel. The app asks `metab` about a link Open accepted
/// (`onOpen`), and answers with `answered(_:for:metab:)` or `handOff()`; an edit, Cancel,
/// or closing the panel while it awaits that answer tells the app to stop asking
/// (`onDrop`).
///
/// A panel, so it never becomes the main window: the File and View items aimed at a
/// folder's window still reach the window behind it.
final class OpenURLWindowController: NSWindowController, NSWindowDelegate, NSTextFieldDelegate {
    private var panel = OpenURLPanel()
    private let field = NSTextField()
    private let message = NSTextField(wrappingLabelWithString: "")
    private let spinner = NSProgressIndicator()
    private let openButton = NSButton(title: "Open", target: nil, action: nil)
    private let cancelButton = NSButton(title: "Cancel", target: nil, action: nil)
    private let content = NSStackView()
    /// Open accepted the text: the app asks `metab` about the link.
    private let onOpen: (URL) -> Void
    /// The panel no longer awaits the answer about this link: the app stops its dry run.
    private let onDrop: (URL) -> Void

    /// The panel's width, in points: a pull request's URL shows whole.
    private static let width: CGFloat = 520
    private static let margin: CGFloat = 20

    init(onOpen: @escaping (URL) -> Void, onDrop: @escaping (URL) -> Void) {
        self.onOpen = onOpen
        self.onDrop = onDrop
        let window = NSPanel(
            contentRect: NSRect(x: 0, y: 0, width: Self.width, height: 160),
            styleMask: [.titled, .closable], backing: .buffered, defer: true)
        window.title = "Open URL"
        window.isReleasedWhenClosed = false
        window.hidesOnDeactivate = false
        super.init(window: window)
        window.delegate = self
        build(in: window)
        render()
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    private func build(in window: NSWindow) {
        let inner = Self.width - 2 * Self.margin
        let prompt = NSTextField(wrappingLabelWithString:
            "Open a GitHub repository, pull request, commit, file, or folder in Metabrowser’s copy.")
        prompt.preferredMaxLayoutWidth = inner
        let examples = NSTextField(wrappingLabelWithString: """
            https://github.com/jlevy/metabrowser
            github.com/jlevy/metabrowser
            jlevy/metabrowser
            """)
        examples.preferredMaxLayoutWidth = inner
        examples.font = .monospacedSystemFont(ofSize: NSFont.smallSystemFontSize, weight: .regular)
        examples.textColor = .secondaryLabelColor
        examples.setAccessibilityElement(true)
        examples.setAccessibilityRole(.staticText)
        field.placeholderString = "GitHub link or repository"
        field.setAccessibilityLabel("GitHub link or repository")
        field.usesSingleLineMode = true
        field.cell?.isScrollable = true
        field.cell?.wraps = false
        field.delegate = self
        field.widthAnchor.constraint(equalToConstant: inner).isActive = true
        message.preferredMaxLayoutWidth = inner
        message.textColor = .systemRed
        message.isSelectable = true
        spinner.style = .spinning
        spinner.controlSize = .small
        spinner.isDisplayedWhenStopped = false
        cancelButton.target = self
        cancelButton.action = #selector(cancelPanel(_:))
        cancelButton.keyEquivalent = "\u{1b}"
        openButton.target = self
        openButton.action = #selector(openLink(_:))
        openButton.keyEquivalent = "\r"
        let buttons = NSStackView()
        buttons.orientation = .horizontal
        buttons.addView(spinner, in: .leading)
        buttons.addView(cancelButton, in: .trailing)
        buttons.addView(openButton, in: .trailing)
        buttons.widthAnchor.constraint(equalToConstant: inner).isActive = true
        content.orientation = .vertical
        content.alignment = .leading
        content.spacing = 12
        content.edgeInsets = NSEdgeInsets(top: Self.margin, left: Self.margin, bottom: Self.margin, right: Self.margin)
        for view in [prompt, field, message, examples, buttons] { content.addArrangedSubview(view) }
        content.setCustomSpacing(6, after: field)
        window.contentView = content
        window.initialFirstResponder = field
    }

    /// Brings the panel forward with its field focused. A panel not on screen starts
    /// empty and centered: what it held when it closed, and any answer still on its way,
    /// is dropped.
    func show() {
        guard let window else { return }
        if !window.isVisible {
            if let dropped = panel.cancel() { onDrop(dropped) }
            panel = OpenURLPanel()
            field.stringValue = ""
            render()
            window.center()
        }
        window.makeKeyAndOrderFront(nil)
        window.makeFirstResponder(field)
    }

    /// `metab` answered about `link`: the plan to open, which closes the panel, or nil,
    /// with the panel saying why under the field.
    func answered(_ answer: PresentAnswer, for link: URL, metab: String) -> PresentPlan? {
        let plan = panel.answered(answer, for: link, metab: metab)
        if plan != nil { window?.close() } else { render() }
        return plan
    }

    /// The link being checked, which goes to the link queue instead; the panel closes.
    func handOff() -> URL? {
        let link = panel.handOff()
        if link != nil { window?.close() }
        return link
    }

    @objc private func openLink(_ sender: Any?) {
        let link = panel.open()
        // Open writes a GitHub URL typed without its scheme in full: the field shows it.
        if field.stringValue != panel.text { field.stringValue = panel.text }
        render()
        if let link { onOpen(link) }
    }

    @objc private func cancelPanel(_ sender: Any?) {
        window?.close()
    }

    private func render() {
        openButton.isEnabled = panel.canOpen
        if panel.isChecking { spinner.startAnimation(nil) } else { spinner.stopAnimation(nil) }
        message.stringValue = panel.message ?? ""
        message.isHidden = panel.message == nil
        fit()
    }

    /// Sizes the panel to its content, keeping its top edge where it is, so a message
    /// grows it downward.
    private func fit() {
        guard let window else { return }
        let size = NSSize(width: Self.width, height: content.fittingSize.height)
        var frame = window.frameRect(forContentRect: NSRect(origin: .zero, size: size))
        frame.origin = NSPoint(x: window.frame.minX, y: window.frame.maxY - frame.height)
        guard frame != window.frame else { return }
        window.setFrame(frame, display: window.isVisible)
    }

    // MARK: - NSTextFieldDelegate

    func controlTextDidChange(_ notification: Notification) {
        if let dropped = panel.edit(field.stringValue) { onDrop(dropped) }
        render()
    }

    /// Return opens and Escape cancels from inside the field, whatever the field editor
    /// would do with them.
    func control(_ control: NSControl, textView: NSTextView, doCommandBy selector: Selector) -> Bool {
        switch selector {
        case #selector(NSResponder.insertNewline(_:)):
            openLink(nil)
            return true
        case #selector(NSResponder.cancelOperation(_:)):
            cancelPanel(nil)
            return true
        default:
            return false
        }
    }

    // MARK: - NSWindowDelegate

    func windowWillClose(_ notification: Notification) {
        if let dropped = panel.cancel() { onDrop(dropped) }
        spinner.stopAnimation(nil)
    }
}
