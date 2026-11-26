import AppKit
import ShellCore
import SwiftUI

/// The panes of Metabrowser > Settings…, in the order of their toolbar tabs.
enum SettingsTab: Int, CaseIterable {
    /// Whether the last session reopens.
    case general
    /// The `metab` in use, how it was found, and the search for another.
    case runtime
    /// The plugins a new server discovers with that `metab`.
    case plugins
    /// The report of `metab --doctor --json`, which Help > Check Setup… also shows.
    case checkSetup

    var label: String {
        switch self {
        case .general: "General"
        case .runtime: "Runtime"
        case .plugins: "Plugins"
        case .checkSetup: "Check Setup"
        }
    }

    /// The tab's symbol, beside its label: the label names the pane, so the image is
    /// decorative and says nothing to assistive apps.
    var image: NSImage? {
        switch self {
        case .general: NSImage(systemSymbolName: "gearshape", accessibilityDescription: nil)
        case .runtime: NSImage(systemSymbolName: "terminal", accessibilityDescription: nil)
        case .plugins: NSImage(systemSymbolName: "puzzlepiece.extension", accessibilityDescription: nil)
        case .checkSetup: NSImage(systemSymbolName: "stethoscope", accessibilityDescription: nil)
        }
    }

    /// Every pane's width, so the window keeps its width from tab to tab, as the system's
    /// own settings windows do, and only its height follows the pane.
    static let width: CGFloat = 660
}

/// The Settings window: a toolbar of tabs, one per `SettingsTab`, as macOS's own settings
/// windows have. `NSTabViewController` sizes the window to each pane's ideal size when
/// its tab is chosen, keeping the top edge, and again when the pane shown grows or shrinks
/// (`NSHostingController.sizingOptions`).
final class SettingsWindowController: NSWindowController {
    private let tabs = SettingsTabsController()

    /// A pane came on screen: its tab was chosen. `show(_:)` calls it too, for the pane it
    /// brings forward.
    var onShow: (SettingsTab) -> Void = { _ in }

    init(
        runtime: RuntimeModel, runtimeActions: RuntimeActions, plugins: PluginListModel,
        checkSetup: CheckSetupModel, checkSetupActions: CheckSetupActions
    ) {
        tabs.tabStyle = .toolbar
        for tab in SettingsTab.allCases {
            let pane: NSViewController =
                switch tab {
                case .general: Self.pane(GeneralSettingsView())
                case .runtime: Self.pane(RuntimeView(model: runtime, actions: runtimeActions))
                case .plugins: Self.pane(PluginsView(runtime: runtime, model: plugins))
                case .checkSetup: Self.pane(CheckSetupView(model: checkSetup, actions: checkSetupActions))
                }
            // The window's title names the pane shown, as in the system's settings windows.
            pane.title = tab.label
            let item = NSTabViewItem(viewController: pane)
            item.label = tab.label
            item.image = tab.image
            tabs.addTabViewItem(item)
        }
        let window = NSWindow(contentViewController: tabs)
        window.styleMask = [.titled, .closable, .miniaturizable]
        window.toolbarStyle = .preference
        window.isReleasedWhenClosed = false
        super.init(window: window)
        tabs.didSelect = { [weak self] index in
            guard let self, let tab = SettingsTab(rawValue: index) else { return }
            onShow(tab)
        }
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }

    /// The pane on screen, or the one the window shows when it next opens.
    var selected: SettingsTab { SettingsTab(rawValue: tabs.selectedTabViewItemIndex) ?? .general }

    private var placed = false

    /// Brings the window forward on `tab`, or on the pane it showed last.
    func show(_ tab: SettingsTab?) {
        if let tab, tab != selected {
            tabs.selectedTabViewItemIndex = tab.rawValue  // which calls `onShow`
        } else {
            onShow(selected)
        }
        showWindow(nil)
        if !placed, let window {
            placed = true
            Self.place(window)
        }
        window?.makeKeyAndOrderFront(nil)
    }

    private static func pane(_ view: some View) -> NSViewController {
        let hosting = NSHostingController(rootView: view)
        hosting.sizingOptions = .preferredContentSize
        return hosting
    }

    /// Centers the window, the first time it shows, as if it showed its tallest pane, Check
    /// Setup, whose height is fixed: the window grows and shrinks from its top edge, so
    /// every pane then fits on the screen it opened on. It runs once the window is on screen
    /// and before it draws, when its title bar and toolbar have their heights.
    private static func place(_ window: NSWindow) {
        guard let visible = (window.screen ?? NSScreen.main)?.visibleFrame else {
            window.center()
            return
        }
        let chrome = window.frame.height - window.contentLayoutRect.height
        let tallest = chrome + CheckSetupView.height
        let top = min(visible.maxY, visible.midY + tallest / 2)
        window.setFrameTopLeftPoint(NSPoint(x: visible.midX - window.frame.width / 2, y: top))
    }
}

/// Reports a chosen tab: `NSTabViewController` is its tab view's delegate.
private final class SettingsTabsController: NSTabViewController {
    var didSelect: (Int) -> Void = { _ in }

    override func tabView(_ tabView: NSTabView, didSelect tabViewItem: NSTabViewItem?) {
        super.tabView(tabView, didSelect: tabViewItem)
        guard let tabViewItem else { return }
        didSelect(tabView.indexOfTabViewItem(tabViewItem))
    }
}

/// Settings > General.
struct GeneralSettingsView: View {
    var body: some View {
        WindowPreferencesView()
            .padding(20)
            .frame(width: SettingsTab.width, alignment: .leading)
    }
}
