import AppKit
import ShellCore
import SwiftUI

/// The first-run screen without a usable metab.
struct SetupGuideView: View {
    let guide: SetupGuide

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Metabrowser needs metab \(MetabRequirement.minimum) or later").font(.headline)
            Text("Use Choose metab… to select a compatible runtime, or Refresh to look for one again.")
                .fixedSize(horizontal: false, vertical: true)
            ForEach(Array(guide.notices.enumerated()), id: \.offset) { _, notice in
                Text(notice).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
            }
            Text("Watching for metab in \(FolderIdentity.abbreviatingHome(guide.binDirectory, home: guide.home)).")
                .foregroundStyle(.secondary)
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
