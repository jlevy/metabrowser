import AppKit
import ShellCore
import ShellViews
import WebKit

/// A folder window's GitHub view (`GitHubView`): github.com's page for the window's item,
/// in a web view of its own, below one thin bar. The window shows it in its page's place
/// (`WebContainerView.setPane`), and the page stays beneath it as it was.
///
/// The bar holds only the view toggle, at the right, where the page's own toggle sits,
/// and a quiet line with the page's location on github.com, so the window says which site
/// it shows when you sign in. It has no background of its own: the window's shows through,
/// and a hairline divides it from the page. Reload, Back, Forward, and opening the page in
/// the default browser are in the menus, not the bar.
final class GitHubPane: NSView {
    let webView: DropAwareWebView
    private let bar: GitHubViewBar

    init(webView: DropAwareWebView, showMetabrowser: @escaping () -> Void) {
        self.webView = webView
        bar = GitHubViewBar(showMetabrowser: showMetabrowser)
        super.init(frame: .zero)
        addSubview(webView)
        addSubview(bar)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    /// The page's location, from the web view's `url`.
    func showLocation() {
        bar.show(location: GitHubView.location(webView.url))
    }

    /// A page that did not load: the bar says so until the next one commits.
    func showFailure(_ error: any Error) {
        bar.show(failure: "github.com did not load: \(error.localizedDescription)")
    }

    override func layout() {
        super.layout()
        let height = ViewToggleLayout.barHeight
        bar.frame = NSRect(x: 0, y: bounds.maxY - height, width: bounds.width, height: height)
        webView.frame = NSRect(x: 0, y: 0, width: bounds.width, height: max(0, bounds.height - height))
    }
}

/// The bar above the GitHub view (`ViewToggleLayout`).
final class GitHubViewBar: NSView {
    private let label = NSTextField(labelWithString: "")
    private let toggle: ViewToggleControl

    init(showMetabrowser: @escaping () -> Void) {
        toggle = ViewToggleControl(showMetabrowser: showMetabrowser)
        super.init(frame: .zero)
        label.font = .systemFont(ofSize: NSFont.smallSystemFontSize)
        label.textColor = .secondaryLabelColor
        label.lineBreakMode = .byTruncatingMiddle
        label.maximumNumberOfLines = 1
        label.cell?.usesSingleLineMode = true
        label.setAccessibilityLabel("Location")
        addSubview(label)
        addSubview(toggle)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    func show(location: String) {
        label.stringValue = location
        label.toolTip = location.isEmpty ? nil : location
    }

    func show(failure: String) {
        label.stringValue = failure
        label.toolTip = failure
    }

    private var placement: ViewToggleLayout {
        ViewToggleLayout(
            width: bounds.width, markAspectRatio: ViewToggleControl.metabrowserAspectRatio,
            rightToLeft: userInterfaceLayoutDirection == .rightToLeft)
    }

    override func layout() {
        super.layout()
        let placement = placement
        toggle.frame = placement.toggle
        toggle.place(placement)
        let lineHeight = label.fittingSize.height
        let span = placement.label
        label.frame = NSRect(
            x: span.minX, y: (span.midY - lineHeight / 2).rounded(), width: span.width, height: lineHeight)
        label.alignment = userInterfaceLayoutDirection == .rightToLeft ? .right : .left
    }

    /// The hairline below the bar, in the system's separator color.
    override func draw(_ dirtyRect: NSRect) {
        NSColor.separatorColor.setFill()
        let scale = window?.backingScaleFactor ?? 2
        NSRect(x: 0, y: 0, width: bounds.width, height: 1 / scale).fill()
    }
}

/// The view toggle, as the view header draws its own (`.view-header-toggle` in
/// `styles.css`): a pill of two segments, the Metabrowser mark's and GitHub's, with
/// GitHub's pressed, the view shown, and Metabrowser's a button that shows the window's
/// page again. Its colors are the system's nearest to the page's tokens: the pressed
/// segment's fill and inset line (`--hover-bg`, `--viz-border-strong`), its muted mark
/// (`--muted`), the other mark in the text color (`--text`), and the link color's tint
/// under the pointer (`--highlight-bg`).
final class ViewToggleControl: NSView {
    static let metabrowserAspectRatio = AppIconMark.ink.width / AppIconMark.ink.height

    private let metabrowser: ViewToggleSegment
    private let github: ViewToggleSegment
    private let divider = NSView()

