import Darwin
import Foundation
import Testing
@testable import ShellCore

/// A wait status for `code`, as `ExitStatus` decodes one.
nonisolated private func exited(_ code: Int32) -> Int32 { code << 8 }

nonisolated private func result(_ output: [String], code: Int32 = 0) -> CommandResult {
    CommandResult(status: exited(code), output: output)
}

private func lines(_ text: String) -> [String] {
    text.split(separator: "\n", omittingEmptySubsequences: false).map(String.init)
}

private func answer(_ json: String, code: Int32 = 0) -> PresentAnswer {
    PresentDryRun.answer(result(lines(json), code: code))
}

private let repository = URL(string: "https://github.com/jlevy/tbd")!

/// What `metab LINK --present --dry-run --format json` prints, copied from #540's `metab`
/// (`json.dumps(…, indent=2)`), with its exit status. `LiveMetabTests` runs the real
/// command for each kind, so these stay what it prints.
private nonisolated enum Fixture {
    static let pullRequest = """
        {
          "kind": "pull_request",
          "root": "https://github.com/jlevy/tbd",
          "page": "/pull/12",
          "handoff": [
            "https://github.com/jlevy/tbd/pull/12"
          ],
          "refusal": null
        }
        """
    /// A ref with a `/` in it: only the mirror knows where it ends, so `page` is null.
    static let fileOnABranchWithASlash = """
        {
          "kind": "file",
          "root": "https://github.com/jlevy/tbd",
          "page": null,
          "handoff": [
            "https://github.com/jlevy/tbd/blob/claude/app-open-urls/docs/macos-app.md"
          ],
          "refusal": null
        }
        """
    /// A raw link with a token: the handoff is the web link with nothing the reducer drops.
    static let rawWithAToken = """
        {
          "kind": "file",
          "root": "https://github.com/jlevy/tbd",
          "page": "/view/g1-UkVBRE1FLm1k",
          "handoff": [
            "https://github.com/jlevy/tbd/blob/main/README.md"
          ],
          "refusal": null
        }
        """
    static let shortCommit = """
        {
          "kind": "commit",
          "root": "https://github.com/jlevy/tbd",
          "page": null,
          "handoff": [
            "https://github.com/jlevy/tbd/commit/dcf2bcfa8"
          ],
          "refusal": null
        }
        """
    /// Exit 3, `PRESENT_REFUSED_EXIT_CODE`.
    static let refusal = """
        {
          "kind": null,
          "root": null,
          "page": null,
          "handoff": null,
          "refusal": {
            "code": "unsupported_github_url",
            "message": "GitHub issues pages are not opened; open the repository at https://github.com/jlevy/tbd"
          }
        }
        """
    static func plan(kind: String = "repository", root: String = "https://github.com/jlevy/tbd", handoff: String = #"["https://github.com/jlevy/tbd"]"#) -> String {
        #"{"kind": "\#(kind)", "root": "\#(root)", "page": "/view/", "handoff": \#(handoff), "refusal": null}"#
    }
}

@Suite struct GitHubLinkTests {
    @Test(arguments: [
        "https://github.com/jlevy/tbd",
        "https://github.com/jlevy/tbd/pull/12/files",
        "https://www.github.com/jlevy/tbd/blob/main/README.md#L3",
        "https://raw.githubusercontent.com/jlevy/tbd/main/README.md",
        "https://raw.githubusercontent.com/jlevy/tbd/main/README.md?token=SECRET",
        "HTTPS://GitHub.com/jlevy/tbd",
        "https://github.com:443/jlevy/tbd",
        "https://github.com",
        // Refused by metab, which says why: the app reads only the scheme and the host.
        "https://github.com/jlevy/tbd/issues/4",
        "https://github.com/settings",
    ])
    func handsGitHubLinksToMetab(_ link: String) {
        #expect(GitHubLink.accepts(URL(string: link)!))
    }

    /// Review B's probes: each is refused on the string the app would pass, whatever host
    /// Foundation decodes from it (B3), and a user or password never passes (A8).
    @Test(arguments: [
        "http://github.com/jlevy/tbd",
        "ssh://git@github.com/jlevy/tbd.git",
        "https://gitlab.com/jlevy/tbd",
        "https://github.com.example.net/jlevy/tbd",
        "https://gist.github.com/jlevy/abc",
        "metabrowser://open?path=/tmp",
        "mailto:someone@example.com",
        "https://github%2Ecom/o/r",
        "https://[github.com]/o/r",
        "https://github.com:8443/o/r",
        "https://user:tok@github.com/o/r",
        "https://x-access-token:TOKEN@github.com/o/r.git",
        "https://github.com@evil.com/o/r",
        "https://evil.com#@github.com/o/r",
        "https://evil.com?@github.com/o/r",
        "https://github.com%2F.evil.com/o/r",
        "https://github.com./o/r",
    ])
    func refusesEverythingElse(_ link: String) {
        guard let url = URL(string: link) else { return }  // Foundation refused it already
        #expect(!GitHubLink.accepts(url))
    }

