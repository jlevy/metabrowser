import AppKit
import ShellCore
import SwiftUI

/// What Help > Check Setup… shows: the report of the last `metab --doctor --json` run
/// (`DoctorRun`), or why there is none.
@Observable final class CheckSetupModel {
    /// Which app and which `metab`, the first lines of a copied report.
    var header: [String] = []
    var isRunning = false
    var answer: DoctorAnswer?
    /// No `metab` is selected, so nothing ran.
    var hasRuntime = true
    /// The step that upgrades the selected `metab` by the tool that installed it, for a
    /// report without setup checks.
    var upgrade: (command: String, note: String?)?

    var copyText: String? {
        answer.map { DoctorRun.text(header: header, answer: $0) }
    }
}

struct CheckSetupActions {
    var checkAgain: () -> Void
    var openSettings: () -> Void
}

struct CheckSetupView: View {
    let model: CheckSetupModel
    let actions: CheckSetupActions

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ForEach(model.header, id: \.self) { line in
                Text(line).foregroundStyle(.secondary).textSelection(.enabled)
            }
            Divider()
            ScrollView {
                content
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.trailing, 8)
            }
            Divider()
            HStack {
                Button("Check Again", action: actions.checkAgain).disabled(model.isRunning || !model.hasRuntime)
                Button("Copy Report") {
                    guard let text = model.copyText else { return }
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(text, forType: .string)
                }
                .disabled(model.copyText == nil || model.isRunning)
                if model.isRunning {
                    ProgressView().controlSize(.small)
                    Text("Running metab --doctor…").foregroundStyle(.secondary)
                }
                Spacer()
                Button("Settings…", action: actions.openSettings)
            }
        }
        .padding(20)
        .frame(minWidth: 640, idealWidth: 700, minHeight: 420, idealHeight: 560, alignment: .topLeading)
    }

    @ViewBuilder private var content: some View {
        if !model.hasRuntime {
            Text("No metab is selected, so there is nothing to check. Settings finds or chooses one.")
                .fixedSize(horizontal: false, vertical: true)
        } else {
            switch model.answer {
            case .none:
                EmptyView()
            case .unreadable(let reason, let output):
                unreadable(reason: reason, output: output)
            case .report(let report):
                reportView(report)
            }
        }
    }

    private func reportView(_ report: DoctorReport) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            Text(
                report.ok
                    ? "No problems: metab can serve a folder with this setup."
                    : "metab found problems that can stop it from serving a folder."
            )
            .font(.headline)
            if !report.hasChecks {
                VStack(alignment: .leading, spacing: 4) {
                    Text(DoctorRun.noChecks).foregroundStyle(.orange).fixedSize(horizontal: false, vertical: true)
                    if let upgrade = model.upgrade {
                        if let note = upgrade.note { Text(note).foregroundStyle(.secondary) }
                        CopyableCommand(text: upgrade.command)
                    }
                }
            }
            ForEach(Array(report.rows.enumerated()), id: \.offset) { _, row in
                CheckRowView(row: row)
            }
        }
    }

    private func unreadable(reason: String, output: [String]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("No report: metab --doctor --json \(reason).")
                .font(.headline)
                .fixedSize(horizontal: false, vertical: true)
            Text(output.isEmpty ? "It printed nothing." : "It printed:").foregroundStyle(.secondary)
            if !output.isEmpty {
                Text(output.joined(separator: "\n"))
                    .font(.system(size: 11, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
                    .padding(8)
                    .background(Color(nsColor: .textBackgroundColor))
                    .clipShape(RoundedRectangle(cornerRadius: 6))
            }
        }
    }
}

/// One check: its state, what it found, and the step that fixes it.
private struct CheckRowView: View {
    let row: DoctorReport.Row

    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            mark
            VStack(alignment: .leading, spacing: 4) {
                HStack(alignment: .firstTextBaseline) {
                    Text(row.title).bold()
                    Text(row.state.label).foregroundStyle(.secondary)
                }
                Text(row.summary).fixedSize(horizontal: false, vertical: true).textSelection(.enabled)
                if !row.details.isEmpty {
                    Grid(alignment: .leadingFirstTextBaseline, horizontalSpacing: 10, verticalSpacing: 2) {
                        ForEach(Array(row.details.enumerated()), id: \.offset) { _, detail in
                            GridRow {
                                Text(detail.name).foregroundStyle(.secondary)
                                Text(detail.value)
                                    .font(.system(size: 11, design: .monospaced))
                                    .fixedSize(horizontal: false, vertical: true)
                                    .textSelection(.enabled)
                            }
                        }
                    }
                    .font(.system(size: 11))
                }
                if let remedy = row.remedy {
                    Text(remedy.text).fixedSize(horizontal: false, vertical: true)
                    if let command = remedy.command { CopyableCommand(text: command) }
                    if let url = remedy.url { Link(url.absoluteString, destination: url) }
                }
            }
        }
    }

    @ViewBuilder private var mark: some View {
        switch row.state {
        case .ok: Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
        case .warning: Image(systemName: "exclamationmark.triangle.fill").foregroundStyle(.orange)
        case .problem: Image(systemName: "xmark.octagon.fill").foregroundStyle(.red)
        case .other: Image(systemName: "questionmark.circle").foregroundStyle(.secondary)
        }
    }
}

final class CheckSetupWindowController: NSWindowController {
    init(model: CheckSetupModel, actions: CheckSetupActions) {
        let hosting = NSHostingController(rootView: CheckSetupView(model: model, actions: actions))
        let window = NSWindow(contentViewController: hosting)
        window.title = "Check Setup"
        window.styleMask = [.titled, .closable, .miniaturizable, .resizable]
        window.isReleasedWhenClosed = false
        window.setContentSize(NSSize(width: 700, height: 560))
        window.center()
        super.init(window: window)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("unused") }
}
