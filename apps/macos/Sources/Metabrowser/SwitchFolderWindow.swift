import AppKit
import ShellCore

/// View > Switch Folder…: a panel over the front folder window with a search field and
/// the folder chooser's rows, most recently shown first (`FolderChooser.panelRows`), so
/// Return on the first row goes back to the folder shown before this one. Option-Return
/// opens the selected row in a new window, Command-Delete with nothing typed closes the
/// selected open folder, and Escape, or a click elsewhere, closes the panel.
///
/// The panel is chrome, so it is an AppKit panel, as File > Open URL… is; its state, what
/// each key does, and where it opens are `FolderSwitcher`'s, tested in `ShellCore`, and
/// each choice is carried out as the chooser's is (`AppDelegate.choose`).
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
    /// While `render()` sets the table's selection from `switcher`'s, so the table's
    /// notice of it is not taken for a click.
    private var isRendering = false

    /// Wide enough for a long path in a row's second line, and tall enough for seven rows
    /// whole: the table's clip view measured 296 points, offscreen on macOS 26.5.
    private static let size = NSSize(width: 480, height: 360)
    private static let margin: CGFloat = 12
    /// The field's top below the panel's top, clear of the close button in the transparent
    /// title bar.
    private static let fieldTop: CGFloat = 28
    private static let rowHeight: CGFloat = 38
    private static let cellIdentifier = NSUserInterfaceItemIdentifier("folder")
    /// What `NSEvent.charactersIgnoringModifiers` reads for Return and for Enter.
    private static let returnKeys: Set<String> = ["\r", "\u{3}"]

    /// `rows` builds the panel's rows for the window it opens over; `choose` carries out a
    /// choice; `close` closes the open folder with a key, unless a sheet over one of its
    /// windows refuses it. Either way the panel then lists what is open, so it needs no
    /// answer from `close`.
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
        // Over a full-screen window, in its Space.
        window.collectionBehavior = [.fullScreenAuxiliary]
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
        // A click selects a row without taking the focus from the field, which takes the
        // panel's keys, and Tab cannot move the focus to the table either.
        table.refusesFirstResponder = true
        // A Command-click cannot leave the row Return chooses unselected.
        table.allowsEmptySelection = false
        table.setAccessibilityLabel("Folders")
        // The field and the list share the focus, so VoiceOver reads the selected row as
        // Up and Down move it, as it does for a search field over its results.
        field.setAccessibilitySharedFocusElements([table])
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
            field.topAnchor.constraint(equalTo: content.topAnchor, constant: Self.fieldTop),
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
    /// window a little below its title, and on screen (`FolderSwitcher.frame`). A window
    /// with a page's sheet open (an alert, a confirm, the print panel) cannot switch until
    /// the sheet ends, so the panel does not open over it.
    func show(over window: BrowserWindowController) {
        guard let panel = self.window, let host = window.window else { return }
        guard host.attachedSheet == nil else {
            NSSound.beep()
            return
        }
        over = window
        field.stringValue = ""
        switcher = FolderSwitcher(rows: rows(window))
        render()
        panel.setFrame(
            FolderSwitcher.frame(size: Self.size, over: host.frame, visible: host.screen?.visibleFrame), display: false)
        panel.makeKeyAndOrderFront(nil)
        panel.makeFirstResponder(field)
    }

    /// The open folders changed, perhaps by another route than the panel's own
    /// Command-Delete, as File > Close Folder from the menu bar while the panel is up: it
    /// lists them again, or closes if the window it was opened over has closed.
    func foldersChanged() {
        guard let panel = window, panel.isVisible else { return }
        if let over, over.window?.isVisible == true {
            switcher.reload(rows(over))
            render()
        } else {
            panel.close()
        }
    }

    private func render() {
        let selected = switcher.selected
        isRendering = true
        defer { isRendering = false }
        table.reloadData()
        if let selected {
            table.selectRowIndexes([selected], byExtendingSelection: false)
            table.scrollRowToVisible(selected)
        } else {
            table.deselectAll(nil)
        }
        NSAccessibility.post(element: table, notification: .selectedRowsChanged)
    }

    // MARK: - Keys

    func controlTextDidChange(_ notification: Notification) {
        switcher.search(field.stringValue)
        render()
    }

    /// The field keeps the focus, so it takes the panel's keys, and `FolderSwitcher`
    /// decides what each does (`FolderSwitcher.command`).
    func control(_ control: NSControl, textView: NSTextView, doCommandBy selector: Selector) -> Bool {
        let event = NSApp.currentEvent
        let key = FolderSwitcher.Key(
            command: NSStringFromSelector(selector),
            isReturn: event.map { $0.type == .keyDown && Self.returnKeys.contains($0.charactersIgnoringModifiers ?? "") }
                ?? false,
            option: event?.modifierFlags.contains(.option) == true)
        switch switcher.command(for: key, text: textView.string) {
        case .move(let delta):
            switcher.move(by: delta)
            render()
        case .choose(let newWindow):
            chooseSelected(newWindow: newWindow)
        case .dismiss:
            window?.close()
        case .close(let folder):
            close(folder)
            foldersChanged()
        case .ignore:
            break
        case .edit:
            return false
        }
        return true
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

    // MARK: - The table

    func numberOfRows(in tableView: NSTableView) -> Int { switcher.shown.count }

    func tableViewSelectionDidChange(_ notification: Notification) {
        if !isRendering, table.selectedRow >= 0 { switcher.select(table.selectedRow) }
    }

    func tableView(_ tableView: NSTableView, rowViewForRow row: Int) -> NSTableRowView? {
        FolderRowSelection()
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

/// A row's selection, drawn in the accent color although the table never takes the focus
/// from the field, as Open Quickly's is.
private final class FolderRowSelection: NSTableRowView {
    override var isEmphasized: Bool {
        get { true }
        set {}
    }
}

/// One row of the Switch Folder panel: the root's mark, its title, and its subtitle, as
/// the chooser's menu item shows them, with a check mark at the trailing edge for this
/// window's folder. VoiceOver reads the row as one cell, by its label.
private final class FolderRowView: NSTableCellView {
    private let mark = NSImageView()
    private let title = NSTextField(labelWithString: "")
    private let subtitle = NSTextField(labelWithString: "")
    private let check = NSImageView()
    /// The space between the mark, the text, and the check mark.
    private static let spacing: CGFloat = 8
    /// The row's content inset from the leading and trailing edges of its cell.
    private static let inset: CGFloat = 4

    init() {
        super.init(frame: .zero)
        subtitle.font = .systemFont(ofSize: NSFont.smallSystemFontSize)
        subtitle.textColor = .secondaryLabelColor
        for label in [title, subtitle] { label.lineBreakMode = .byTruncatingMiddle }
        check.image = NSImage(systemSymbolName: "checkmark", accessibilityDescription: "Shown in this window")
        tintImages()
        let text = NSStackView(views: [title, subtitle])
        text.orientation = .vertical
        text.alignment = .leading
        text.spacing = 0
        let line = NSStackView(views: [mark, text, check])
        line.orientation = .horizontal
        line.distribution = .fill
        line.spacing = Self.spacing
        line.alignment = .centerY
        line.translatesAutoresizingMaskIntoConstraints = false
        addSubview(line)
        NSLayoutConstraint.activate([
            mark.widthAnchor.constraint(equalToConstant: RootMark.menuSize.width),
            mark.heightAnchor.constraint(equalToConstant: RootMark.menuSize.height),
            line.leadingAnchor.constraint(equalTo: leadingAnchor, constant: Self.inset),
            line.trailingAnchor.constraint(equalTo: trailingAnchor, constant: -Self.inset),
            line.centerYAnchor.constraint(equalTo: centerYAnchor),
        ])
        // The text takes the room the row has, truncating first, so the check mark sits at
        // the trailing edge whatever the text's length, and keeps its width.
        text.setContentCompressionResistancePriority(.defaultLow, for: .horizontal)
        text.setContentHuggingPriority(.defaultLow, for: .horizontal)
        check.setContentCompressionResistancePriority(.required, for: .horizontal)
        check.setContentHuggingPriority(.required, for: .horizontal)
        imageView = mark
        textField = title
        setAccessibilityElement(true)
        setAccessibilityRole(.cell)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    /// The selected row's emphasized style draws its text in the selection's ink; the
    /// marks follow it there, and are dimmed as the subtitle is elsewhere.
    override var backgroundStyle: NSView.BackgroundStyle {
        didSet { tintImages() }
    }

    private func tintImages() {
        let tint: NSColor? = backgroundStyle == .emphasized ? nil : .secondaryLabelColor
        mark.contentTintColor = tint
        check.contentTintColor = tint
    }

    func show(_ row: FolderChooser.Row) {
        mark.image = row.mark.image
        title.stringValue = row.title
        subtitle.stringValue = row.subtitle
        check.isHidden = !row.isChecked
        setAccessibilityLabel("\(row.title), \(row.subtitle)\(row.isChecked ? ", shown in this window" : "")")
    }
}
