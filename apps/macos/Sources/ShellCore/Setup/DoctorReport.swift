import Foundation

/// What `metab --doctor --json` reports, as Help > Check Setup… shows it: one row for the
/// plugins and settings, one for where `--present` opens a target, one for GitHub CLI, and
/// one per setup check, each with its state, a sentence, details, and the step that fixes
/// it.
///
/// The shape is `metab`'s, documented in `src/metabrowser/cli/doctor.py` and pinned by
/// `tests/golden/cli-doctor.tryscript.md`: `ok`, `problems`, `plugin_count`, `open_in`,
/// the `github` object of the GitHub status check, and `checks`. A key the app does not
/// read is ignored, and an object left out has no row, so a report from a `metab` whose
/// doctor predates `checks` still shows the rest and says the checks are missing
/// (`hasChecks`). The app reads `gh` and `git` only from here and never runs either.
public nonisolated struct DoctorReport: Equatable, Sendable {
    public enum State: Equatable, Sendable {
        case ok, warning, problem
        /// A state this app does not know, shown as `metab` named it.
        case other(String)

        init(_ named: String) {
            switch named {
            case "ok": self = .ok
            case "warning": self = .warning
            case "problem": self = .problem
            default: self = .other(named)
            }
        }

        public var label: String {
            switch self {
            case .ok: "ok"
            case .warning: "warning"
            case .problem: "problem"
            case .other(let named): named
            }
        }
    }

    /// What fixes a row: a sentence, and a command to copy or a page to open.
    public struct Remedy: Equatable, Sendable {
        public var text: String
        public var command: String?
        /// Only an `https` page: a report is `metab`'s output, and the app opens nothing else.
        public var url: URL?

        public init(text: String, command: String? = nil, url: URL? = nil) {
            self.text = text
            self.command = command
            self.url = url
        }
    }

    public struct Detail: Equatable, Sendable {
        public var name: String
        public var value: String

        public init(name: String, value: String) {
            self.name = name
            self.value = value
        }
    }

    public struct Row: Equatable, Sendable {
        /// The check's `id`, or `plugins`, `open_in`, or `github`.
        public var id: String
        public var title: String
        public var state: State
        public var summary: String
        public var details: [Detail]
        public var remedy: Remedy?

        public init(
            id: String, title: String, state: State, summary: String, details: [Detail] = [], remedy: Remedy? = nil
        ) {
            self.id = id
            self.title = title
            self.state = state
            self.summary = summary
            self.details = details
            self.remedy = remedy
        }
    }

    /// No problem: `metab` serves a folder with this setup. Warnings may remain.
    public var ok: Bool
    public var rows: [Row]
    /// False for a `metab` whose doctor reports no setup checks: one built before them.
    public var hasChecks: Bool

    public init(ok: Bool, rows: [Row], hasChecks: Bool) {
        self.ok = ok
        self.rows = rows
        self.hasChecks = hasChecks
    }

    /// The report as text, for Copy Report: `lines` first, such as which app and which
    /// `metab` ran it, then one block per row, as `metab --doctor` prints its checks.
    public func text(after lines: [String]) -> String {
        var text = lines
        text.append(ok ? "No problems." : "Problems found.")
        for row in rows {
            text.append("\(row.id): \(row.state.label): \(row.summary)")
            text += row.details.map { "  \($0.name): \($0.value)" }
            if let remedy = row.remedy {
                let step = remedy.command ?? remedy.url?.absoluteString
                text.append("  fix: \(remedy.text)" + (step.map { " \($0)" } ?? ""))
            }
        }
        if !hasChecks { text.append(DoctorRun.noChecks) }
        return text.joined(separator: "\n") + "\n"
    }
}

/// How a run of `metab --doctor --json` ended: a report, or why there is none.
public nonisolated enum DoctorAnswer: Equatable, Sendable {
    case report(DoctorReport)
    case unreadable(reason: String, output: [String])
}

