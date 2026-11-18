import Foundation
import Testing
@testable import ShellCore

/// File > Open Recent's decisions: reading `metab --recent --json`, and which entries
/// become rows. `metab` owns the list itself, which `tests/golden/cli-recent.tryscript.md`
/// pins; `LiveMetabTests` checks the two against each other.
@Suite struct RecentTargetsTests {
    private static let home = "/Volumes/Home"
    private static let stamp = "2026-11-18T03:14:15Z"

    private func folder(_ root: String) -> RecentTarget {
        RecentTarget(mode: .folder, root: root, openedAt: Self.stamp)
    }

    private func mirror(_ root: String) -> RecentTarget {
        RecentTarget(mode: .mirror, root: root, openedAt: Self.stamp)
    }

    /// The answer as `metab` prints it: indented, one object.
    private static let answer = """
        {
          "limit": 50,
          "targets": [
            {
              "mode": "mirror",
              "root": "https://github.com/jlevy/tbd",
              "opened_at": "2026-11-18T03:14:15Z"
            },
            {
              "mode": "folder",
              "root": "/Volumes/Home/src/fdu",
              "opened_at": "2026-11-17T22:01:09Z"
            }
          ],
          "problem": null
        }
        """

    private func result(_ text: String, status: Int32? = 0) -> CommandResult {
        CommandResult(status: status, output: text.split(separator: "\n", omittingEmptySubsequences: false).map(String.init))
    }

    // MARK: - The answer

    @Test func theAnswerIsReadInMetabsOrder() {
        let expected = RecentTargets.Listing(targets: [
            RecentTarget(mode: .mirror, root: "https://github.com/jlevy/tbd", openedAt: "2026-11-18T03:14:15Z"),
            RecentTarget(mode: .folder, root: "/Volumes/Home/src/fdu", openedAt: "2026-11-17T22:01:09Z"),
        ])
        #expect(RecentTargets.answer(result(Self.answer)) == .listing(expected))
    }

    @Test func aWarningAroundTheObjectIsSkipped() {
        let noisy = "warning: something on stderr\n" + Self.answer + "\nanother line"
        guard case .listing(let listing) = RecentTargets.answer(result(noisy)) else {
            Issue.record("the object between the warnings was not read")
            return
        }
        #expect(listing.targets.count == 2)
    }

    @Test func aProblemComesWithAnEmptyList() {
        let newer = """
            {
              "limit": 50,
              "targets": [],
              "problem": "The recent targets file uses format mf02, and this release reads formats up to mf01."
            }
            """
        guard case .listing(let listing) = RecentTargets.answer(result(newer)) else {
            Issue.record("an answer with a problem is still an answer")
            return
        }
        #expect(listing.targets.isEmpty)
        #expect(listing.problem?.contains("mf02") == true)
    }

