import AppKit
import ShellCore
import SwiftUI

/// The plugins Settings > Plugins lists: `metab --plugins --json` from the selected
/// runtime, in a new server's environment (`PluginInventory`). It is read when the pane
/// first shows a runtime, and again on Refresh or when the runtime changes, and kept
/// while other panes show, so going back to the tab does not discover them again.
@Observable final class PluginListModel {
    /// The runtime the answer is for, or is being discovered for.
    private(set) var setup: RuntimeSetup?
    /// Nil while discovery runs, and while there is no runtime.
    private(set) var answer: PluginInventory.Answer?
    private(set) var isDiscovering = false
    @ObservationIgnored private var discovery: Task<Void, Never>?
    @ObservationIgnored private let run: CommandRunner.Run
    @ObservationIgnored private let environment: () -> [String: String]

    init(
        run: @escaping CommandRunner.Run = CommandRunner.live,
        environment: @escaping () -> [String: String] = { ProcessInfo.processInfo.environment }
    ) {
        self.run = run
        self.environment = environment
    }

    /// The pane shows `setup`: discovers its plugins unless they are listed or being
    /// discovered already.
    func show(_ setup: RuntimeSetup?) {
        guard setup != self.setup || (answer == nil && !isDiscovering) else { return }
        discover(setup)
    }

    /// Refresh: discovers the plugins again, as a new server would now.
    func refresh() {
        discover(setup)
    }

    private func discover(_ setup: RuntimeSetup?) {
        discovery?.cancel()
        self.setup = setup
        answer = nil
        guard let setup else {
            isDiscovering = false
            discovery = nil
            return
        }
        isDiscovering = true
        let command = PluginInventory.spec(setup: setup, inherited: environment())
        let run = self.run
        discovery = Task { [weak self] in
            let result = await run(command, PluginInventory.timeout)
            guard !Task.isCancelled, let self else { return }
            answer = PluginInventory.answer(result)
            isDiscovering = false
            discovery = nil
        }
    }
}

/// Settings > Plugins.
struct PluginsView: View {
    let runtime: RuntimeModel
    let model: PluginListModel

    /// The list's height: about ten plugins, and the rest scroll.
    static let listHeight: CGFloat = 340

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let setup = runtime.setup {
                Text("The plugins a new server discovers with metab \(setup.runtime.version).")
                    .foregroundStyle(.secondary)
                list
                    .frame(maxWidth: .infinity, minHeight: Self.listHeight, maxHeight: Self.listHeight, alignment: .topLeading)
                    .background(Color(nsColor: .textBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                    .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(Color(nsColor: .separatorColor)))
                HStack {
                    Button("Refresh") { model.refresh() }.disabled(model.isDiscovering)
                    if case .inventory(let inventory) = model.answer {
                        Text(Self.count(inventory)).foregroundStyle(.secondary)
                    }
                }
            } else {
                Text("No metab is selected, so no plugins are listed. Settings > Runtime finds or chooses one.")
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(20)
        .frame(width: SettingsTab.width, alignment: .topLeading)
        .onAppear { model.show(runtime.setup) }
        .onChange(of: runtime.setup) { _, setup in model.show(setup) }
    }

    @ViewBuilder private var list: some View {
        switch model.answer {
        case nil:
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text("Discovering plugins…")
            }
            .padding(12)
        case .unavailable(let message):
            Text(message).foregroundStyle(.secondary).textSelection(.enabled).padding(12)
        case .inventory(let inventory):
            if inventory.plugins.isEmpty && inventory.errors.isEmpty {
                Text("No plugins were discovered.").foregroundStyle(.secondary).padding(12)
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        ForEach(inventory.plugins) { plugin in
                            PluginRow(plugin: plugin)
                            Divider()
                        }
                        if !inventory.errors.isEmpty {
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Discovery problems").bold()
                                ForEach(Array(inventory.errors.enumerated()), id: \.offset) { _, error in
                                    Text(error).foregroundStyle(.orange)
                                        .fixedSize(horizontal: false, vertical: true)
                                        .textSelection(.enabled)
                                }
                            }
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
    }

    static func count(_ inventory: PluginInventory) -> String {
        let plugins = inventory.plugins.count == 1 ? "1 plugin" : "\(inventory.plugins.count) plugins"
        switch inventory.errors.count {
        case 0: return plugins
        case 1: return "\(plugins), 1 discovery problem"
        default: return "\(plugins), \(inventory.errors.count) discovery problems"
        }
    }
}

/// One plugin: its name, then its ID, version, and source, then what it requires.
private struct PluginRow: View {
    let plugin: PluginInventory.Plugin

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(plugin.displayName).bold()
            Text("\(plugin.name) · \(plugin.version) · \(plugin.source)").foregroundStyle(.secondary)
            if let requires = plugin.requires, !requires.isEmpty {
                Text("Requires \(requires.joined(separator: ", "))").foregroundStyle(.secondary)
            }
        }
        .textSelection(.enabled)
        .padding(.horizontal, 12)
        .padding(.vertical, 8)
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}
