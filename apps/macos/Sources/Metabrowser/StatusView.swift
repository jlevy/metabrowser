import ShellCore
import SwiftUI

/// What a folder window shows in place of the page: the server is starting, or it
/// failed and here is why.
@Observable final class WindowStatus {
    enum Phase: Equatable {
        case starting
        case failed(ServerFailure)
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
            }
        }
    }
}

private struct StartingView: View {
    let folderName: String
    let folderPath: String
    /// A start that finishes quickly never flashes a spinner.
    @State private var showsSpinner = false
    /// Below this, a delay reads as instant, and a spinner would only flash.
    private static let spinnerDelay: Duration = .milliseconds(300)

    var body: some View {
        VStack(spacing: 12) {
            ProgressView().opacity(showsSpinner ? 1 : 0)
            Text("Starting Metabrowser for \(folderName)…").font(.headline)
            Text(folderPath).font(.callout).foregroundStyle(.secondary).textSelection(.enabled)
        }
        .padding(32)
        .task {
            try? await Task.sleep(for: Self.spinnerDelay)  // cancelled: the view went away
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
