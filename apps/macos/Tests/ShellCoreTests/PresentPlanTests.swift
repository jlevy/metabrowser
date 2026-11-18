import Darwin
import Foundation
import Testing
@testable import ShellCore

/// A wait status for `code`, as `ExitStatus` decodes one.
private func exited(_ code: Int32) -> Int32 { code << 8 }

private func result(_ output: [String], code: Int32 = 0) -> CommandResult {
    CommandResult(status: exited(code), output: output)
}

private func answer(_ json: String, code: Int32 = 0) -> PresentAnswer {
    PresentDryRun.answer(result(json.split(separator: "\n", omittingEmptySubsequences: false).map(String.init), code: code))
}

private let repository = URL(string: "https://github.com/jlevy/tbd")!

/// The answers `metab LINK --present --dry-run --json` gives, as the contract fixes them
/// (bead mb-d9tu), indented as `json.dumps(…, indent=2)` prints and in one line.
private nonisolated enum Fixture {
    static let pullRequest = """
        {
          "kind": "pull_request",
          "root": "https://github.com/jlevy/tbd",
          "page": "/pull/12",
          "refusal": null
        }
        """
    static let commit = #"{"kind": "commit", "root": "https://github.com/jlevy/tbd", "page": "/commit/0123abcd", "refusal": null}"#
    static let file = #"{"kind": "file", "root": "https://github.com/jlevy/tbd", "page": "/view/docs/a%20b.md#L10", "refusal": null}"#
    static let pulls = #"{"kind": "repository", "root": "https://github.com/jlevy/tbd", "page": "/pulls", "refusal": null}"#
    static let folder = #"{"kind": "folder", "root": "/tmp/account/notes", "page": "/view/", "refusal": null}"#
    static let refusal = """
        {
          "kind": null,
          "root": null,
          "page": null,
          "refusal": {
            "code": "unsupported_github_url",
            "message": "GitHub issues pages are not opened; open the repository at https://github.com/jlevy/tbd"
          }
        }
        """
    static let notSignedIn = #"{"kind": null, "root": null, "page": null, "refusal": {"code": "not_logged_in", "message": "gh is not signed in to github.com: run gh auth login --hostname github.com"}}"#
}

@Suite struct GitHubLinkTests {
    @Test(arguments: [
        "https://github.com/jlevy/tbd",
        "https://github.com/jlevy/tbd/pull/12/files",
        "https://www.github.com/jlevy/tbd/blob/main/README.md#L3",
        "https://raw.githubusercontent.com/jlevy/tbd/main/README.md",
        "HTTPS://GitHub.com/jlevy/tbd",
        // Refused by metab, which says why: the app reads only the scheme and the host.
        "https://github.com/jlevy/tbd/issues/4",
        "https://github.com/settings",
    ])
    func handsGitHubLinksToMetab(_ link: String) {
        #expect(GitHubLink.accepts(URL(string: link)!))
    }

    @Test(arguments: [
        "http://github.com/jlevy/tbd",
        "ssh://git@github.com/jlevy/tbd.git",
        "https://gitlab.com/jlevy/tbd",
        "https://github.com.example.net/jlevy/tbd",
        "https://gist.github.com/jlevy/abc",
        "metabrowser://open?path=/tmp",
        "mailto:someone@example.com",
    ])
    func refusesEverythingElse(_ link: String) {
        #expect(!GitHubLink.accepts(URL(string: link)!))
    }

