import AppKit
import ShellCore
import SwiftUI

/// What Settings > Check Setup shows, which Help > Check Setup… opens: the report of the
/// last `metab --doctor --json` run (`DoctorRun`), or why there is none.
@Observable final class CheckSetupModel {
    /// Which app and which `metab`, the first lines of the report's text.
    var header: [String] = []
    var isRunning = false
    var answer: DoctorAnswer?
    /// No `metab` is selected, so nothing ran.
    var hasRuntime = true
    /// The report as the pane shows it and Copy Report copies it.
    var text: String? {
        answer.map { DoctorRun.text(header: header, answer: $0) }
    }
}

struct CheckSetupActions {
    var checkAgain: () -> Void
}

/// Settings > Check Setup: a sentence that says whether `metab` can serve a folder, then
/// the whole report as plain text (`DoctorReport.text(after:)`), each check as
/// `metab --doctor` prints one: `id: state: summary`, then its details, indented. One
/// read-only text view holds it, so it wraps and scrolls as text does, and any part of it
/// can be selected and copied; Copy Report copies all of it.
struct CheckSetupView: View {
    let model: CheckSetupModel
    let actions: CheckSetupActions

    /// The pane's height, fixed: the report scrolls within it. The tallest pane, which
    /// the window is placed for (`SettingsWindowController`).
    static let height: CGFloat = 520

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            verdict
            if let text = model.text, model.hasRuntime {
                ReportTextView(text: text)
                    .clipShape(RoundedRectangle(cornerRadius: 6))
                    .overlay(RoundedRectangle(cornerRadius: 6).strokeBorder(Color(nsColor: .separatorColor)))
            } else {
                Spacer(minLength: 0)
            }
            HStack {
                // Enabled with no `metab` selected too: it rereads the selection, so one
                // chosen in Settings > Runtime meanwhile is checked.
                Button("Check Again", action: actions.checkAgain).disabled(model.isRunning)
                Button("Copy Report") {
                    guard let text = model.text else { return }
                    NSPasteboard.general.clearContents()
                    NSPasteboard.general.setString(text, forType: .string)
                }
                .disabled(model.text == nil || model.isRunning)
                if model.isRunning {
                    ProgressView().controlSize(.small)
                    Text("Running metab --doctor…").foregroundStyle(.secondary)
                }
                Spacer()
                Link("Setup Help", destination: ProjectLinks.installationGuide)
            }
        }
        .padding(20)
        .frame(width: SettingsTab.width, height: Self.height, alignment: .topLeading)
    }

    /// One sentence for the whole report, and the checks that need a look.
    @ViewBuilder private var verdict: some View {
        if !model.hasRuntime {
            Text(
                "No metab is selected, so there is nothing to check. Settings > Runtime finds or chooses one; "
                    + "then Check Again."
            )
            .fixedSize(horizontal: false, vertical: true)
        } else {
            switch model.answer {
            case .none:
                EmptyView()
            case .unreadable(let reason, _):
                Text("No report: metab --doctor --json \(reason).")
                    .font(.headline)
                    .fixedSize(horizontal: false, vertical: true)
            case .report(let report):
                VStack(alignment: .leading, spacing: 4) {
                    Label {
                        Text(
                            report.ok
                                ? "No problems: metab can serve a folder with this setup."
                                : "metab found problems that can stop it from serving a folder."
                        )
                    } icon: {
                        if report.ok {
                            Image(systemName: "checkmark.circle.fill").foregroundStyle(.green)
                        } else {
                            Image(systemName: "xmark.octagon.fill").foregroundStyle(.red)
                        }
                    }
                    .font(.headline)
                    if let attention = Self.attention(report) {
                        Text(attention).foregroundStyle(.secondary).fixedSize(horizontal: false, vertical: true)
                    }
                    if !report.hasChecks {
                        Text(DoctorRun.noChecks).foregroundStyle(.orange).fixedSize(horizontal: false, vertical: true)
                    }
                }
            }
        }
    }

    /// The checks whose state is not ok, by title and state, so a warning in a long report
    /// is not missed: "Needs a look: GitHub CLI (warning)."
    static func attention(_ report: DoctorReport) -> String? {
        let rows = report.rows.filter { $0.state != .ok }
        guard !rows.isEmpty else { return nil }
        return "Needs a look: " + rows.map { "\($0.title) (\($0.state.label))" }.joined(separator: ", ") + "."
    }
}

/// The report as one block of monospaced text in a read-only, selectable `NSTextView`: it
/// wraps at the pane's width and scrolls, a line that wraps continues under its own
/// indent, and a selection copies as plain text. An `https` address in it is a link.
struct ReportTextView: NSViewRepresentable {
    let text: String

    static let font = NSFont.monospacedSystemFont(ofSize: 11, weight: .regular)

    func makeNSView(context: Context) -> NSScrollView {
        let scroll = NSTextView.scrollableTextView()
        scroll.hasVerticalScroller = true
        scroll.autohidesScrollers = true
        scroll.borderType = .noBorder
        guard let view = scroll.documentView as? NSTextView else { return scroll }
        view.isEditable = false
        view.isSelectable = true
        // Plain text: a copy is the text alone, as a bug report wants it.
        view.isRichText = false
        view.textContainerInset = NSSize(width: 6, height: 8)
        view.backgroundColor = .textBackgroundColor
        view.setAccessibilityLabel("Setup report")
        view.textStorage?.setAttributedString(Self.styled(text))
        return scroll
    }

    func updateNSView(_ scroll: NSScrollView, context: Context) {
        guard let view = scroll.documentView as? NSTextView, view.string != text else { return }
        view.textStorage?.setAttributedString(Self.styled(text))
    }

    /// `text` in the report's font and the text color, each line indented under itself
    /// where it wraps, and each `https` address a link.
    static func styled(_ text: String) -> NSAttributedString {
        let styled = NSMutableAttributedString(
            string: text, attributes: [.font: font, .foregroundColor: NSColor.textColor])
        let space = (" " as NSString).size(withAttributes: [.font: font]).width
        let whole = text as NSString
        var start = 0
        while start < whole.length {
            let line = whole.lineRange(for: NSRange(location: start, length: 0))
            let leading = whole.substring(with: line).prefix(while: { $0 == " " }).count
            let paragraph = NSMutableParagraphStyle()
            paragraph.headIndent = CGFloat(leading + 4) * space
            paragraph.lineBreakMode = .byWordWrapping
            styled.addAttribute(.paragraphStyle, value: paragraph, range: line)
            start = NSMaxRange(line)
        }
        if let links = try? NSDataDetector(types: NSTextCheckingResult.CheckingType.link.rawValue) {
            for match in links.matches(in: text, range: NSRange(location: 0, length: whole.length)) {
                guard let url = match.url, url.scheme == "https" else { continue }
                styled.addAttribute(.link, value: url, range: match.range)
            }
        }
        return styled
    }
}
