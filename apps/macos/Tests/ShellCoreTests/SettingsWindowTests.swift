import AppKit
import Foundation
import Testing
@testable import Metabrowser
@testable import ShellCore

/// Metabrowser > Settings…: its tabs, the plugin list, and the setup report, in a real
/// window, clicked as a person clicks it.
///
/// The plugin list used to sit behind a disclosure under Information, and a click on its
/// title, Plugins, did nothing: on macOS only a disclosure's chevron toggles it. It is a
/// tab now, which a click on its title shows. The setup report drew each check's details
/// in a grid, where a value that wrapped drew taller than the space the grid gave it and
/// ran over the next check; the report is one block of text now.
@Suite(.serialized) struct SettingsWindowTests {
    /// What `metab --plugins --json` prints, cut to three plugins and the keys the app reads:
    /// an object whose braces stand on lines of their own (`JSONAnswer`), as
    /// `tests/golden/app-contract.txt` pins it.
    nonisolated static let inventory = [
        "{",
        #"  "plugins": ["#,
        #"    {"name": "agents", "display_name": "Agent Session Browser", "version": "0.0.1", "source": "builtin", "requires": ["structured"]},"#,
        #"    {"name": "binary", "display_name": "Binary", "version": "0.0.1", "source": "builtin", "requires": []},"#,
        #"    {"name": "sqlite", "display_name": "SQLite", "version": "0.0.1", "source": "builtin", "requires": ["table"]}"#,
        "  ],",
        #"  "errors": []"#,
        "}",
    ]

    nonisolated static let setup = RuntimeSetup(
        runtime: Runtime(executable: "/opt/metab/bin/metab", version: MetabRequirement.minimum, source: .chosen),
        tools: ToolPaths(git: "/opt/git/bin/git"))

    struct Fixture {
        let controller: SettingsWindowController
        let window: NSWindow
        let runtime: RuntimeModel
        let plugins: PluginListModel
        let checkSetup: CheckSetupModel
        let runs: Recorder<LaunchSpec>
        var shown: [SettingsTab] { shownRecorder.all }
        let shownRecorder: Recorder<SettingsTab>
    }

    private func fixture(setup: RuntimeSetup? = Self.setup) async -> Fixture {
        await runAppKitEventLoop()
        let runs = Recorder<LaunchSpec>()
        let runtime = RuntimeModel()
        runtime.setup = setup
        let plugins = PluginListModel(run: { spec, _ in
            runs.append(spec)
            return CommandResult(status: 0, output: Self.inventory)
        }, environment: { [:] })
        let checkSetup = CheckSetupModel()
        let controller = SettingsWindowController(
            runtime: runtime, runtimeActions: RuntimeActions(findAgain: {}, choose: {}, revealLogs: {}),
            plugins: plugins, checkSetup: checkSetup, checkSetupActions: CheckSetupActions(checkAgain: {}))
        let shown = Recorder<SettingsTab>()
        controller.onShow = { shown.append($0) }
        controller.window?.animationBehavior = .none
        return Fixture(
            controller: controller, window: controller.window!, runtime: runtime, plugins: plugins,
            checkSetup: checkSetup, runs: runs, shownRecorder: shown)
    }

    /// The toolbar's tab titled `label`, found as assistive apps find it.
    private func tab(_ label: String, in window: NSWindow) -> NSAccessibilityProtocol? {
        var found: NSAccessibilityProtocol?
        func visit(_ element: Any) {
            guard found == nil, let element = element as? NSAccessibilityProtocol else { return }
            if element.accessibilityTitle() == label || element.accessibilityLabel() == label,
                [.button, .radioButton].contains(element.accessibilityRole())
            {
                found = element
                return
            }
            for child in element.accessibilityChildren() ?? [] { visit(child) }
        }
        visit(window)
        return found
    }

    /// Presses `tab` as VoiceOver and Full Keyboard Access press it, which runs the click
    /// its button runs for a mouse (`NSButtonCell.performClick`), wherever the window is on
    /// screen and wherever the pointer is.
    private func click(_ tab: NSAccessibilityProtocol?) throws {
        // The toolbar's item viewer answers false but selects its tab; each test checks the
        // tab it expects.
        _ = try #require(tab, "no such tab").accessibilityPerformPress()
    }

