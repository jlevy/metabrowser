import AppKit
import ShellCore
import SwiftUI

/// What Settings > Runtime shows: the `metab` in use, the tools handed to it, and what
/// discovery looked at. The Plugins pane reads `setup` too.
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
    var revealLogs: () -> Void
}

/// Settings > Runtime.
struct RuntimeView: View {
    let model: RuntimeModel
    let actions: RuntimeActions

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if let setup = model.setup {
                found(setup)
            } else if let guide = model.guide {
                SetupGuideView(guide: guide)
            } else {
                activity(RuntimeActivity(
                    isSearching: model.isSearching, isChoosing: model.isChoosing,
                    isPreparingGuide: model.isPreparingGuide))
            }
            if let notice = model.notice {
                Text(notice).foregroundStyle(.orange).textSelection(.enabled)
                    .fixedSize(horizontal: false, vertical: true)
            }
            HStack {
                Button("Find Again", action: actions.findAgain).disabled(model.isSearching)
                Button("Choose metab…", action: actions.choose)
            }
            // Shown as it is rather than behind a disclosure: the pane has the room, and a
            // disclosure's title takes no click on macOS, only its chevron does.
            if !model.tried.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Places looked").foregroundStyle(.secondary)
                    Text(model.tried.map { "\($0.path) — \(Self.describe($0.result))" }.joined(separator: "\n"))
                        .font(.system(size: 11, design: .monospaced))
                        .fixedSize(horizontal: false, vertical: true)
                        .textSelection(.enabled)
                }
            }
            Divider()
            HStack {
                Button("Reveal Logs", action: actions.revealLogs)
                Link("Installation and troubleshooting on GitHub", destination: ProjectLinks.installationGuide)
            }
        }
        .padding(20)
        .frame(width: SettingsTab.width, alignment: .leading)
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