    @Test func aMetabFromBeforeTheListIsToldApartFromAFailure() {
        let usage = "Usage: metab [OPTIONS] [ROOT]\nTry 'metab --help' for help.\n│ No such option: --recent │"
        #expect(RecentTargets.answer(result(usage, status: 2 << 8)) == .unsupported)
        #expect(
            RecentTargets.answer(result("Error: The Metabrowser storage directory is accessible to other users", status: 1 << 8))
                == .unreadable("Error: The Metabrowser storage directory is accessible to other users"))
    }

    @Test func anAnswerThatIsNotTheListIsUnreadable() {
        #expect(RecentTargets.answer(result("No recent targets.")) == .unreadable("printed no JSON object"))
        #expect(
            RecentTargets.answer(result("{\n  \"targets\": \"none\"\n}"))
                == .unreadable("printed JSON that is not a list of targets"))
        #expect(
            RecentTargets.answer(result("{\n  \"targets\": [{\"mode\": \"window\", \"root\": \"/a\", \"opened_at\": \"x\"}]\n}"))
                == .unreadable("printed JSON that is not a list of targets"))
        #expect(
            RecentTargets.answer(CommandResult(status: nil, output: [], timedOut: true))
                == .unreadable("did not answer within 20 seconds"))
        #expect(
            RecentTargets.answer(CommandResult(status: nil, output: [], launchError: "no such file"))
                == .unreadable("could not run: no such file"))
    }

    // MARK: - The rows

    @Test func everyFolderIsARowAndARepositoryOnlyInABuildThatOpensLinks() {
        let targets = [mirror("https://github.com/jlevy/tbd"), folder("/Volumes/Home/src/fdu"), folder("/")]
        let without = RecentTargets.items(targets, opensURLs: false, home: Self.home)
        #expect(without.map(\.title) == ["fdu", "/"])
        #expect(without.map(\.url) == [URL(filePath: "/Volumes/Home/src/fdu/"), URL(filePath: "/")])

        let with = RecentTargets.items(targets, opensURLs: true, home: Self.home)
        #expect(with.map(\.title) == ["tbd", "fdu", "/"])
        #expect(with.first?.url == URL(string: "https://github.com/jlevy/tbd"))
        #expect(with.map(\.target) == targets)
    }

    @Test func aRowsToolTipSaysWhereItIsAndWhatItIs() {
        let items = RecentTargets.items(
            [folder("/Volumes/Home/src/fdu"), mirror("https://github.com/jlevy/tbd")], opensURLs: true, home: Self.home)
        #expect(items.map(\.toolTip) == ["~/src/fdu · Local folder", "github.com/jlevy/tbd · Cached mirror"])
    }

    @Test func rowsThatShareAShortNameAreTitledByTheirFullNames() {
        let items = RecentTargets.items(
            [folder("/Volumes/Home/src/tbd"), mirror("https://github.com/jlevy/tbd"), folder("/Volumes/Home/notes")],
            opensURLs: true, home: Self.home)
        #expect(items.map(\.title) == ["~/src/tbd", "github.com/jlevy/tbd", "notes"])
    }

    @Test func aRootTheAppCannotOpenIsNoRow() {
        let targets = [
            mirror("file:///Volumes/Home/origin.git"),  // metab in Terminal serves it; the app has no way to
            mirror("https://example.com/team/project"),
            mirror("http://github.com/jlevy/tbd"),
            mirror("https://github.com/jlevy/tbd?tab=readme"),
            mirror("https://token@github.com/jlevy/tbd"),
            folder("relative/path"),
        ]
        #expect(RecentTargets.items(targets, opensURLs: true, home: Self.home).isEmpty)
        #expect(targets.allSatisfy { $0.url == nil })
    }

    @Test func aBuildSaysWhetherItOpensLinks() {
        #expect(RecentTargets.opensURLs(infoDictionary: [RecentTargets.opensURLsKey: true]))
        #expect(!RecentTargets.opensURLs(infoDictionary: [RecentTargets.opensURLsKey: false]))
        #expect(!RecentTargets.opensURLs(infoDictionary: [RecentTargets.opensURLsKey: "YES"]))
        #expect(!RecentTargets.opensURLs(infoDictionary: [:]))
    }

    // MARK: - The two menus

    @Test func theDockMenuHoldsTheSameTargetsAsOpenRecentInTheSameOrder() {
        let open = RecentTargets.rows(for: .openRecent, count: 3)
        let dock = RecentTargets.rows(for: .dock, count: 3)
        #expect(open == [.target(0), .target(1), .target(2), .separator, .clear])
        #expect(dock == [.target(0), .target(1), .target(2)])
        #expect(open.filter { if case .target = $0 { true } else { false } } == dock)
    }

    @Test func withNothingRecentOpenRecentSaysSoAndTheDockMenuAddsNothing() {
        #expect(RecentTargets.rows(for: .openRecent, count: 0) == [.empty, .separator, .clear])
        #expect(RecentTargets.rows(for: .dock, count: 0) == [])
    }

    // MARK: - The commands

    @Test func theCommandsAreMetabsModes() {
        #expect(RecentTargets.listArguments == ["--recent", "--json"])
        #expect(RecentTargets.clearArguments == ["--recent-clear"])
        #expect(RecentTargets.addArguments("/Volumes/Home/src/fdu") == ["/Volumes/Home/src/fdu", "--recent-add"])
        #expect(RecentTargets.forgetArguments("/Volumes/Gone/work") == ["/Volumes/Gone/work", "--recent-forget"])
    }

    @Test func aCommandRunsInTheEnvironmentEveryMetabGets() {
        let setup = RuntimeSetup(
            runtime: Runtime(executable: "/opt/tools/metab", version: "0.12.1", source: .chosen),
            tools: ToolPaths(git: "/opt/git/bin/git", gh: nil))
        let inherited = ["HOME": "/Volumes/Home", "METABROWSER_CONFIG_DIR": "/elsewhere", "UV_PYTHON": "3.14"]
        let spec = RecentTargets.spec(RecentTargets.listArguments, with: setup, inherited: inherited)
        #expect(spec.executable == "/opt/tools/metab")
        #expect(spec.arguments == ["--recent", "--json"])
        #expect(spec.environment == ChildEnvironment.build(inherited: inherited, toolDirectories: setup.tools.directories))
        // The servers the app starts get no storage override either, so both use one list.
        #expect(spec.environment["METABROWSER_CONFIG_DIR"] == nil)
    }

    /// An app started with the opt-out, as `make run` starts a development build, hands
    /// it to every `metab` it runs, so nothing that run opens is recorded.
    @Test func anAppStartedNotToRecordTellsEveryMetabItRuns() {
        #expect(RecentTargets.recordVariable == "METABROWSER_RECORD_RECENT")
        let setup = RuntimeSetup(
            runtime: Runtime(executable: "/opt/tools/metab", version: "0.12.1", source: .chosen), tools: ToolPaths())
        let off = RecentTargets.spec(
            RecentTargets.addArguments("/Volumes/Home/src/fdu"), with: setup,
            inherited: [RecentTargets.recordVariable: "0"])
        #expect(off.environment[RecentTargets.recordVariable] == "0")
        let server = CLIServeLaunch().spec(
            serving: URL(filePath: "/Volumes/Home/src/fdu/"), with: setup,
            inherited: [RecentTargets.recordVariable: "0"], logURL: nil)
        #expect(server.environment[RecentTargets.recordVariable] == "0")
        let unset = RecentTargets.spec(RecentTargets.listArguments, with: setup, inherited: [:])
        #expect(unset.environment[RecentTargets.recordVariable] == nil)
    }
}
