import AppKit
import ShellCore
import SwiftUI

/// What the Settings window shows: the `metab` in use, the tools handed to it, and
/// what discovery looked at.
@Observable final class RuntimeModel {
    var setup: RuntimeSetup?
    var tried: [CandidateOutcome] = []
    var isSearching = false
    /// A file chosen with Choose metab… is being checked.
    var isChoosing = false
    /// A search found nothing, and the app is locating the directory to watch.
    var isPreparingGuide = false
    var notice: String?
    /// Discovery status, once a search found no usable metab.
    var guide: SetupGuide?
}

struct RuntimeActions {
    var findAgain: () -> Void
    var choose: () -> Void
    var checkSetup: () -> Void
    var revealLogs: () -> Void
}

struct RuntimeView: View {
    let model: RuntimeModel
    let actions: RuntimeActions

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Text("Information").font(.headline)
            if let setup = model.setup {
                found(setup)
                PluginInventoryView(setup: setup)
            } else if let guide = model.guide {
                SetupGuideView(guide: guide)
            } else {
                activity(RuntimeActivity(
                    isSearching: model.isSearching, isChoosing: model.isChoosing,
                    isPreparingGuide: model.isPreparingGuide))
            }
            if let notice = model.notice {
                Text(notice).foregroundStyle(.orange).textSelection(.enabled)
            }
            if !model.tried.isEmpty {
                DisclosureGroup("Places looked") {
                    VStack(alignment: .leading, spacing: 4) {
                        ForEach(Array(model.tried.enumerated()), id: \.offset) { _, outcome in
                            Text("\(outcome.path) — \(Self.describe(outcome.result))")
                                .font(.system(size: 11, design: .monospaced))
                                .textSelection(.enabled)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
            HStack {
                Button("Check Setup…", action: actions.checkSetup)
                Button("Reveal Logs", action: actions.revealLogs)
                Link("Installation and troubleshooting on GitHub", destination: ProjectLinks.installationGuide)
            }
            Divider()
            Text("Preferences").font(.headline)
            HStack {
                Button("Find Again", action: actions.findAgain).disabled(model.isSearching)
                Button("Choose metab…", action: actions.choose)
            }
            WindowPreferencesView()
        }
        .padding(20)
        .frame(width: 620, alignment: .leading)
    }

    private func found(_ setup: RuntimeSetup) -> some View {
        Grid(alignment: .leadingFirstTextBaseline, horizontalSpacing: 12, verticalSpacing: 6) {
            GridRow {
                Text("Runtime").foregroundStyle(.secondary)
                Text("metab \(setup.runtime.version)").bold()
            }
            GridRow {
                Text("Path").foregroundStyle(.secondary)
                Text(setup.runtime.executable).textSelection(.enabled)
            }
            GridRow {
                Text("Found").foregroundStyle(.secondary)
                Text(setup.runtime.source.label)
            }
            GridRow {
                Text("git").foregroundStyle(.secondary)
                Text(setup.tools.git ?? "not found").textSelection(.enabled)
            }
            GridRow {
                Text("gh").foregroundStyle(.secondary)
                Text(setup.tools.gh ?? "not found (GitHub pull request views need it)").textSelection(.enabled)
            }
        }
    }

    /// What is running before runtime discovery has produced a result.
    @ViewBuilder private func activity(_ activity: RuntimeActivity) -> some View {
        switch activity {
        case .searching: working("Looking for the metab command-line tool…")
        case .checkingChoice: working("Checking the chosen metab…")
        case .preparingGuide: working("Checking where metab is installed…")
        case .idle: Text("No metab is selected. Find Again looks for one, and Choose metab… picks one.")
        }
    }

    private func working(_ text: String) -> some View {
        HStack(spacing: 8) {
            ProgressView().controlSize(.small)
            Text(text)
        }
    }

    static func describe(_ result: CandidateResult) -> String {
        switch result {
        case .valid(let version): "metab \(version)"
        case .missing: "not found"
        case .tooOld(let version):
            "metab \(version), \(MetabRequirement.flagShortfall(version) ?? "older than \(MetabRequirement.minimum)")"
        case .rejected(let reason): reason
        case .untrusted(let reason): "not run: \(reason)"
        }
    }
}

/// Reads plugin discovery only while the section is open, then rereads it if the
/// selected runtime changes or the user refreshes the list.
private struct PluginInventoryView: View {
    let setup: RuntimeSetup
    @State private var expanded = false
    @State private var response: PluginInventory.Answer?
    @State private var refresh = 0

    private struct Request: Equatable {
        var setup: RuntimeSetup
        var refresh: Int
    }

    var body: some View {
        DisclosureGroup("Plugins", isExpanded: $expanded) {
            if expanded {
                VStack(alignment: .leading, spacing: 8) {
                    Text("Discovery for new servers using the selected runtime.")
                        .foregroundStyle(.secondary)
                    inventory
                    Button("Refresh Plugin List") { refresh += 1 }
                        .disabled(response == nil)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .task(id: Request(setup: setup, refresh: refresh)) {
                    response = nil
                    let command = PluginInventory.spec(setup: setup, inherited: ProcessInfo.processInfo.environment)
                    let result = await CommandRunner.run(command, timeout: PluginInventory.timeout)
                    guard !Task.isCancelled else { return }
                    response = PluginInventory.answer(result)
                }
            }
        }
    }

    @ViewBuilder private var inventory: some View {
        switch response {
        case nil:
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text("Discovering plugins…")
            }
        case .unavailable(let message):
            Text(message).foregroundStyle(.secondary).textSelection(.enabled)
        case .inventory(let result):
            if result.plugins.isEmpty && result.errors.isEmpty {
                Text("No plugins were discovered.").foregroundStyle(.secondary)
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(result.plugins) { plugin in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(plugin.displayName).bold()
                                Text("\(plugin.name) · \(plugin.version) · \(plugin.source)")
                                    .foregroundStyle(.secondary)
                                if let requires = plugin.requires, !requires.isEmpty {
                                    Text("Requires \(requires.joined(separator: ", "))")
                                        .foregroundStyle(.secondary)
                                }
                            }
                            .textSelection(.enabled)
                        }
                        if !result.errors.isEmpty {
                            Text("Discovery problems").bold()
                            ForEach(Array(result.errors.enumerated()), id: \.offset) { _, error in
                                Text(error).foregroundStyle(.orange).textSelection(.enabled)
                            }
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                .frame(height: 180)
            }
        }
    }
}

final class RuntimeWindowController: NSWindowController {
    init(model: RuntimeModel, actions: RuntimeActions) {
        let hosting = NSHostingController(rootView: RuntimeView(model: model, actions: actions))
        hosting.sizingOptions = .preferredContentSize
        let window = NSWindow(contentViewController: hosting)
        window.title = "Metabrowser Settings"
        window.styleMask = [.titled, .closable, .miniaturizable]
        window.isReleasedWhenClosed = false
        window.center()
        super.init(window: window)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }
}