/// Runs `metab --doctor --json` for Help > Check Setup… and reads its report.
///
/// It runs in a server's environment, with the tool directories the app found first on
/// `PATH` (`ChildEnvironment`), so the `gh` and `git` it reports are the ones the app's
/// servers run. A report exits 1 when it holds a problem; that is still a report.
public nonisolated enum DoctorRun {
    public static let arguments = ["--doctor", "--json"]
    public static let timeout = RuntimeDiscovery.doctorTimeout
    /// What the window says of a report without `checks`.
    public static let noChecks =
        "This metab reports no setup checks: it was built before metab --doctor checked Git and the "
        + "configuration and cache directories. Upgrade it to see them."

    public static func spec(setup: RuntimeSetup, inherited: [String: String]) -> LaunchSpec {
        LaunchSpec(
            executable: setup.runtime.executable, arguments: arguments,
            environment: ChildEnvironment.build(inherited: inherited, toolDirectories: setup.tools.directories))
    }

    /// What a copied report starts with: this app, the oldest `metab` it runs, and the
    /// `metab` that ran the check, which the report itself describes only from inside.
    public static func header(app: AppIdentity, setup: RuntimeSetup?) -> [String] {
        let metab = setup.map { setup in
            "metab: \(setup.runtime.version) at \(setup.runtime.executable) (found: \(setup.runtime.source.label))"
        }
        return [
            "\(app.name): \(app.buildLine); runs metab \(MetabRequirement.minimum) or later",
            metab ?? "metab: none selected",
        ]
    }

    /// Copy Report's text: `header`, then the report, or why there is none and all that
    /// `metab` printed.
    public static func text(header: [String], answer: DoctorAnswer) -> String {
        switch answer {
        case .report(let report):
            return report.text(after: header)
        case .unreadable(let reason, let output):
            let printed = output.isEmpty ? ["  (nothing)"] : output.map { "  \($0)" }
            return (header + ["metab --doctor --json \(reason).", "It printed:"] + printed).joined(separator: "\n")
                + "\n"
        }
    }

    public static func answer(_ result: CommandResult) -> DoctorAnswer {
        let output = result.output
        if let launchError = result.launchError {
            return .unreadable(reason: "could not run: \(launchError)", output: [])
        }
        if result.timedOut {
            return .unreadable(reason: "did not finish within \(timeout.components.seconds) seconds", output: output)
        }
        let status = result.status.map { "\(ExitStatus(waitStatus: $0))" } ?? "no exit status"
        let data: Data
        switch JSONAnswer.object(in: output) {
        case .success(let found): data = found
        case .failure(let problem): return .unreadable(reason: "\(problem.description) (\(status))", output: output)
        }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        guard let wire = try? decoder.decode(Wire.self, from: data) else {
            return .unreadable(reason: "printed a report this app cannot read (\(status))", output: output)
        }
        return .report(report(wire))
    }

    // The keys the app reads; any other is ignored.
    private struct Wire: Decodable {
        var ok: Bool
        var problems: [String]
        var pluginCount: Int?
        var openIn: OpenIn?
        var github: GitHub?
        var checks: [Check]?
    }

    private struct OpenIn: Decodable {
        var value: String?
        var source: String?
        var app: App?
    }

    private struct App: Decodable {
        var found: Bool?
        var bundlePath: String?
        var code: String?
        var reason: String?
    }

    private struct GitHub: Decodable {
        var state: String
        var message: String
        var fix: String?
        var ghPath: String?
        var ghVersion: String?
        var ghMinimum: String?
        var account: String?
    }

    private struct Check: Decodable {
        var id: String
        var title: String
        var state: String
        var summary: String
        var details: [Detail]?
        var remedy: Remedy?
    }

    private struct Detail: Decodable {
        var name: String
        var value: String
    }

    private struct Remedy: Decodable {
        var text: String
        var command: String?
        var url: String?
    }

    private static func report(_ wire: Wire) -> DoctorReport {
        let checks = wire.checks ?? []
        // A check's problem is listed as "<id>: …" too; the rest belong to the plugins and
        // the settings `--present` reads.
        let owned = Set(checks.map(\.id))
        let others = wire.problems.filter { problem in
            !owned.contains { problem.hasPrefix($0 + ": ") }
        }
        let openInProblems = others.filter { $0.hasPrefix("open_in: ") || $0.hasPrefix("open_in is ") }
        let pluginProblems = others.filter { !openInProblems.contains($0) }
        var rows: [DoctorReport.Row] = []
        let plugins = wire.pluginCount.map { $0 == 1 ? "1 plugin" : "\($0) plugins" } ?? "The plugins"
        rows.append(DoctorReport.Row(
            id: "plugins", title: "Plugins", state: pluginProblems.isEmpty ? .ok : .problem,
            summary: pluginProblems.isEmpty
                ? "\(plugins) and the packaged cache record contracts check out"
                : "\(pluginProblems.count) problem(s) with the plugins or the packaged cache record contracts",
            details: pluginProblems.map { DoctorReport.Detail(name: "problem", value: $0) }))
        if let openIn = wire.openIn {
            rows.append(openInRow(openIn, problems: openInProblems))
        }
        if let github = wire.github {
            rows.append(gitHubRow(github))
        }
        rows += checks.map { check in
            DoctorReport.Row(
                id: check.id, title: check.title, state: DoctorReport.State(check.state), summary: check.summary,
                details: (check.details ?? []).map { DoctorReport.Detail(name: $0.name, value: $0.value) },
                remedy: check.remedy.map { remedy($0.text, command: $0.command, url: $0.url) })
        }
        return DoctorReport(ok: wire.ok, rows: rows, hasChecks: wire.checks != nil)
    }

    private static func openInRow(_ openIn: OpenIn, problems: [String]) -> DoctorReport.Row {
        let named = openIn.value.map { "\($0) (\(openIn.source ?? "unknown"))" } ?? "unreadable"
        var details: [DoctorReport.Detail] = []
        if let app = openIn.app {
            let found = app.found == true ? (app.bundlePath ?? "found") : "none (\(app.code ?? "unknown"))"
            details.append(DoctorReport.Detail(name: "app", value: found))
            if app.found != true, let reason = app.reason { details.append(DoctorReport.Detail(name: "why", value: reason)) }
        }
        details += problems.map { DoctorReport.Detail(name: "problem", value: $0) }
        return DoctorReport.Row(
            id: "open_in", title: "Opening from Terminal", state: problems.isEmpty ? .ok : .problem,
            summary: "metab --present opens a target with open_in \(named)", details: details)
    }

    /// GitHub CLI's state is never a problem: only GitHub work needs it. Its path, version,
    /// and minimum are the doctor's, which ran with the app's tool directories on `PATH`.
    private static func gitHubRow(_ github: GitHub) -> DoctorReport.Row {
        var details: [DoctorReport.Detail] = []
        if let path = github.ghPath {
            let version = github.ghVersion.map { "version \($0)" } ?? "version unknown"
            let minimum = github.ghMinimum.map { "; needs \($0) or later" } ?? ""
            details.append(DoctorReport.Detail(name: "gh", value: "\(path) (\(version)\(minimum))"))
        } else {
            details.append(DoctorReport.Detail(name: "gh", value: "not found on PATH"))
        }
        if let account = github.account { details.append(DoctorReport.Detail(name: "account", value: account)) }
        let fix = github.fix.map { fix in
            fix.hasPrefix("https://") ? remedy("Install or update GitHub CLI:", command: nil, url: fix)
                : remedy("In Terminal:", command: fix, url: nil)
        }
        return DoctorReport.Row(
            id: "github", title: "GitHub CLI", state: github.state == "ok" ? .ok : .warning,
            summary: github.message, details: details, remedy: fix)
    }

    private static func remedy(_ text: String, command: String?, url: String?) -> DoctorReport.Remedy {
        let page = url.flatMap(URL.init(string:)).flatMap { $0.scheme == "https" ? $0 : nil }
        return DoctorReport.Remedy(text: text, command: command, url: page)
    }
}
