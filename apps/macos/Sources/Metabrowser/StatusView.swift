import AppKit
import ShellCore
import SwiftUI

/// What a folder window shows in place of the page (`WindowPhase`).
@Observable final class WindowStatus {
    var phase: WindowPhase = .starting
    /// While starting: the start waits for another repository's, behind their launch gate.
    var waitsForAnotherStart = false
    /// While a repository starts: what its server says it is doing, such as how far its
    /// clone has got (`ServerSupervisor.startProgress`).
    var progress: StartProgress?
}

struct StatusView: View {
    let folderName: String
    let folderPath: String
    let status: WindowStatus
    let retry: () -> Void
    let revealLogs: () -> Void
    let showSettings: () -> Void

    var body: some View {
        ZStack {
            Color(nsColor: .windowBackgroundColor)
            switch status.phase {
            case .starting:
                StartingView(
                    folderName: folderName, folderPath: folderPath, waits: status.waitsForAnotherStart,
                    progress: status.progress)
            case .failed(let failure):
                FailureView(
                    folderName: folderName, folderPath: folderPath, failure: failure, retry: retry,
                    revealLogs: revealLogs, showSettings: showSettings)
            case .waitingForSelection:
                VStack(spacing: 12) {
                    Text("Metabrowser opens \(folderName) when you select it.").font(.headline)
                    Text("macOS can ask your permission before an app reads this location.")
                    Text(folderPath).font(.callout).foregroundStyle(.secondary).textSelection(.enabled)
                }
                .padding(32)
            case .waitingForRuntime:
                VStack(spacing: 12) {
                    Text("Metabrowser opens \(folderName) once it has a metab it can run.").font(.headline)
                    Button("Open Settings…", action: showSettings)
                    Link("Installation and troubleshooting on GitHub", destination: ProjectLinks.installationGuide)
                }
                .padding(32)
            case .reloading:
                DelayedSpinner()
            }
        }
    }
}

private struct StartingView: View {
    let folderName: String
    let folderPath: String
    let waits: Bool
    let progress: StartProgress?

    var body: some View {
        VStack(spacing: 12) {
            DelayedSpinner()
            Text("Starting Metabrowser for \(folderName)…").font(.headline)
            if waits {
                Text("It starts once another repository has finished starting, which a first clone can take minutes to do.")
                    .multilineTextAlignment(.center)
            }
            if let progress {
                Text(progress.text)
                    .monospacedDigit()
                    .multilineTextAlignment(.center)
                    .textSelection(.enabled)
            }
            Text(folderPath).font(.callout).foregroundStyle(.secondary).textSelection(.enabled)
        }
        .padding(32)
    }
}

/// A spinner that appears only after `delay`, so a quick start or reload never flashes one.
private struct DelayedSpinner: View {
    /// Below this, a delay reads as instant, and a spinner would only flash.
    static let delay = Duration.milliseconds(300)
    @State private var showsSpinner = false

    var body: some View {
        ProgressView().opacity(showsSpinner ? 1 : 0)
            .task {
                try? await Task.sleep(for: Self.delay)  // cancelled: the view went away
                showsSpinner = true
            }
    }
}

private struct FailureView: View {
    let folderName: String
    let folderPath: String
    let failure: ServerFailure
    let retry: () -> Void
    let revealLogs: () -> Void
    let showSettings: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            if let gitHub = failure.gitHub {
                Label("Metabrowser could not open \(folderPath)", systemImage: "exclamationmark.triangle.fill")
                    .font(.title3.weight(.semibold))
                    .symbolRenderingMode(.multicolor)
                GitHubFailureDetails(failure: gitHub)
                DisclosureGroup("Recent server output") {
                    RecentOutput(lines: failure.recentOutput)
                }
            } else {
                Label("Metabrowser could not serve \(folderName)", systemImage: "exclamationmark.triangle.fill")
                    .font(.title3.weight(.semibold))
                    .symbolRenderingMode(.multicolor)
                Text(failure.summary).textSelection(.enabled)
                Text("Recent server output").font(.caption).foregroundStyle(.secondary)
                RecentOutput(lines: failure.recentOutput)
            }
            HStack {
                Button("Retry", action: retry).keyboardShortcut(.defaultAction)
                if let gitHub = failure.gitHub {
                    Button("Copy Message") {
                        NSPasteboard.general.clearContents()
                        NSPasteboard.general.setString(gitHub.copiedText(location: folderPath), forType: .string)
                    }
                }
                Button("Reveal Logs", action: revealLogs)
                Spacer()
                Button("Runtime Settings…", action: showSettings)
            }
        }
        .padding(28)
        .frame(maxWidth: 760)
    }
}

/// A GitHub failure: what went wrong, `metab`'s message, and the commands that fix it,
/// each with Copy, and, for one
/// that a sign-in can fix, that switching back tries again.
private struct GitHubFailureDetails: View {
    let failure: GitHubFailure

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(failure.headline).font(.headline)
            Text(failure.explanation).fixedSize(horizontal: false, vertical: true)
            Text(failure.message)
                .foregroundStyle(.secondary)
                .textSelection(.enabled)
                .fixedSize(horizontal: false, vertical: true)
            ForEach(Array(failure.steps.enumerated()), id: \.offset) { _, step in
                VStack(alignment: .leading, spacing: 4) {
                    Text(step.purpose)
                    CopyableCommand(text: step.command)
                }
            }
            if failure.rechecksOnActivation {
                Text(GitHubFailure.recheckNote).foregroundStyle(.secondary)
            }
        }
    }
}

/// The server's newest lines, scrolled to the end; Reveal Logs shows the rest.
private struct RecentOutput: View {
    let lines: [String]

    /// The newest lines fit the view.
    private static let shownLines = 120

    private var text: String {
        lines.isEmpty ? "(no output)" : lines.suffix(Self.shownLines).joined(separator: "\n")
    }

    var body: some View {
        ScrollView {
            Text(text)
                .font(.system(size: 11, design: .monospaced))
                .frame(maxWidth: .infinity, alignment: .leading)
                .textSelection(.enabled)
                .padding(8)
        }
        .defaultScrollAnchor(.bottom)
        .frame(minHeight: 120, maxHeight: 320)
        .background(Color(nsColor: .textBackgroundColor))
        .clipShape(RoundedRectangle(cornerRadius: 6))
        .overlay(RoundedRectangle(cornerRadius: 6).stroke(Color(nsColor: .separatorColor)))
    }
}