    /// No link is too long for Foundation, so the app bounds what it passes and shows (B4).
    @Test func anOverlongLinkIsRefused() {
        let long = URL(string: "https://github.com/o/r/blob/main/" + String(repeating: "a", count: 70_000))!
        #expect(!GitHubLink.accepts(long))
        let longest = URL(string: "https://github.com/o/r/blob/main/" + String(repeating: "a", count: 8_000))!
        #expect(GitHubLink.accepts(longest))
        #expect(GitHubLink.shown(long).count == GitHubLink.shownLength)
        #expect(GitHubLink.shown(long).hasPrefix("https://github.com/o/r/blob/main/"))
        #expect(GitHubLink.shown(repository) == repository.absoluteString)
        // A user name or password, which can be a token, is not shown.
        #expect(GitHubLink.shown(URL(string: "https://x-access-token:SECRET@github.com/o/r")!) == "https://github.com/o/r")
    }

    @Test func theDryRunIsTheContractsCommandRunInTheHomeFolder() {
        let link = URL(string: "https://github.com/jlevy/tbd/pull/12")!
        #expect(PresentDryRun.arguments(for: link) == [link.absoluteString, "--present", "--dry-run", "--format", "json"])
        #expect(PresentDryRun.timeout == RuntimeDiscovery.versionTimeout)
        let setup = RuntimeSetup(
            runtime: Runtime(executable: "/opt/metab", version: "0.12.1", source: .chosen, fingerprint: nil),
            tools: ToolPaths(git: "/usr/bin/git", gh: "/opt/homebrew/bin/gh"))
        let spec = PresentDryRun.spec(for: link, with: setup, inherited: ["HOME": "/tmp/account"], home: "/tmp/account")
        #expect(spec.executable == "/opt/metab")
        #expect(spec.workingDirectory == "/tmp/account")
        #expect(spec.environment["PATH"]?.split(separator: ":").contains("/opt/homebrew/bin") == true)
    }
}

