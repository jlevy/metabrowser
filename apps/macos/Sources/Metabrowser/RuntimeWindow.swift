import AppKit
import ShellCore
import SwiftUI

/// What the Settings window shows: the `metab` in use, the tools handed to it, and
/// what discovery looked at.
@Observable final class RuntimeModel {
    var setup: RuntimeSetup?
    var tried: [CandidateOutcome] = []
    var isSearching = false
    var isRunningDoctor = false
    var doctorOutput: String?
    var notice: String?
}

struct RuntimeActions {
    var findAgain: () -> Void
    var choose: () -> Void
    var runDoctor: () -> Void
    var revealLogs: () -> Void
}

struct RuntimeView: View {
    let model: RuntimeModel
    let actions: RuntimeActions

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if let setup = model.setup {
                found(setup)
            } else if model.isSearching {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text("Looking for the metab command-line tool…")
                }
            } else {
                missing
            }
            if let notice = model.notice {
                Text(notice).foregroundStyle(.orange).textSelection(.enabled)
            }
            Divider()
            HStack {
                Button("Find Again", action: actions.findAgain).disabled(model.isSearching)
                Button("Choose metab…", action: actions.choose)
                Button("Run Doctor", action: actions.runDoctor)
                    .disabled(model.setup == nil || model.isRunningDoctor)
                Spacer()
                Button("Reveal Logs", action: actions.revealLogs)
            }
            if model.isRunningDoctor {
                ProgressView().controlSize(.small)
            }
            if let output = model.doctorOutput {
                ScrollView {
                    Text(output)
                        .font(.system(size: 11, design: .monospaced))
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .textSelection(.enabled)
                        .padding(8)
                }
                .frame(minHeight: 80, maxHeight: 220)
                .background(Color(nsColor: .textBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 6))
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

    private var missing: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Metabrowser needs the metab command-line tool").font(.headline)
            Text("This app runs your own installation of Metabrowser and did not find one. Install it with uv, then click Find Again:")
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Text(RuntimeDiscovery.installCommand)
                    .font(.system(.body, design: .monospaced))
                    .textSelection(.enabled)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(Color(nsColor: .textBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius: 4))
                Button("Copy") {
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(RuntimeDiscovery.installCommand, forType: .string)
                }
            }
            Link(
                "Installation guide",
                destination: URL(string: "https://github.com/jlevy/metabrowser/blob/main/docs/installation.md")!)
        }
    }

    static func describe(_ result: CandidateResult) -> String {
        switch result {
        case .valid(let version): "metab \(version)"
        case .missing: "not found"
        case .rejected(let reason): reason
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