    private func views<T: NSView>(_ type: T.Type, in view: NSView?) -> [T] {
        guard let view else { return [] }
        return (view as? T).map { [$0] } ?? [] + view.subviews.flatMap { views(type, in: $0) }
    }

    @Test func aClickOnThePluginsTabListsThePlugins() async throws {
        let fixture = await fixture()
        let window = fixture.window
        fixture.controller.show(.general)
        defer { window.orderOut(nil) }
        #expect(await eventually(within: .seconds(10)) { tab("Plugins", in: window) != nil })
        let general = window.frame
        #expect(fixture.runs.all.isEmpty, "the list is read only when its pane shows")

        try click(tab("Plugins", in: window))
        #expect(await eventually(within: .seconds(10)) { fixture.controller.selected == .plugins })
        #expect(fixture.shown.last == .plugins)
        #expect(await eventually(within: .seconds(10)) { fixture.plugins.answer != nil })
        guard case .inventory(let listed) = fixture.plugins.answer else {
            Issue.record("the pane did not list the plugins: \(String(describing: fixture.plugins.answer))")
            return
        }
        #expect(listed.plugins.map(\.name) == ["agents", "binary", "sqlite"])
        #expect(fixture.runs.all.map(\.arguments) == [PluginInventory.arguments])
        #expect(fixture.runs.all.first?.executable == Self.setup.runtime.executable)
        // The window grew to the list from its top edge and kept its width.
        #expect(await eventually(within: .seconds(10)) { window.frame.height > general.height })
        #expect(window.frame.maxY == general.maxY)
        #expect(window.frame.width == general.width)
        #expect(window.title == "Plugins")

        // Another pane and back: the list is kept, not discovered again; Refresh does.
        try click(tab("General", in: window))
        #expect(await eventually(within: .seconds(10)) { fixture.controller.selected == .general })
        try click(tab("Plugins", in: window))
        #expect(await eventually(within: .seconds(10)) { fixture.controller.selected == .plugins })
        #expect(fixture.runs.all.count == 1)
        fixture.plugins.refresh()
        #expect(await eventually(within: .seconds(10)) { fixture.runs.all.count == 2 && fixture.plugins.answer != nil })
    }

    @Test func everyTabIsTitledInTheToolbarAndKeepsTheWindowsWidthAndTop() async throws {
        let fixture = await fixture()
        let window = fixture.window
        fixture.controller.show(.general)
        defer { window.orderOut(nil) }
        #expect(await eventually(within: .seconds(10)) { tab("General", in: window) != nil })
        let first = window.frame
        for pane in SettingsTab.allCases {
            let button = tab(pane.label, in: window)
            try click(button)
            #expect(await eventually(within: .seconds(10)) { fixture.controller.selected == pane })
            #expect(window.title == pane.label)
            #expect(window.frame.width == first.width)
            #expect(window.frame.maxY == first.maxY)
        }
        // General came on screen with the window; each other pane once, as it was pressed.
        #expect(fixture.shown.first == .general)
        #expect(Array(fixture.shown.drop(while: { $0 == .general })) == [.runtime, .plugins, .checkSetup])
    }

    /// Help > Check Setup… and a click on its tab each bring the pane on screen, which runs
    /// the check; the menu's Settings… shows the pane it showed last.
    @Test func checkSetupRunsWhenItsPaneComesOnScreen() async throws {
        let fixture = await fixture()
        let window = fixture.window
        defer { window.orderOut(nil) }
        fixture.controller.show(.checkSetup)
        #expect(fixture.controller.selected == .checkSetup)
        #expect(fixture.shown == [.checkSetup])
        // Asked for again while it shows, as Help > Check Setup… is: it runs again.
        fixture.controller.show(.checkSetup)
        #expect(fixture.shown == [.checkSetup, .checkSetup])
        fixture.controller.show(.runtime)
        #expect(fixture.shown.last == .runtime)
        fixture.controller.show(nil)
        #expect(fixture.shown.last == .runtime)
        #expect(window.isVisible)
    }

