import AppKit
import ShellCore

/// View > Switch Folder…: a panel over the front folder window with a search field and
/// the folder chooser's rows, most recently shown first (`FolderChooser.panelRows`), so
/// Return on the first row goes back to the folder shown before this one. Option-Return
/// opens the selected row in a new window, Command-Delete closes the selected open folder,
/// and Escape, or a click elsewhere, closes the panel.
///
/// The panel is chrome, so it is an AppKit panel, as File > Open URL… is; its state and
/// what each key does are `FolderSwitcher`'s, tested in `ShellCore`, and each choice is
/// carried out as the chooser's is (`AppDelegate.choose`).
final class SwitchFolderWindowController: NSWindowController, NSWindowDelegate, NSSearchFieldDelegate,
    NSTableViewDataSource, NSTableViewDelegate
{
    private var switcher = FolderSwitcher(rows: [])
    /// The window the panel was opened over, which its choices act on.
    private weak var over: BrowserWindowController?
    private let field = NSSearchField()
    private let table = NSTableView()
    private let rows: (BrowserWindowController) -> [FolderChooser.Row]
    private let choose: (FolderChooser.Action, BrowserWindowController?) -> Void
    private let close: (String) -> Void

    /// Wide enough for a long path in a row's second line, and tall enough for eight rows.
    private static let size = NSSize(width: 480, height: 360)
    private static let margin: CGFloat = 12
    private static let rowHeight: CGFloat = 38
    private static let cellIdentifier = NSUserInterfaceItemIdentifier("folder")

    /// `rows` builds the panel's rows for the window it opens over; `choose` carries out a
    /// choice; `close` closes the open folder with a key.
    init(
        rows: @escaping (BrowserWindowController) -> [FolderChooser.Row],
        choose: @escaping (FolderChooser.Action, BrowserWindowController?) -> Void,
        close: @escaping (String) -> Void
    ) {
        self.rows = rows
        self.choose = choose
        self.close = close
        let window = NSPanel(
            contentRect: NSRect(origin: .zero, size: Self.size), styleMask: [.titled, .closable, .fullSizeContentView],
            backing: .buffered, defer: true)
        window.title = "Switch Folder"
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.isReleasedWhenClosed = false
        window.hidesOnDeactivate = true
        super.init(window: window)
        window.delegate = self
        build(in: window)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    private func build(in window: NSWindow) {
        field.placeholderString = "Switch to a folder"
        field.delegate = self
        field.sendsSearchStringImmediately = true
        field.translatesAutoresizingMaskIntoConstraints = false
        let column = NSTableColumn(identifier: Self.cellIdentifier)
        table.addTableColumn(column)
        table.headerView = nil
        table.rowHeight = Self.rowHeight
        table.style = .inset
        table.dataSource = self
        table.delegate = self
        table.target = self
        table.doubleAction = #selector(chooseClicked(_:))
        table.setAccessibilityLabel("Folders")
        let scroll = NSScrollView()
        scroll.documentView = table
        scroll.hasVerticalScroller = true
        scroll.drawsBackground = false
        scroll.translatesAutoresizingMaskIntoConstraints = false
        let content = NSView()
        content.addSubview(field)
        content.addSubview(scroll)
        let margin = Self.margin
        NSLayoutConstraint.activate([
            field.topAnchor.constraint(equalTo: content.topAnchor, constant: margin + 16),
            field.leadingAnchor.constraint(equalTo: content.leadingAnchor, constant: margin),
            field.trailingAnchor.constraint(equalTo: content.trailingAnchor, constant: -margin),
            scroll.topAnchor.constraint(equalTo: field.bottomAnchor, constant: margin / 2),
            scroll.leadingAnchor.constraint(equalTo: content.leadingAnchor),
            scroll.trailingAnchor.constraint(equalTo: content.trailingAnchor),
            scroll.bottomAnchor.constraint(equalTo: content.bottomAnchor, constant: -margin / 2),
        ])
        window.contentView = content
        window.initialFirstResponder = field
    }

    /// Opens the panel over `window`, empty and on its first row, centered across the
    /// window and a little below its title bar.
    func show(over window: BrowserWindowController) {
        guard let panel = self.window, let host = window.window else { return }
        over = window
        field.stringValue = ""
        switcher = FolderSwitcher(rows: rows(window))
        render()
        let frame = host.frame
        panel.setFrameOrigin(NSPoint(
            x: (frame.midX - Self.size.width / 2).rounded(), y: (frame.maxY - 80 - Self.size.height).rounded()))
        panel.makeKeyAndOrderFront(nil)
        panel.makeFirstResponder(field)
    }

    private func render() {
        table.reloadData()
        if let selected = switcher.selected {
            table.selectRowIndexes([selected], byExtendingSelection: false)
            table.scrollRowToVisible(selected)
        } else {
            table.deselectAll(nil)
        }
    }

    // MARK: - Keys

    func controlTextDidChange(_ notification: Notification) {
        switcher.search(field.stringValue)
        render()
    }

    /// The field keeps the focus, so it takes the panel's keys: Up and Down move the
    /// selection, Return and Option-Return choose, Escape closes, and Command-Delete closes
    /// the selected open folder.
    func control(_ control: NSControl, textView: NSTextView, doCommandBy selector: Selector) -> Bool {
        switch selector {
        case #selector(NSResponder.moveUp(_:)):
            move(by: -1)
        case #selector(NSResponder.moveDown(_:)):
            move(by: 1)
        case #selector(NSResponder.insertNewline(_:)):
            chooseSelected(newWindow: NSApp.currentEvent?.modifierFlags.contains(.option) == true)
        case #selector(NSResponder.insertNewlineIgnoringFieldEditor(_:)):
            chooseSelected(newWindow: true)
        case #selector(NSResponder.cancelOperation(_:)):
            window?.close()
        case #selector(NSResponder.deleteToBeginningOfLine(_:)):
            guard let key = switcher.closable else { return false }
            closeFolder(key)
        default:
            return false
        }
        return true
    }

    private func move(by delta: Int) {
        switcher.move(by: delta)
        render()
    }

    private func chooseSelected(newWindow: Bool) {
        guard let action = switcher.choice(newWindow: newWindow) else { return }
        let target = over
        window?.close()
        choose(action, target)
    }

    @objc private func chooseClicked(_ sender: Any?) {
        guard table.clickedRow >= 0 else { return }
        switcher.select(table.clickedRow)
        chooseSelected(newWindow: NSApp.currentEvent?.modifierFlags.contains(.option) == true)
    }

    /// Closes the folder, and lists what is open now; the panel stays, unless the window it
    /// was opened over closed with the folder.
    private func closeFolder(_ key: String) {
        close(key)
        if let over, over.window?.isVisible == true {
            switcher.reload(rows(over))
            render()
        } else {
            window?.close()
        }
    }

    // MARK: - The table

    func numberOfRows(in tableView: NSTableView) -> Int { switcher.shown.count }

    func tableViewSelectionDidChange(_ notification: Notification) {
        if table.selectedRow >= 0 { switcher.select(table.selectedRow) }
    }

    func tableView(_ tableView: NSTableView, viewFor tableColumn: NSTableColumn?, row: Int) -> NSView? {
        let cell = tableView.makeView(withIdentifier: Self.cellIdentifier, owner: self) as? FolderRowView ?? FolderRowView()
        cell.identifier = Self.cellIdentifier
        cell.show(switcher.shown[row])
        return cell
    }

    // MARK: - NSWindowDelegate

    /// A click elsewhere closes the panel, as Spotlight's does.
    func windowDidResignKey(_ notification: Notification) {
        window?.close()
    }
}

/// One row of the Switch Folder panel: the root's mark, its title, and its subtitle, as
/// the chooser's menu item shows them, with a check mark's place for this window's folder.
private final class FolderRowView: NSTableCellView {
    private let mark = NSImageView()
    private let title = NSTextField(labelWithString: "")
    private let subtitle = NSTextField(labelWithString: "")
    private let check = NSImageView()

    init() {
        super.init(frame: .zero)
        subtitle.font = .systemFont(ofSize: NSFont.smallSystemFontSize)
        subtitle.textColor = .secondaryLabelColor
        for label in [title, subtitle] { label.lineBreakMode = .byTruncatingMiddle }
        check.image = NSImage(systemSymbolName: "checkmark", accessibilityDescription: "Shown in this window")
        check.contentTintColor = .secondaryLabelColor
        let text = NSStackView(views: [title, subtitle])
        text.orientation = .vertical
        text.alignment = .leading
        text.spacing = 0
        let line = NSStackView(views: [mark, text, check])
        line.orientation = .horizontal
        line.spacing = 8
        line.alignment = .centerY
        line.translatesAutoresizingMaskIntoConstraints = false
        addSubview(line)
        NSLayoutConstraint.activate([
            mark.widthAnchor.constraint(equalToConstant: RootMark.menuSize.width),
            mark.heightAnchor.constraint(equalToConstant: RootMark.menuSize.height),
            line.leadingAnchor.constraint(equalTo: leadingAnchor, constant: 4),
            line.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -4),
            line.centerYAnchor.constraint(equalTo: centerYAnchor),
        ])
        text.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        imageView = mark
        textField = title
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    func show(_ row: FolderChooser.Row) {
        mark.image = row.mark.image
        mark.contentTintColor = .secondaryLabelColor
        title.stringValue = row.title
        subtitle.stringValue = row.subtitle
        check.isHidden = !row.isChecked
        setAccessibilityLabel("\(row.title), \(row.subtitle)\(row.isChecked ? ", shown in this window" : "")")
    }
}
