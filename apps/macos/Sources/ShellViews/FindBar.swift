import AppKit
import ShellCore

/// The find bar a window shows above its page (Edit > Find, mb-jkbp): a search field,
/// Previous and Next, a "Not Found" note, and Done, laid out as Safari's is. It only
/// reports what the reader does; the window runs each search through `PageFind`.
///
/// In the field, typing searches as it goes, Return finds the next match, Shift-Return
/// the previous one, and Escape closes the bar, as Done does.
@MainActor public final class FindBar: NSView, NSSearchFieldDelegate {
    public let field = NSSearchField()
    private let steps = NSSegmentedControl()
    private let note = NSTextField(labelWithString: "")
    private let done = NSButton(title: "Done", target: nil, action: nil)

    /// The field's text changed: search for it from the current match.
    public var onSearch: ((String) -> Void)?
    /// Previous or Next, from the buttons or the field's Return.
    public var onStep: ((PageFind.Step) -> Void)?
    /// Done, or Escape in the field.
    public var onClose: (() -> Void)?

    public init() {
        super.init(frame: NSRect(x: 0, y: 0, width: 600, height: 34))
        field.placeholderString = "Find on Page"
        field.delegate = self
        field.sendsSearchStringImmediately = true
        field.setAccessibilityLabel("Find on Page")

        steps.segmentCount = 2
        steps.trackingMode = .momentary
        steps.segmentStyle = .separated
        for (index, (symbol, label)) in [("chevron.left", "Previous"), ("chevron.right", "Next")].enumerated() {
            steps.setImage(NSImage(systemSymbolName: symbol, accessibilityDescription: label), forSegment: index)
            steps.setToolTip(label, forSegment: index)
            steps.setWidth(24, forSegment: index)
        }
        steps.target = self
        steps.action = #selector(stepClicked(_:))

        note.textColor = .secondaryLabelColor
        note.font = .systemFont(ofSize: NSFont.smallSystemFontSize)

        done.target = self
        done.action = #selector(doneClicked(_:))
        done.bezelStyle = .rounded
        done.controlSize = .small

        let row = NSStackView(views: [field, steps, note, NSView(), done])
        row.orientation = .horizontal
        row.spacing = 8
        row.edgeInsets = NSEdgeInsets(top: 5, left: 10, bottom: 5, right: 10)
        row.translatesAutoresizingMaskIntoConstraints = false
        field.widthAnchor.constraint(equalToConstant: 260).isActive = true
        let separator = NSBox()
        separator.boxType = .separator
        separator.translatesAutoresizingMaskIntoConstraints = false
        addSubview(row)
        addSubview(separator)
        NSLayoutConstraint.activate([
            row.leadingAnchor.constraint(equalTo: leadingAnchor),
            row.trailingAnchor.constraint(equalTo: trailingAnchor),
            row.topAnchor.constraint(equalTo: topAnchor),
            row.bottomAnchor.constraint(equalTo: separator.topAnchor),
            separator.leadingAnchor.constraint(equalTo: leadingAnchor),
            separator.trailingAnchor.constraint(equalTo: trailingAnchor),
            separator.bottomAnchor.constraint(equalTo: bottomAnchor),
        ])
    }

    @available(*, unavailable)
    public required init?(coder: NSCoder) { fatalError("unused") }

    /// Say whether the last search found anything: nil clears the note.
    public func show(found: Bool?) {
        note.stringValue = found == false ? "Not Found" : ""
    }

    @objc private func stepClicked(_ sender: NSSegmentedControl) {
        onStep?(sender.selectedSegment == 0 ? .previous : .next)
    }

    @objc private func doneClicked(_ sender: Any?) { onClose?() }

    public func controlTextDidChange(_ notification: Notification) {
        onSearch?(field.stringValue)
    }

    public func control(_ control: NSControl, textView: NSTextView, doCommandBy selector: Selector) -> Bool {
        switch selector {
        case #selector(NSResponder.insertNewline(_:)):
            let shift = NSApp.currentEvent?.modifierFlags.contains(.shift) ?? false
            onStep?(shift ? .previous : .next)
            return true
        case #selector(NSResponder.cancelOperation(_:)):
            onClose?()
            return true
        default:
            return false
        }
    }
}
