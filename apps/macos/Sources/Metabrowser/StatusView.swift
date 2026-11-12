import ShellCore
import SwiftUI

/// What a folder window shows in place of the page: the server is starting, it failed
/// and here is why, it waits for its tab to be selected or for a `metab` the app can run,
/// or a discarded tab reloads.
@Observable final class WindowStatus {
    enum Phase: Equatable {
        case starting
        case failed(ServerFailure)
        /// A restored folder in a protected location, whose server starts only once its tab
        /// is selected, so that a launch raises no privacy prompt for it.
        case waitingForSelection
        /// A start waiting for a `metab` the app accepts.
        case waitingForRuntime
        /// A tab that gave up its page loads it again from the running server.
        case reloading
    }

    var phase: Phase = .starting
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
                StartingView(folderName: folderName, folderPath: folderPath)
            case .failed(let failure):
                FailureView(
                    folderName: folderName, failure: failure, retry: retry, revealLogs: revealLogs,
                    showSettings: showSettings)
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
                    Text("Settings says what it found and what to install.")
                    Button("Open Settings…", action: showSettings)
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

    var body: some View {
        VStack(spacing: 12) {
            DelayedSpinner()
            Text("Starting Metabrowser for \(folderName)…").font(.headline)
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
    let failure: ServerFailure
    let retry: () -> Void
    let revealLogs: () -> Void
    let showSettings: () -> Void

    /// The newest lines fit the view; Reveal Logs shows the rest.
    private static let shownLines = 120

    private var output: String {
        failure.recentOutput.isEmpty ? "(no output)" : failure.recentOutput.suffix(Self.shownLines).joined(separator: "\n")
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Label("Metabrowser could not serve \(folderName)", systemImage: "exclamationmark.triangle.fill")
                .font(.title3.weight(.semibold))
                .symbolRenderingMode(.multicolor)
            Text(failure.summary).textSelection(.enabled)
            Text("Recent server output").font(.caption).foregroundStyle(.secondary)
            ScrollView {
                Text(output)
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
            HStack {
                Button("Retry", action: retry).keyboardShortcut(.defaultAction)
                Button("Reveal Logs", action: revealLogs)
                Spacer()
                Button("Runtime Settings…", action: showSettings)
            }
        }
        .padding(28)
        .frame(maxWidth: 760)
    }
}