@Suite struct PresentDryRunTests {
    @Test func aPullRequestIsServedWithItsCanonicalLink() {
        #expect(answer(Fixture.pullRequest) == .plan(PresentPlan(
            kind: .pullRequest, repository: repository, link: URL(string: "https://github.com/jlevy/tbd/pull/12")!)))
    }

    /// A null page, which #540 gives where only the mirror knows where a ref ends, is no
    /// obstacle: the app reads no page, and its window shows the server's entry page.
    @Test func aNullPageStillOpens() {
        #expect(answer(Fixture.fileOnABranchWithASlash) == .plan(PresentPlan(
            kind: .file, repository: repository,
            link: URL(string: "https://github.com/jlevy/tbd/blob/claude/app-open-urls/docs/macos-app.md")!)))
        #expect(answer(Fixture.shortCommit) == .plan(PresentPlan(
            kind: .commit, repository: repository, link: URL(string: "https://github.com/jlevy/tbd/commit/dcf2bcfa8")!)))
    }

    /// The server is started with the handoff, so a token in a raw link never reaches it.
    @Test func theServerGetsTheHandoffNotTheLink() {
        guard case .plan(let plan) = answer(Fixture.rawWithAToken) else {
            Issue.record("expected a plan")
            return
        }
        #expect(plan.link.absoluteString == "https://github.com/jlevy/tbd/blob/main/README.md")
        #expect(!plan.link.absoluteString.contains("token"))
    }

    @Test func aRefusalCarriesMetabsMessage() {
        let expected = PresentRefusal(
            code: "unsupported_github_url",
            message: "GitHub issues pages are not opened; open the repository at https://github.com/jlevy/tbd")
        #expect(answer(Fixture.refusal, code: 3) == .refused(expected))
        let alert = answer(Fixture.refusal, code: 3).alert(
            link: URL(string: "https://github.com/jlevy/tbd/issues/4")!, metab: "metab 0.12.1 at /opt/metab")
        #expect(alert?.detail == expected.message + "\n\nhttps://github.com/jlevy/tbd/issues/4")
    }

    /// An alert shows the link and every line of `metab`'s output shortened (B4).
    @Test func anAlertIsBoundedWhateverItShows() {
        let long = URL(string: "https://github.com/o/r/blob/main/" + String(repeating: "a", count: 7_000))!
        let message = String(repeating: "m", count: 10_000)
        let refused = PresentAnswer.refused(PresentRefusal(code: "x", message: message)).alert(link: long, metab: "metab")
        #expect((refused?.detail.count ?? .max) <= PresentAnswer.shownLineLength + 2 + GitHubLink.shownLength)
        let unreadable = PresentAnswer.unreadable(reason: "printed no answer", output: Array(repeating: message, count: 9))
            .alert(link: long, metab: "metab")
        #expect(unreadable?.detail.split(separator: "\n").allSatisfy { $0.count <= PresentAnswer.shownLineLength } == true)
    }

    /// stdout and stderr share the command's pipe, so a warning before or after the JSON
    /// must not hide the answer.
    @Test func linesOnStderrAroundTheAnswerArePassedOver() {
        let noisy = ["WARNING: ignoring METABROWSER_FOO in /tmp/account/.env"] + lines(Fixture.pullRequest) + ["a late line"]
        #expect(PresentDryRun.answer(result(noisy)) == answer(Fixture.pullRequest))
        let compact = ["{not json}", Fixture.plan(), "done"]
        #expect(PresentDryRun.answer(result(compact)) == answer(Fixture.plan()))
    }

    /// A stray object on stderr, before or after the real answer, makes the answer
    /// unreadable rather than standing in for it (B5).
    @Test func twoAnswersAreNone() {
        let strayRefusal = #"{"refusal": {"code": "x", "message": "stray"}}"#
        let strayPlan = Fixture.plan(handoff: #"["https://github.com/jlevy/tbd/pull/99"]"#)
        for output in [[strayRefusal] + lines(Fixture.pullRequest), lines(Fixture.pullRequest) + [strayPlan],
                       [strayPlan, Fixture.plan()]] {
            guard case .unreadable(let reason, _) = PresentDryRun.answer(result(output)) else {
                Issue.record("expected two answers to be unreadable: \(output)")
                continue
            }
            #expect(reason.hasPrefix("printed 2 answers"))
        }
    }

    @Test(arguments: [
        // Exit 0 must come with a plan.
        (#"{"kind": null, "root": null, "page": null, "handoff": null, "refusal": null}"#, Int32(0)),
        // A plan must come with exit 0.
        (Fixture.plan(), Int32(1)),
        (Fixture.plan(kind: "issue"), Int32(0)),
        // A link resolves to a repository, never a folder on this Mac (B5).
        (Fixture.plan(kind: "folder"), Int32(0)),
        (Fixture.plan(root: "/tmp/account/notes", handoff: #"["/tmp/account/notes"]"#), Int32(0)),
        (Fixture.plan(root: "relative/path"), Int32(0)),
        (Fixture.plan(root: "https://github.com/jlevy/tbd/pull/12"), Int32(0)),
        (#"{"kind": 3, "root": "https://github.com/jlevy/tbd", "handoff": ["https://github.com/jlevy/tbd"], "refusal": null}"#, Int32(0)),
        // The handoff is one link into the root's repository, on github.com, that the app
        // would accept itself.
        (Fixture.plan(handoff: "null"), Int32(0)),
        (Fixture.plan(handoff: "[]"), Int32(0)),
        (Fixture.plan(handoff: #"["https://github.com/jlevy/tbd", "https://github.com/jlevy/tbd"]"#), Int32(0)),
        (Fixture.plan(handoff: #"["https://github.com/jlevy/tbdx"]"#), Int32(0)),
        (Fixture.plan(handoff: #"["https://github.com/other/repo"]"#), Int32(0)),
        (Fixture.plan(handoff: #"["https://evil.example/jlevy/tbd"]"#), Int32(0)),
        (Fixture.plan(handoff: #"["https://raw.githubusercontent.com/jlevy/tbd/main/a"]"#), Int32(0)),
        (Fixture.plan(handoff: #"["http://github.com/jlevy/tbd"]"#), Int32(0)),
        (Fixture.plan(handoff: #"["--exit-on-eof"]"#), Int32(0)),
        (Fixture.plan(handoff: #"["https://github.com/jlevy/tbd/blob/main/\#(String(repeating: "a", count: 9_000))"]"#), Int32(0)),
        ("Traceback (most recent call last):", Int32(1)),
        ("", Int32(0)),
    ])
    func anythingElseIsUnreadable(_ json: String, _ code: Int32) {
        guard case .unreadable = answer(json, code: code) else {
            Issue.record("expected an unreadable answer for \(json)")
            return
        }
    }

    /// A `metab` from before `--present` is refused at setup (`RuntimeDiscovery.validate`),
    /// so its usage error here is only an answer the app cannot read.
    @Test func aUsageErrorIsUnreadable() {
        let clickUsageError = [
            "Usage: metab [OPTIONS] [ROOT]", "Try 'metab --help' for help.", "", "Error: No such option: --present",
        ]
        guard case .unreadable(let reason, let output) = PresentDryRun.answer(result(clickUsageError, code: 2)) else {
            Issue.record("expected an unreadable answer")
            return
        }
        #expect(reason == "printed no answer (exit status 2)")
        #expect(output == clickUsageError)
    }

    @Test func aRunThatFailedOrTimedOutIsUnreadableAndSaysSo() {
        let crashed = PresentDryRun.answer(CommandResult(status: nil, output: [], launchError: "No such file or directory"))
        #expect(crashed == .unreadable(reason: "could not run: No such file or directory", output: []))
        let slow = PresentDryRun.answer(CommandResult(status: nil, output: ["importing"], timedOut: true))
        #expect(slow == .unreadable(reason: "did not answer within \(PresentDryRun.timeout)", output: ["importing"]))
        let alert = slow.alert(link: repository, metab: "metab 0.12.1 at /opt/metab")
        #expect(alert?.detail == "https://github.com/jlevy/tbd\n\nmetab 0.12.1 at /opt/metab did not answer within 20.0 seconds. Its last output:\nimporting")
    }

    @Test func anOversizedAnswerIsNotRead() {
        let huge = Array(repeating: String(repeating: "x", count: 1000), count: 600) + [Fixture.plan()]
        guard case .unreadable(let reason, _) = PresentDryRun.answer(result(huge)) else {
            Issue.record("expected an unreadable answer")
            return
        }
        #expect(reason.contains("more than"))
    }

    @Test(arguments: [
        ("https://github.com/jlevy/tbd", true),
        ("https://github.com/a-b/c.d_e-f", true),
        ("https://github.com/jlevy/tbd/", false),
        ("https://github.com/jlevy", false),
        ("https://github.com/jlevy/tbd.git?x=1", false),
        ("https://github.com/jlevy/..", false),
        ("https://www.github.com/jlevy/tbd", false),
        ("http://github.com/jlevy/tbd", false),
        ("https://user@github.com/jlevy/tbd", false),
        ("https://github.com/jl%65vy/tbd", false),
    ])
    func onlyACanonicalRepositoryURLIsARepositoryRoot(_ text: String, _ canonical: Bool) {
        #expect((PresentPlan.repositoryURL(text) != nil) == canonical)
    }
}

@Suite struct LinkQueueTests {
    private func link(_ n: Int) -> URL { URL(string: "https://github.com/o/r/pull/\(n)")! }

    @Test func linksAreResolvedOneAtATimeInTheOrderSent() {
        var queue = LinkQueue()
        #expect(queue.isIdle)
        #expect(queue.offer(link(1)) == .queued)
        #expect(queue.offer(link(2)) == .queued)
        #expect(queue.next() == link(1))
        #expect(queue.next() == nil)  // one is being resolved
        #expect(!queue.isIdle)
        queue.finish()
        #expect(queue.next() == link(2))
        queue.finish()
        #expect(queue.next() == nil)
        #expect(queue.isIdle)
    }

    /// B1: a link equal to one waiting or being resolved opens once.
    @Test func aRepeatedLinkIsDropped() {
        var queue = LinkQueue()
        _ = queue.offer(link(1))
        #expect(queue.offer(link(1)) == .repeated)
        _ = queue.next()
        #expect(queue.offer(link(1)) == .repeated)
        queue.finish()
        #expect(queue.offer(link(1)) == .queued)
    }

    /// B1: past the limit, links are counted, and said once.
    @Test func aBurstPastTheLimitIsCountedNotKept() {
        var queue = LinkQueue()
        _ = queue.offer(link(0))
        _ = queue.next()
        for n in 1...LinkQueue.limit { #expect(queue.offer(link(n)) == .queued) }
        #expect(queue.offer(link(LinkQueue.limit + 1)) == .dropped)
        #expect(queue.offer(link(LinkQueue.limit + 2)) == .dropped)
        #expect(queue.waiting.count == LinkQueue.limit)
        #expect(queue.takeDropped() == 2)
        #expect(queue.takeDropped() == 0)
    }

    /// B1: a burst's problems are one alert, not one modal each.
    @Test func aBurstsProblemsAreOneAlert() {
        let one = LinkAlert(message: "Metabrowser cannot open this link", detail: "why")
        #expect(LinkAlert.combined([]) == nil)
        #expect(LinkAlert.combined([one]) == one)
        let many = LinkAlert.combined(Array(repeating: one, count: 7), dropped: 3)
        #expect(many?.message == "Metabrowser could not open 10 links")
        #expect(many?.detail.contains("3 more links were not opened") == true)
        #expect(many?.detail.contains("and 2 more.") == true)
        #expect(many?.detail.components(separatedBy: "Metabrowser cannot open this link: why").count == LinkAlert.shownInBatch + 1)
    }
}

@Suite struct RepositoryCacheTests {
    private let setup = RuntimeSetup(
        runtime: Runtime(executable: "/opt/metab", version: "0.12.1", source: .chosen, fingerprint: nil),
        tools: ToolPaths())

    nonisolated private static func page(_ sources: [(String, String, String)], next: String? = nil) -> CommandResult {
        let rows = sources.map { url, publication, problems in
            #"{"slug": "s", "publication": "\#(publication)", "identity": {"display_url": "\#(url)"}, "problems": \#(problems)}"#
        }
        let after = next.map { "\"\($0)\"" } ?? "null"
        return result([#"{"home": "present", "sources": [\#(rows.joined(separator: ", "))], "next_after": \#(after)}"#])
    }

    @Test func theRouteIsAskedOnePageAtATime() {
        #expect(RepositoryCache.arguments(folder: "/tmp/support", after: nil)
            == ["/tmp/support", "--api", "/api/cache/sources?limit=100", "--format", "json"])
        #expect(RepositoryCache.arguments(folder: "/tmp/support", after: "github-com--o--r--0123")
            == ["/tmp/support", "--api", "/api/cache/sources?limit=100&after=github-com--o--r--0123", "--format", "json"])
        let spec = RepositoryCache.spec(folder: "/tmp/support", after: nil, with: setup, inherited: [:])
        #expect(spec.workingDirectory == "/tmp/support")
    }

    @Test func aPublishedSourceWithNoProblemsIsCached() {
        #expect(RepositoryCache.read(Self.page([("https://github.com/jlevy/tbd", "published", "[]")]), looking: repository) == .found)
        #expect(RepositoryCache.read(Self.page([("https://github.com/jlevy/tbd", "unattached", "[]")]), looking: repository) == .end)
        #expect(RepositoryCache.read(Self.page([("https://github.com/jlevy/tbd", "published", #"["damaged"]"#)]), looking: repository) == .end)
        #expect(RepositoryCache.read(Self.page([("git@github.com:jlevy/tbd.git", "published", "[]")]), looking: repository) == .end)
        #expect(RepositoryCache.read(Self.page([], next: "github-com--a--b--01"), looking: repository) == .next("github-com--a--b--01"))
        #expect(RepositoryCache.read(result(["Error: /api/cache/sources returned HTTP 409"], code: 1), looking: repository)
            == .unreadable("exit status 1: Error: /api/cache/sources returned HTTP 409"))
    }

    @Test func theLookUpReadsEveryPageAndAsksWhenItCannot() async {
        let pages = Recorder<LaunchSpec>()
        let found = await RepositoryCache.lookUp(repository, folder: "/tmp/support", with: setup, inherited: [:]) { spec, _ in
            pages.append(spec)
            return spec.arguments[2].contains("after=")
                ? Self.page([("https://github.com/jlevy/tbd", "published", "[]")]) : Self.page([], next: "github-com--a--b--01")
        }
        #expect(found == .cached)
        #expect(pages.all.count == 2)
        let absent = await RepositoryCache.lookUp(repository, folder: "/tmp", with: setup, inherited: [:]) { _, _ in Self.page([]) }
        #expect(absent == .notCached)
        let asked = Recorder<LaunchSpec>()
        let endless = await RepositoryCache.lookUp(repository, folder: "/tmp", with: setup, inherited: [:]) { spec, _ in
            asked.append(spec)
            return Self.page([], next: "github-com--x--\(asked.count)")
        }
        #expect(endless == .unknown("the cache lists more than 1000 sources"))
        let broken = await RepositoryCache.lookUp(repository, folder: "/tmp", with: setup, inherited: [:]) { _, _ in
            CommandResult(status: nil, output: [], launchError: "No such file or directory")
        }
        #expect(broken == .unknown("could not run: No such file or directory"))
    }
}