    /// The report from the doctor's own transcript, as the pane shows it: one text view
    /// holding exactly what Copy Report copies, read-only, wrapping lines without drawing
    /// one over another, and any part of it selectable and copied as plain text.
    @Test func theReportIsOneBlockOfTextAnyPartOfWhichCopies() async throws {
        let fixture = await fixture()
        let window = fixture.window
        fixture.checkSetup.header = DoctorRun.header(
            app: AppIdentity(infoDictionary: ["CFBundleShortVersionString": "0.1.0", "CFBundleVersion": "1"]),
            setup: Self.setup)
        fixture.checkSetup.answer = DoctorRun.answer(CommandResult(status: 0, output: try doctorTranscript()))
        fixture.controller.show(.checkSetup)
        defer { window.orderOut(nil) }
        let text = try #require(fixture.checkSetup.text)

        #expect(await eventually(within: .seconds(10)) { views(NSTextView.self, in: window.contentView).count == 1 })
        let report = try #require(views(NSTextView.self, in: window.contentView).first)
        #expect(report.string == text)
        #expect(!report.isEditable)
        #expect(report.isSelectable)
        #expect(!report.isRichText)
        #expect(report.accessibilityLabel() == "Setup report")
        #expect(window.makeFirstResponder(report))

        // From the middle of the metab check into the Git check: two checks, partly.
        let whole = text as NSString
        let start = whole.range(of: "  executable:").location
        let end = NSMaxRange(whole.range(of: "  file ages: available"))
        try #require(start != NSNotFound && end > start)
        let part = NSRange(location: start, length: end - start)
        report.setSelectedRange(part)
        let pasteboard = NSPasteboard(name: NSPasteboard.Name("settings-window-tests-\(UUID().uuidString)"))
        defer { pasteboard.releaseGlobally() }
        pasteboard.clearContents()
        // What Edit > Copy writes: the text view's own types, which are plain text alone.
        #expect(report.writeSelection(to: pasteboard, types: report.writablePasteboardTypes))
        #expect(pasteboard.string(forType: .string) == whole.substring(with: part))
        #expect(pasteboard.types?.contains(.rtf) == false)

        // Each line of text, wrapped or not, is below the one before it.
        let layout = try #require(report.layoutManager)
        let container = try #require(report.textContainer)
        layout.ensureLayout(for: container)
        var fragments: [NSRect] = []
        layout.enumerateLineFragments(forGlyphRange: layout.glyphRange(for: container)) { rect, _, _, _, _ in
            fragments.append(rect)
        }
        #expect(fragments.count > whole.components(separatedBy: "\n").count, "a long detail wraps")
        #expect(zip(fragments, fragments.dropFirst()).allSatisfy { $0.maxY <= $1.minY })
        // The report scrolls within the pane rather than growing the window past its height.
        let scroll = try #require(report.enclosingScrollView)
        #expect(report.frame.height > scroll.contentView.bounds.height)
        #expect(window.contentLayoutRect.height == CheckSetupView.height)
    }

    @Test func withoutARuntimeThePanesSaySoAndRunNothing() async throws {
        let fixture = await fixture(setup: nil)
        let window = fixture.window
        fixture.checkSetup.hasRuntime = false
        fixture.controller.show(.plugins)
        defer { window.orderOut(nil) }
        try? await Task.sleep(for: .milliseconds(300))
        #expect(fixture.runs.all.isEmpty)
        #expect(fixture.plugins.answer == nil)
        fixture.runtime.setup = Self.setup
        #expect(await eventually(within: .seconds(10)) { fixture.plugins.answer != nil })
        #expect(fixture.runs.all.count == 1)
        fixture.controller.show(.checkSetup)
        #expect(views(NSTextView.self, in: window.contentView).isEmpty)
    }

    /// `tests/golden/cli-doctor.tryscript.md`'s `metab --doctor --json`, as `DoctorReportTests` reads it.
    private func doctorTranscript() throws -> [String] {
        let root = URL(filePath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let golden = try String(
            contentsOf: root.appending(path: "tests/golden/cli-doctor.tryscript.md"), encoding: .utf8)
        let all = golden.split(separator: "\n", omittingEmptySubsequences: false).map(String.init)
        let start = try #require(all.firstIndex(of: "$ metab --doctor --json")) + 1
        let end = try #require(all[start...].firstIndex { $0.hasPrefix("? ") })
        return Array(all[start..<end])
    }
}
