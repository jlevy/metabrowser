import Foundation
import Testing
@testable import ShellCore

/// A wait status for `code`, as `ExitStatus` decodes one.
nonisolated private func exited(_ code: Int32) -> Int32 { code << 8 }

private func lines(_ text: String) -> [String] {
    text.split(separator: "\n", omittingEmptySubsequences: false).map(String.init)
}

private func answer(_ output: [String], code: Int32 = 0) -> DoctorAnswer {
    DoctorRun.answer(CommandResult(status: exited(code), output: output))
}

private func report(_ output: [String], code: Int32 = 0) throws -> DoctorReport {
    guard case .report(let report) = answer(output, code: code) else {
        Issue.record("no report from \(output)")
        throw CancellationError()
    }
    return report
}

/// Help > Check Setup…'s reading of `metab --doctor --json` (`DoctorRun`). The report is
/// `metab`'s, pinned by `tests/golden/cli-doctor.tryscript.md`, and the first tests read
/// it from there, so a change to its shape fails here as well as in the transcript.
@Suite struct DoctorReportTests {
    /// The output of `command` in the doctor's transcript: the lines after it, up to its
    /// exit status.
    private func transcript(_ command: String) throws -> [String] {
        let root = URL(filePath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let golden = try String(
            contentsOf: root.appending(path: "tests/golden/cli-doctor.tryscript.md"), encoding: .utf8)
        let all = lines(golden)
        let start = try #require(all.firstIndex(of: "$ " + command), "no `\(command)` in the transcript") + 1
        let end = try #require(all[start...].firstIndex { $0.hasPrefix("? ") })
        return Array(all[start..<end])
    }

    @Test func readsTheReportMetabPrints() throws {
        let output = try transcript("metab --doctor --json")
        let report = try report(output)
        #expect(report.ok)
        #expect(report.hasChecks)
        #expect(
            report.rows.map(\.id)
                == ["plugins", "open_in", "metab", "git", "config", "cache", "event_log", "github"])
        #expect(report.rows.allSatisfy { $0.state == .ok })
        // A check the app has no special word for is one more row, from the structured entry.
        let eventLog = try #require(report.rows.first { $0.id == "event_log" })
        #expect(eventLog.title == "Event log")
        #expect(eventLog.details.map(\.name).prefix(2) == ["directory", "source"])
        let json = try JSONSerialization.jsonObject(with: Data(output.joined(separator: "\n").utf8))
        let payload = try #require(json as? [String: Any])
        let checks = try #require(payload["checks"] as? [[String: Any]])
        let plugins = try #require(checks.first { $0["id"] as? String == "plugins" })
        #expect(report.rows[0].summary == plugins["summary"] as? String)
        #expect(report.rows[1].title == "Opening from a terminal")
        let git = try #require(report.rows.first { $0.id == "git" })
        #expect(git.title == "Git")
        #expect(git.summary == "git version 2.56.1, which meets every floor")
        #expect(git.details.map(\.name) == ["executable", "version", "file ages"])
        #expect(git.details.last?.value == "available")
        let github = try #require(report.rows.last)
        #expect(github.details.first?.value == "[FAKE_GH] (version 2.98.0; needs 2.81.0 or later)")
        #expect(github.remedy == nil)
    }

    /// A check's problem is listed among the problems too; the row is the check's own.
    @Test func aProblemIsTheChecksRow() throws {
        let report = try report(
            transcript(
                "METABROWSER_CONFIG_DIR=$PWD/config METABROWSER_CACHE_DIR=relative metab --doctor --json 2>/dev/null"),
            code: 1)
        #expect(!report.ok)
        let cache = try #require(report.rows.first { $0.id == "cache" })
        #expect(cache.state == .problem)
        #expect(cache.summary.hasPrefix("METABROWSER_CACHE_DIR must be"))
        let plugins = try #require(report.rows.first { $0.id == "plugins" })
        #expect(plugins.state == .ok, "the cache's problem is not the plugins'")
    }

