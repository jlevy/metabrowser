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
    /// Refresh: runtime discovery again.
    var refresh: () -> Void
    var choose: () -> Void
    var revealLogsFolder: () -> Void
}

/// Settings > Runtime.
struct RuntimeView: View {
    let model: RuntimeModel
    let actions: RuntimeActions

    /// The most Places looked takes before it scrolls: about nine lines. A search that
    /// finds no `metab` lists each directory of the login shell's `PATH`
    /// (`RuntimeDiscovery`), dozens on some Macs, under the setup guide's notices, and the
    /// pane outgrew the height the window is placed for (`CheckSetupView.height`), which put
    /// Reveal Logs Folder and the help link below a small screen's edge. Measured on
    /// 2026-11-24 with 40 places and three notices (`SettingsWindowTests`): the pane is
    /// 431 pt with this cap and 861 pt without it.
    static let placesLookedHeight: CGFloat = 130

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
                // Disabled while a search runs, which a press would only wait for.
                Button("Refresh", action: actions.refresh).disabled(model.isSearching)
                Button("Choose metab…", action: actions.choose)
            }
            // Shown rather than behind a disclosure, whose title takes no click on macOS,
            // only its chevron does; a long list scrolls in place.
            if !model.tried.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Places looked").foregroundStyle(.secondary)
                    ScrollView(.vertical) {
                        Text(model.tried.map { "\($0.path) — \(Self.describe($0.result))" }.joined(separator: "\n"))
                            .font(.system(size: 11, design: .monospaced))
                            .fixedSize(horizontal: false, vertical: true)
                            .textSelection(.enabled)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(maxHeight: Self.placesLookedHeight)
                    .accessibilityLabel("Places looked")
                }
            }
            Divider()
            HStack {
                Button("Reveal Logs Folder", action: actions.revealLogsFolder)
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
        case .idle: Text("No metab is selected. Refresh looks for one, and Choose metab… picks one.")
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
