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
    /// A search found nothing, and the first-run steps are being worked out.
    var isPreparingGuide = false
    var isRunningDoctor = false
    var doctorOutput: String?
    var notice: String?
    /// The first-run steps, once a search found no usable `metab`.
    var guide: SetupGuide?
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
            } else if let guide = model.guide {
                missing(guide)
            } else {
                activity(RuntimeActivity(
                    isSearching: model.isSearching, isChoosing: model.isChoosing,
                    isPreparingSteps: model.isPreparingGuide))
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
            Divider()
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

    /// What is running while there is neither a runtime nor steps to show.
    @ViewBuilder private func activity(_ activity: RuntimeActivity) -> some View {
        switch activity {
        case .searching: working("Looking for the metab command-line tool…")
        case .checkingChoice: working("Checking the chosen metab…")
        case .preparingSteps: working("Working out the steps to install metab…")
        case .idle: Text("No metab is selected. Find Again looks for one, and Choose metab… picks one.")
        }
    }

    private func working(_ text: String) -> some View {
        HStack(spacing: 8) {
            ProgressView().controlSize(.small)
            Text(text)
        }
    }

    private func missing(_ guide: SetupGuide) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            SetupGuideView(guide: guide)
            Link(
                "Installation guide",
                destination: URL(string: "https://github.com/jlevy/metabrowser/blob/main/docs/installation.md")!)
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