    /// Every row is an entry of `checks` or the `github` object, as `metab` sent it: no
    /// problem is placed by its words, and a step is a command only when `remedy` says so.
    @Test func readsAReportAmongOtherOutputAndIgnoresKeysItDoesNotKnow() throws {
        let output = ["warning: something on stderr"] + lines("""
            {
              "ok": false,
              "plugin_count": 1,
              "problems": ["plugin 'x' data_hook 'y': cannot import 'z': no module", "git: a later check's problem"],
              "github": {"state": "not_logged_in", "message": "GH_TOKEN is not accepted.",
                         "fix": "replace the token in GH_TOKEN, or unset it and run gh auth login",
                         "remedy": {"text": "Replace the token in GH_TOKEN, or unset it and run gh auth login.",
                                    "command": null, "url": null},
                         "gh_path": "/opt/homebrew/bin/gh", "gh_version": "2.80.0", "gh_minimum": "2.81.0",
                         "a_later_key": [1, 2]},
              "checks": [
                {"id": "plugins", "title": "Plugins", "state": "problem", "summary": "1 problem(s)",
                 "details": [{"name": "plugins", "value": "1"},
                             {"name": "problem", "value": "plugin 'x' data_hook 'y': cannot import 'z': no module"}],
                 "remedy": null},
                {"id": "git", "title": "Git", "state": "problem", "summary": "a later check's problem",
                 "details": [{"name": "version", "value": "git version 2.40.0"}],
                 "remedy": {"text": "Install Git.", "command": null, "url": "https://git-scm.com/downloads"}},
                {"id": "later", "title": "A later check", "state": "notice", "summary": "something new",
                 "details": [], "remedy": {"text": "Open this.", "command": null, "url": "file:///etc/passwd"}}
              ],
              "a_later_section": {"state": "ok"}
            }
            """)
        let report = try report(output, code: 1)
        #expect(!report.ok)
        #expect(report.rows.map(\.id) == ["plugins", "git", "later", "github"])
        let plugins = report.rows[0]
        #expect(plugins.state == .problem)
        #expect(plugins.details.map(\.name) == ["plugins", "problem"])
        #expect(report.rows[1].remedy?.url == URL(string: "https://git-scm.com/downloads"))
        let later = report.rows[2]
        #expect(later.state == .other("notice"))
        #expect(later.remedy == DoctorReport.Remedy(text: "Open this."), "only an https page opens")
        let github = report.rows[3]
        #expect(github.state == .warning, "GitHub CLI is never a problem: only GitHub work needs it")
        #expect(
            github.remedy == DoctorReport.Remedy(text: "Replace the token in GH_TOKEN, or unset it and run gh auth login."),
            "a sentence is never a command to copy")
        #expect(github.details.first?.value == "/opt/homebrew/bin/gh (version 2.80.0; needs 2.81.0 or later)")
    }

    /// One entry a later or broken `metab` sends in another shape is one row the window
    /// cannot read, with its `id` when it has one; the rest of the report still shows.
    @Test func aCheckThatDoesNotDecodeIsOneUnreadableRow() throws {
        let report = try report(lines("""
            {
              "ok": true,
              "problems": [],
              "checks": [
                {"id": "plugins", "title": "Plugins", "state": "ok", "summary": "fine"},
                {"id": "git", "title": "Git", "state": "ok", "summary": "fine", "details": [{"name": "major", "value": 2}]},
                {"title": "No id", "state": "ok", "summary": "fine", "remedy": {"command": "true"}},
                null
              ],
              "github": {"state": "ok", "message": "fine", "remedy": {"text": 3}}
            }
            """))
        #expect(report.rows.map(\.id) == ["plugins", "git", "unreadable", "unreadable", "github"])
        #expect(report.rows[0].state == .ok)
        for row in report.rows.dropFirst() {
            #expect(row.state == .other("unreadable"))
            #expect(row.summary == DoctorRun.unreadableSummary)
        }
        #expect(report.rows.map(\.title) == ["Plugins", "git", "A check", "A check", "GitHub CLI"])
    }

    /// A `metab` whose doctor predates the setup checks and GitHub's section still reports
    /// its problems, as it words them, and the window says the checks are missing.
    @Test func anOlderReportHasNoCheckRows() throws {
        let older = try report(lines("""
            {
              "ok": false,
              "plugin_count": 9,
              "problems": ["plugin 'x': index.js missing"],
              "open_in": {"value": "browser", "source": "default", "present_browser": true, "app": null}
            }
            """), code: 1)
        #expect(!older.ok)
        #expect(!older.hasChecks)
        #expect(older.rows.map(\.id) == ["problems"])
        #expect(older.rows[0].details == [.init(name: "problem", value: "plugin 'x': index.js missing")])
        #expect(older.text(after: []).contains(DoctorRun.noChecks))
        #expect(older.text(after: []).hasSuffix(ProjectLinks.installationGuide.absoluteString + "\n"))
        let clean = try report(lines(#"{"ok": true, "plugin_count": 9, "problems": []}"#))
        #expect(clean.rows.isEmpty)
        #expect(!clean.hasChecks)
    }

    @Test(arguments: [
        // No report at all, as from a crash on import.
        (["Traceback (most recent call last):", "ImportError: x"], 1, "printed no answer (exit status 1)"),
        // Not the doctor's shape: `ok` is required, and `checks` is a list.
        (["{\"problems\": []}"], 0, "printed a report this app cannot read (exit status 0)"),
        (["{\"ok\": \"yes\", \"problems\": []}"], 0, "printed a report this app cannot read (exit status 0)"),
        (["{\"ok\": true, \"checks\": {\"id\": \"git\"}}"], 0, "printed a report this app cannot read (exit status 0)"),
        (["{\"ok\": true, \"problems\": []}", "{\"ok\": true, \"problems\": []}"], 0, "printed 2 answers (exit status 0)"),
    ])
    func malformedOutputIsNoReport(output: [String], code: Int32, reason: String) {
        #expect(answer(output, code: code) == .unreadable(reason: reason, output: output))
    }

    @Test func aRunThatCannotStartOrFinishIsNoReport() {
        #expect(
            DoctorRun.answer(CommandResult(status: nil, output: [], launchError: "No such file or directory"))
                == .unreadable(reason: "could not run: No such file or directory", output: []))
        #expect(
            DoctorRun.answer(CommandResult(status: nil, output: ["importing"], timedOut: true))
                == .unreadable(reason: "did not finish within 60 seconds", output: ["importing"]))
    }

    @Test func copyReportNamesTheAppAndTheMetabThenEachRow() {
        let app = AppIdentity(infoDictionary: [
            "CFBundleName": "Metabrowser", "CFBundleShortVersionString": "0.1.0", "CFBundleVersion": "2466",
            AppIdentity.commitKey: "abc1234",
        ])
        let setup = RuntimeSetup(
            runtime: Runtime(executable: "/Volumes/Home/.local/bin/metab", version: "0.13.0", source: .localBin),
            tools: ToolPaths(git: "/usr/bin/git", gh: nil))
        let header = DoctorRun.header(app: app, setup: setup)
        #expect(header == [
            "Metabrowser: Development build · 0.1.0 (2466) · abc1234; runs metab \(MetabRequirement.minimum) or later",
            "metab: 0.13.0 at /Volumes/Home/.local/bin/metab (found: ~/.local/bin)",
        ])
        #expect(DoctorRun.header(app: app, setup: nil).last == "metab: none selected")
        let report = DoctorReport(
            ok: true,
            rows: [
                .init(
                    id: "git", title: "Git", state: .warning, summary: "below the floor",
                    details: [.init(name: "version", value: "git version 2.39.5")],
                    remedy: .init(text: "Install Git with Homebrew.", command: "brew install git")),
                .init(
                    id: "github", title: "GitHub CLI", state: .warning, summary: "not found",
                    remedy: .init(text: "Install GitHub CLI:", url: URL(string: "https://cli.github.com/"))),
            ],
            hasChecks: true)
        #expect(DoctorRun.text(header: ["app"], answer: .report(report)) == """
            app
            No problems.
            git: warning: below the floor
              version: git version 2.39.5
              fix: Install Git with Homebrew. brew install git
            github: warning: not found
              fix: Install GitHub CLI: https://cli.github.com/

            """)
        #expect(DoctorRun.text(header: ["app"], answer: .unreadable(reason: "printed no answer", output: ["boom"])) == """
            app
            metab --doctor --json printed no answer.
            It printed:
              boom

            """)
    }

    @Test func theRunIsTheDoctorsJSONWithTheAppsTools() {
        let setup = RuntimeSetup(
            runtime: Runtime(executable: "/opt/metab", version: "0.13.0", source: .chosen),
            tools: ToolPaths(git: "/opt/homebrew/bin/git", gh: "/opt/homebrew/bin/gh"))
        let spec = DoctorRun.spec(
            setup: setup,
            inherited: ["PATH": "/usr/bin:/bin", "HOME": "/Volumes/Home", DoctorRun.appVariable: "/elsewhere.app"],
            appBundle: "/Applications/Metabrowser.app")
        #expect(spec.executable == "/opt/metab")
        #expect(spec.arguments == ["--doctor", "--json"])
        #expect(spec.environment["PATH"]?.hasPrefix("/opt/homebrew/bin") == true)
        #expect(spec.environment[DoctorRun.appVariable] == "/Applications/Metabrowser.app", "this app, never an inherited one")
    }
}