    init(showMetabrowser: @escaping () -> Void) {
        metabrowser = ViewToggleSegment(
            mark: ViewToggleMarks.metabrowser, label: "Metabrowser view", isCurrent: false, select: showMetabrowser)
        metabrowser.toolTip = "Metabrowser view"
        metabrowser.setAccessibilityHelp("Shows this window’s Metabrowser view again.")
        github = ViewToggleSegment(mark: ViewToggleMarks.github, label: "GitHub view", isCurrent: true, select: {})
        github.toolTip = "GitHub view, shown"
        super.init(frame: .zero)
        wantsLayer = true
        layer?.masksToBounds = true
        layer?.borderWidth = ViewToggleLayout.border
        divider.wantsLayer = true
        addSubview(metabrowser)
        addSubview(github)
        addSubview(divider)
        setAccessibilityElement(true)
        setAccessibilityRole(.radioGroup)
        setAccessibilityLabel("View")
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    override var wantsUpdateLayer: Bool { true }

    /// The segments' and marks' frames from `placement`, the bar's, moved into the toggle.
    func place(_ placement: ViewToggleLayout) {
        let origin = placement.toggle.origin
        func local(_ rect: CGRect) -> CGRect { rect.offsetBy(dx: -origin.x, dy: -origin.y) }
        func within(_ rect: CGRect, _ segment: CGRect) -> CGRect {
            rect.offsetBy(dx: -segment.minX, dy: -segment.minY)
        }
        metabrowser.frame = local(placement.metabrowser)
        metabrowser.markFrame = within(placement.metabrowserMark, placement.metabrowser)
        github.frame = local(placement.github)
        github.markFrame = within(placement.githubMark, placement.github)
        // The line between them, inside the second segment, as the page draws it.
        let between = max(placement.metabrowser.minX, placement.github.minX)
        divider.frame = NSRect(
            x: between - origin.x, y: 0, width: ViewToggleLayout.border, height: placement.toggle.height)
        layer?.cornerRadius = placement.toggle.height / 2
    }

    override func updateLayer() {
        effectiveAppearance.performAsCurrentDrawingAppearance {
            layer?.backgroundColor = NSColor.controlBackgroundColor.cgColor
            layer?.borderColor = NSColor.separatorColor.cgColor
            divider.layer?.backgroundColor = NSColor.separatorColor.cgColor
        }
    }
}

/// One segment of the view toggle: a radio button with a mark.
final class ViewToggleSegment: NSButton {
    private let mark: NSImage?
    private let isCurrent: Bool
    private let select: () -> Void
    private var trackingArea: NSTrackingArea?
    private var isHovered = false { didSet { needsDisplay = true } }
    /// Where the mark sits in the segment.
    var markFrame = NSRect.zero { didSet { needsDisplay = true } }

    init(mark svg: String, label: String, isCurrent: Bool, select: @escaping () -> Void) {
        mark = NSImage(data: Data(svg.utf8))
        mark?.isTemplate = true
        self.isCurrent = isCurrent
        self.select = select
        super.init(frame: .zero)
        title = ""
        isBordered = false
        target = self
        action = #selector(chosen(_:))
        setAccessibilityRole(.radioButton)
        setAccessibilityLabel(label)
        setAccessibilityValue(isCurrent ? 1 : 0)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    @objc private func chosen(_ sender: Any?) {
        if !isCurrent { select() }
    }

    override func accessibilityPerformPress() -> Bool {
        chosen(nil)
        return true
    }

    override func updateTrackingAreas() {
        super.updateTrackingAreas()
        if let trackingArea { removeTrackingArea(trackingArea) }
        guard !isCurrent else { return }
        let area = NSTrackingArea(
            rect: bounds, options: [.mouseEnteredAndExited, .activeInKeyWindow, .inVisibleRect], owner: self,
            userInfo: nil)
        addTrackingArea(area)
        trackingArea = area
    }

    override func mouseEntered(with event: NSEvent) { isHovered = true }
    override func mouseExited(with event: NSEvent) { isHovered = false }

    override func draw(_ dirtyRect: NSRect) {
        if isCurrent {
            NSColor.quaternaryLabelColor.setFill()
            bounds.fill()
            NSColor.tertiaryLabelColor.setStroke()
            let inset = NSBezierPath(rect: bounds.insetBy(dx: 0.5, dy: 0.5))
            inset.lineWidth = ViewToggleLayout.border
            inset.stroke()
        } else if isHighlighted || isHovered {
            NSColor.linkColor.withAlphaComponent(isHighlighted ? 0.2 : 0.1).setFill()
            bounds.fill()
        }
        guard let mark else { return }
        let color: NSColor = isCurrent ? .secondaryLabelColor : .labelColor
        let tinted = NSImage(size: markFrame.size, flipped: false) { rect in
            mark.draw(in: rect)
            color.setFill()
            rect.fill(using: .sourceIn)
            return true
        }
        tinted.draw(in: markFrame)
    }
}
