import AppKit
import ShellCore
import SwiftUI

/// The first-run screen without a usable `metab`: only the missing steps, each a
/// command to copy, and a note that the app continues by itself.
struct SetupGuideView: View {
    let guide: SetupGuide

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(guide.heading).font(.headline)
            Text("Metabrowser runs your own installation of metab. Run these in Terminal; Metabrowser continues by itself once metab is ready.")
                .fixedSize(horizontal: false, vertical: true)
            ForEach(Array(guide.steps.enumerated()), id: \.offset) { index, step in
                VStack(alignment: .leading, spacing: 4) {
                    Text("\(index + 1). \(step.title(home: guide.home))")
                        .fixedSize(horizontal: false, vertical: true)
                    if let note = step.note {
                        Text(note).foregroundStyle(.secondary)
                    }
                    CopyableCommand(text: step.command)
                    if let alternative = step.alternative {
                        Text("Or, with Homebrew:").foregroundStyle(.secondary)
                        CopyableCommand(text: alternative)
                    }
                }
            }
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text("Waiting for metab in \(FolderIdentity.abbreviatingHome(guide.binDirectory, home: guide.home))…")
                    .foregroundStyle(.secondary)
            }
            if guide.suggestsUpdateShell {
                VStack(alignment: .leading, spacing: 4) {
                    Text("To run metab in Terminal as well, run this and open a new Terminal window. Metabrowser does not need it.")
                        .foregroundStyle(.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                    CopyableCommand(text: SetupGuide.updateShellCommand)
                }
            }
        }
    }
}

/// A command shown in a monospaced box, with a button that copies it.
struct CopyableCommand: View {
    let text: String

    var body: some View {
        HStack {
            Text(text)
                .font(.system(.body, design: .monospaced))
                .textSelection(.enabled)
                .padding(.horizontal, 8)
                .padding(.vertical, 4)
                .background(Color(nsColor: .textBackgroundColor))
                .clipShape(RoundedRectangle(cornerRadius: 4))
            Button("Copy") {
                NSPasteboard.general.clearContents()
                NSPasteboard.general.setString(text, forType: .string)
            }
        }
    }
}
