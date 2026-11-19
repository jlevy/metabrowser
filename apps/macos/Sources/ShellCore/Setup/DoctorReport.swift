import Foundation

/// What `metab --doctor --json` reports, as Help > Check Setup… shows it: one row per
/// entry of `checks`, in `metab`'s order, then one for GitHub CLI, each with its state, a
/// sentence, details, and the step that fixes it.
///
/// The shape is `metab`'s, documented in `src/metabrowser/cli/doctor.py` and pinned by
/// `tests/golden/cli-doctor.tryscript.md`: `ok`, `problems`, `checks`, and the `github`
/// object of the GitHub status check. Every row comes from those structured entries and
/// their `remedy` objects; no row is chosen by, and no step read from, a sentence's
/// words. A key the app does not read is ignored. A check or `github` object the app
/// cannot decode is one unreadable row, and the rest still shows. A report from a `metab`
/// whose doctor predates `checks` lists its `problems` in one row and says the checks are
/// missing (`hasChecks`). The app reads `gh` and `git` only from here and never runs
/// either.
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
        /// The check's `id`, or `github`, or `problems` for an older report's problems.
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

    /// Names this app's bundle to the doctor, whose `metab` check then compares with this
    /// build's minimum (`DOCTOR_APP_ENV` in `src/metabrowser/cli/doctor.py`), not with
    /// the app LaunchServices finds first, which is the release build when both are
    /// installed.
    public static let appVariable = "METABROWSER_DOCTOR_APP"

    /// `appBundle` is this app's bundle path, which the doctor reads the minimum from.
    public static func spec(setup: RuntimeSetup, inherited: [String: String], appBundle: String) -> LaunchSpec {
        var environment = ChildEnvironment.build(inherited: inherited, toolDirectories: setup.tools.directories)
        environment[appVariable] = appBundle
        return LaunchSpec(executable: setup.runtime.executable, arguments: arguments, environment: environment)
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
        guard let wire = try? JSONDecoder().decode(Wire.self, from: data) else {
            return .unreadable(reason: "printed a report this app cannot read (\(status))", output: output)
        }
        return .report(report(wire))
    }

    // The keys the app reads, each named in a `CodingKeys` as `metab` spells it; any other
    // is ignored.
    private struct Wire: Decodable {
        var ok: Bool
        var problems: [String]?
        var checks: [Entry<Check>]?
        var github: Entry<GitHub>?

        enum CodingKeys: String, CodingKey {
            case ok = "ok"
            case problems = "problems"
            case checks = "checks"
            case github = "github"
        }
    }

    /// One entry that may not decode, such as a check from a later `metab` with a value
    /// of another type: it is kept as unreadable, with its `id` when it has one, so one
    /// entry never hides the rest of the report.
    private enum Entry<Value: Decodable>: Decodable {
        case read(Value)
        case unreadable(id: String?)

        init(from decoder: any Decoder) throws {
            if let value = try? Value(from: decoder) {
                self = .read(value)
            } else {
                let container = try? decoder.container(keyedBy: Check.CodingKeys.self)
                self = .unreadable(id: try? container?.decode(String.self, forKey: .id))
            }
        }
    }

    private struct GitHub: Decodable {
        var state: String
        var message: String
        var remedy: Remedy?
        var ghPath: String?
        var ghVersion: String?
        var ghMinimum: String?
        var account: String?

        enum CodingKeys: String, CodingKey {
            case state = "state"
            case message = "message"
            case remedy = "remedy"
            case ghPath = "gh_path"
            case ghVersion = "gh_version"
            case ghMinimum = "gh_minimum"
            case account = "account"
        }
    }

    private struct Check: Decodable {
        var id: String
        var title: String
        var state: String
        var summary: String
        var details: [Detail]?
        var remedy: Remedy?

        enum CodingKeys: String, CodingKey {
            case id = "id"
            case title = "title"
            case state = "state"
            case summary = "summary"
            case details = "details"
            case remedy = "remedy"
        }
    }

    private struct Detail: Decodable {
        var name: String
        var value: String

        enum CodingKeys: String, CodingKey {
            case name = "name"
            case value = "value"
        }
    }

    private struct Remedy: Decodable {
        var text: String
        var command: String?
        var url: String?

        enum CodingKeys: String, CodingKey {
            case text = "text"
            case command = "command"
            case url = "url"
        }
    }

    /// What the window says of an entry it cannot read.
    static let unreadableSummary = "metab reported this in a shape this app cannot read; a newer Metabrowser may."

    private static func report(_ wire: Wire) -> DoctorReport {
        var rows: [DoctorReport.Row] = []
        if let checks = wire.checks {
            rows += checks.map { entry in
                switch entry {
                case .read(let check): checkRow(check)
                case .unreadable(let id): unreadableRow(id: id ?? "unreadable", title: id ?? "A check")
                }
            }
        } else if let problems = wire.problems, !problems.isEmpty {
            // An older `metab` lists its problems only as text, which is shown as it is.
            rows.append(DoctorReport.Row(
                id: "problems", title: "Problems", state: .problem, summary: "\(problems.count) problem(s)",
                details: problems.map { DoctorReport.Detail(name: "problem", value: $0) }))
        }
        switch wire.github {
        case .read(let github): rows.append(gitHubRow(github))
        case .unreadable: rows.append(unreadableRow(id: "github", title: "GitHub CLI"))
        case nil: break
        }
        return DoctorReport(ok: wire.ok, rows: rows, hasChecks: wire.checks != nil)
    }

    private static func checkRow(_ check: Check) -> DoctorReport.Row {
        DoctorReport.Row(
            id: check.id, title: check.title, state: DoctorReport.State(check.state), summary: check.summary,
            details: (check.details ?? []).map { DoctorReport.Detail(name: $0.name, value: $0.value) },
            remedy: check.remedy.map(remedyOf))
    }

    private static func unreadableRow(id: String, title: String) -> DoctorReport.Row {
        DoctorReport.Row(id: id, title: title, state: .other("unreadable"), summary: unreadableSummary)
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
        return DoctorReport.Row(
            id: "github", title: "GitHub CLI", state: github.state == "ok" ? .ok : .warning,
            summary: github.message, details: details, remedy: github.remedy.map(remedyOf))
    }

    private static func remedyOf(_ wire: Remedy) -> DoctorReport.Remedy {
        let page = wire.url.flatMap(URL.init(string:)).flatMap { $0.scheme == "https" ? $0 : nil }
        return DoctorReport.Remedy(text: wire.text, command: wire.command, url: page)
    }
}
