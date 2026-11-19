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
        let report = try report(transcript("metab --doctor --json"))
        #expect(report.ok)
        #expect(report.hasChecks)
        #expect(report.rows.map(\.id) == ["plugins", "open_in", "github", "metab", "git", "config", "cache"])
        #expect(report.rows.allSatisfy { $0.state == .ok })
        let git = try #require(report.rows.first { $0.id == "git" })
        #expect(git.title == "Git")
        #expect(git.summary == "git version 2.50.1, which meets every floor")
        #expect(git.details.map(\.name) == ["executable", "version"])
        let github = try #require(report.rows.first { $0.id == "github" })
        #expect(github.details.first?.value == "[FAKE_GH] (version 2.98.0; needs 2.81.0 or later)")
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

    @Test func readsAReportAmongOtherOutputAndIgnoresKeysItDoesNotKnow() throws {
        let output = ["warning: something on stderr"] + lines("""
            {
              "ok": false,
              "plugin_count": 1,
              "problems": [
                "plugin 'x' data_hook 'y': cannot import 'z': no module",
                "open_in is app (config.yml), and no app takes a target: LaunchServices knows no app",
                "git: a later check's problem"
              ],
              "open_in": {"value": "app", "source": "config.yml", "app": {"found": false, "code": "app_not_found",
                          "reason": "LaunchServices knows no app"}},
              "github": {"state": "gh_too_old", "message": "GitHub CLI 2.80.0 is too old.", "fix": "brew upgrade gh",
                         "gh_path": "/opt/homebrew/bin/gh", "gh_version": "2.80.0", "gh_minimum": "2.81.0",
                         "a_later_key": [1, 2]},
              "checks": [
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
        #expect(report.rows.map(\.id) == ["plugins", "open_in", "github", "git", "later"])
        let plugins = report.rows[0]
        #expect(plugins.state == .problem)
        #expect(plugins.summary == "1 problem(s) with the plugins or the packaged cache record contracts")
        #expect(plugins.details == [.init(name: "problem", value: "plugin 'x' data_hook 'y': cannot import 'z': no module")])
        let openIn = report.rows[1]
        #expect(openIn.state == .problem)
        #expect(openIn.summary == "metab --present opens a target with open_in app (config.yml)")
        #expect(openIn.details.map(\.name) == ["app", "why", "problem"])
        let github = report.rows[2]
        #expect(github.state == .warning, "GitHub CLI is never a problem: only GitHub work needs it")
        #expect(github.remedy == DoctorReport.Remedy(text: "In Terminal:", command: "brew upgrade gh"))
        #expect(github.details.first?.value == "/opt/homebrew/bin/gh (version 2.80.0; needs 2.81.0 or later)")
        #expect(report.rows[3].remedy?.url == URL(string: "https://git-scm.com/downloads"))
        let later = report.rows[4]
        #expect(later.state == .other("notice"))
        #expect(later.remedy == DoctorReport.Remedy(text: "Open this."), "only an https page opens")
    }

    /// A `metab` whose doctor predates the setup checks and GitHub's section still reports
    /// what it has, and the window says the checks are missing.
    @Test func anOlderReportHasNoCheckRows() throws {
        let report = try report(lines("""
            {
              "ok": true,
              "plugin_count": 9,
              "problems": [],
              "open_in": {"value": "browser", "source": "default", "present_browser": true, "app": null}
            }
            """))
        #expect(report.ok)
        #expect(!report.hasChecks)
        #expect(report.rows.map(\.id) == ["plugins", "open_in"])
        #expect(report.rows[0].summary == "9 plugins and the packaged cache record contracts check out")
        #expect(report.text(after: []).hasSuffix(DoctorRun.noChecks + "\n"))
    }

    @Test(arguments: [
        // No report at all, as from a crash on import.
        (["Traceback (most recent call last):", "ImportError: x"], 1, "printed no answer (exit status 1)"),
        // Not the doctor's shape: `ok` is required.
        (["{\"problems\": []}"], 0, "printed a report this app cannot read (exit status 0)"),
        (["{\"ok\": \"yes\", \"problems\": []}"], 0, "printed a report this app cannot read (exit status 0)"),
        (["{\"ok\": true, \"problems\": [], \"checks\": [{\"id\": \"git\"}]}"], 0,
         "printed a report this app cannot read (exit status 0)"),
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
        let spec = DoctorRun.spec(setup: setup, inherited: ["PATH": "/usr/bin:/bin", "HOME": "/Volumes/Home"])
        #expect(spec.executable == "/opt/metab")
        #expect(spec.arguments == ["--doctor", "--json"])
        #expect(spec.environment["PATH"]?.hasPrefix("/opt/homebrew/bin") == true)
    }
}