    @Test func theDryRunIsTheContractsCommandRunInTheHomeFolder() {
        let link = URL(string: "https://github.com/jlevy/tbd/pull/12")!
        #expect(PresentDryRun.arguments(for: link) == [link.absoluteString, "--present", "--dry-run", "--json"])
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
    @Test func aPullRequestOpensAtItsPageInItsRepository() {
        #expect(answer(Fixture.pullRequest) == .plan(PresentPlan(
            kind: .pullRequest, root: .repository(repository), page: PageAddress(reference: "/pull/12"))))
    }

    @Test func everyRepositoryKindKeepsItsPage() {
        #expect(answer(Fixture.commit) == .plan(PresentPlan(
            kind: .commit, root: .repository(repository), page: PageAddress(reference: "/commit/0123abcd"))))
        #expect(answer(Fixture.file) == .plan(PresentPlan(
            kind: .file, root: .repository(repository), page: PageAddress(reference: "/view/docs/a%20b.md#L10"))))
        #expect(answer(Fixture.pulls) == .plan(PresentPlan(
            kind: .repository, root: .repository(repository), page: PageAddress(reference: "/pulls"))))
    }

    @Test func aLocalRootIsAPath() {
        #expect(answer(Fixture.folder) == .plan(PresentPlan(
            kind: .folder, root: .local("/tmp/account/notes"), page: PageAddress(reference: "/view/"))))
    }

    @Test func aNullPageIsTheEntryPage() {
        let json = #"{"kind": "repository", "root": "https://github.com/jlevy/tbd", "page": null, "refusal": null}"#
        #expect(answer(json) == .plan(PresentPlan(kind: .repository, root: .repository(repository), page: nil)))
    }

    @Test func aRefusalCarriesMetabsMessageWhole() {
        let expected = PresentRefusal(
            code: "unsupported_github_url",
            message: "GitHub issues pages are not opened; open the repository at https://github.com/jlevy/tbd")
        #expect(answer(Fixture.refusal, code: 2) == .refused(expected))
        let alert = answer(Fixture.refusal, code: 2).alert(
            link: URL(string: "https://github.com/jlevy/tbd/issues/4")!, metab: "metab 0.12.1 at /opt/metab")
        #expect(alert?.detail == expected.message + "\n\nhttps://github.com/jlevy/tbd/issues/4")
    }

    @Test func aSignInFailureNamesItsFix() {
        guard case .refused(let refusal) = answer(Fixture.notSignedIn, code: 4) else {
            Issue.record("expected a refusal")
            return
        }
        #expect(refusal.code == "not_logged_in")
        #expect(refusal.message.contains("gh auth login"))
    }

    /// stdout and stderr share the command's pipe, so a warning before or after the JSON
    /// must not hide the answer.
    @Test func linesOnStderrAroundTheAnswerArePassedOver() {
        let noisy = ["WARNING: ignoring METABROWSER_FOO in /tmp/account/.env"]
            + Fixture.pullRequest.split(separator: "\n").map(String.init) + ["a late line"]
        #expect(PresentDryRun.answer(result(noisy)) == answer(Fixture.pullRequest))
        let compact = ["{not json}", Fixture.commit, "done"]
        #expect(PresentDryRun.answer(result(compact)) == answer(Fixture.commit))
    }

    /// A `metab` from before `--present` exits 2 with click's usage error naming the flag.
    @Test func aMetabWithoutPresentIsUnsupported() {
        let clickUsageError = [
            "Usage: metab [OPTIONS] [ROOT]", "Try 'metab --help' for help.", "", "Error: No such option: --present",
        ]
        #expect(PresentDryRun.answer(result(clickUsageError, code: 2)) == .unsupported)
        let alert = PresentAnswer.unsupported.alert(link: repository, metab: "metab 0.12.1.dev3 at /opt/metab")
        #expect(alert?.detail.contains("metab 0.12.1.dev3 at /opt/metab has no --present") == true)
        // Another usage error, or the flag named on another exit, says nothing about the build.
        #expect(PresentDryRun.answer(result(["Error: No such option: --json"], code: 2)) != .unsupported)
        #expect(PresentDryRun.answer(result(["--present crashed"], code: 1)) != .unsupported)
    }

    @Test(arguments: [
        // Exit 0 must come with a plan.
        (#"{"kind": null, "root": null, "page": null, "refusal": null}"#, Int32(0)),
        // A plan must come with exit 0.
        (Fixture.commit, Int32(1)),
        (#"{"kind": "issue", "root": "https://github.com/jlevy/tbd", "page": "/view/", "refusal": null}"#, Int32(0)),
        (#"{"kind": "commit", "root": "relative/path", "page": "/view/", "refusal": null}"#, Int32(0)),
        (#"{"kind": "commit", "root": "https://github.com/jlevy/tbd/pull/12", "page": "/view/", "refusal": null}"#, Int32(0)),
        (#"{"kind": "commit", "root": "https://github.com/jlevy/tbd", "page": "https://evil.example/", "refusal": null}"#, Int32(0)),
        (#"{"kind": "commit", "root": "https://github.com/jlevy/tbd", "page": "//evil.example/", "refusal": null}"#, Int32(0)),
        (#"{"kind": 3, "root": "https://github.com/jlevy/tbd", "page": "/view/", "refusal": null}"#, Int32(0)),
        ("Traceback (most recent call last):", Int32(1)),
        ("", Int32(0)),
    ])
    func anythingElseIsUnreadable(_ json: String, _ code: Int32) {
        guard case .unreadable = answer(json, code: code) else {
            Issue.record("expected an unreadable answer for \(json)")
            return
        }
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
        let huge = Array(repeating: String(repeating: "x", count: 1000), count: 70) + [Fixture.commit]
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
