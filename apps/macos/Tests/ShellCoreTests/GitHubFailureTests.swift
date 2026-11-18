import Foundation
import Testing
@testable import ShellCore

/// The lines `metab` ends a failed start with. `tests/test_macos_app_pins.py` builds each
/// message with `metab`'s own code and expects it here, word for word, and reads samples
/// only from this enum.
enum GitHubFailureSamples {
    /// `gh` was found, so Git asked it for a credential, and GitHub showed no repository.
    static let notFound =
        "Error: https://github.com/octo/absent was not found, or it is private and could not be read (not_found_or_private); if it is private, sign in with gh auth login to an account that can read it; nothing was published"
    /// No `gh` was found, so Git had no credential to offer.
    static let notFoundWithoutGh =
        "Error: https://github.com/octo/absent was not found, or it is private and could not be read (not_found_or_private); if it is private, install GitHub CLI (gh) and sign in with gh auth login; nothing was published"
    static let unreachable =
        "Error: https://github.com/octo/demo could not be reached; check the network connection (network_unreachable); nothing was published"
    static let rateLimited =
        "Error: https://github.com/octo/demo is limiting the rate of requests; try again later (rate_limited); nothing was published"
    static let serverError =
        "Error: https://github.com/octo/demo answered with a server error; try again later (server_error); nothing was published"
    /// A clone that stalled, which can happen minutes into its fetch.
    static let timedOut =
        "Error: https://github.com/octo/demo stopped answering in time (timed_out); nothing was published"
    /// Placeholders for the GitHub plugin's states, which no start ends with today: its
    /// messages (`GhError`) name no state, and none reaches a start's `Error:` line. The pin
    /// builds these from the plugin's messages with the state appended, a format `metab`
    /// does not print; the GitHub status check (`mb-si2g`) decides the real one.
    static let notSignedIn =
        "Error: GitHub CLI is not signed in to github.com. Run gh auth login --hostname github.com, then retry. (not_logged_in)"
    static let ghMissing =
        "Error: Metabrowser could not find GitHub CLI (gh). Install it from https://cli.github.com/, then run gh auth login --hostname github.com. (gh_missing)"
}

private let repository = URL(string: "https://github.com/octo/absent")!

@Suite struct GitHubFailureTests {
    private func diagnosed(_ line: String) -> GitHubFailure? {
        GitHubFailure.diagnose(["cloning https://github.com/octo/absent into ~/.cache/metabrowser", line], repository: repository)
    }

    @Test func eachStateMetabNamesIsAKind() {
        #expect(diagnosed(GitHubFailureSamples.notFound)?.kind == .notFound)
        #expect(diagnosed(GitHubFailureSamples.notFoundWithoutGh)?.kind == .notFoundWithoutGitHubCLI)
        #expect(diagnosed(GitHubFailureSamples.unreachable)?.kind == .network)
        #expect(diagnosed(GitHubFailureSamples.timedOut)?.kind == .network)
        #expect(diagnosed(GitHubFailureSamples.rateLimited)?.kind == .rateLimited)
        #expect(diagnosed(GitHubFailureSamples.serverError)?.kind == .serverError)
        #expect(diagnosed(GitHubFailureSamples.notSignedIn)?.kind == .notSignedIn)
        #expect(diagnosed(GitHubFailureSamples.ghMissing)?.kind == .noGitHubCLI)
    }

    /// `(gh)` in the middle of a sentence is no state: a state ends its clause.
    @Test func theStateIsTheOneThatEndsAClause() {
        #expect(diagnosed(GitHubFailureSamples.ghMissing)?.state == "gh_missing")
        #expect(diagnosed(GitHubFailureSamples.notFoundWithoutGh)?.state == "not_found_or_private")
        #expect(GitHubFailure.state(in: "a (b) c") == nil)
        #expect(GitHubFailure.state(in: "a (Not_A_State); b") == nil)
        #expect(GitHubFailure.state(in: "a (unclosed") == nil)
        #expect(GitHubFailure.state(in: "a () (timed_out)") == "timed_out")
    }

    @Test func theMessageIsMetabsLineWithoutItsPrefix() throws {
        let failure = try #require(diagnosed(GitHubFailureSamples.notFound))
        #expect(failure.message == String(GitHubFailureSamples.notFound.dropFirst("Error: ".count)))
        #expect(failure.repository == repository)
    }

    @Test func otherFailuresAreNotGitHubs() {
        for line in [
            "Error: https://github.com/octo/demo is over the size limit for a first clone (too_large); GitHub reports 2,000,000 KB; nothing was published",
            "Error: the source could not be read as a Git repository; nothing was published",
            "Error: ROOT does not exist",
            "Traceback (most recent call last):",
            "https://github.com/octo/demo could not be reached (network_unreachable); nothing was published",
        ] {
            #expect(diagnosed(line) == nil, "\(line)")
        }
        #expect(GitHubFailure.diagnose([], repository: repository) == nil)
    }

    /// Only the line `metab` exits with: an earlier one is not why the server stopped.
    @Test func onlyTheLastLineCounts() {
        let output = [GitHubFailureSamples.unreachable, "INFO: the server went on, then crashed"]
        #expect(GitHubFailure.diagnose(output, repository: repository) == nil)
    }

    @Test func eachKindNamesTheCommandsThatFixIt() throws {
        let commands = { (line: String) in self.diagnosed(line)?.steps.map(\.command) ?? [] }
        #expect(commands(GitHubFailureSamples.notSignedIn) == ["gh auth login --hostname github.com"])
        #expect(commands(GitHubFailureSamples.ghMissing) == ["gh auth login --hostname github.com"])
        #expect(commands(GitHubFailureSamples.notFound) == [
            "gh auth status --hostname github.com",
            "gh auth login --hostname github.com",
            "gh auth refresh --hostname github.com --scopes repo",
        ])
        #expect(commands(GitHubFailureSamples.notFoundWithoutGh) == ["gh auth login --hostname github.com"])
        #expect(commands(GitHubFailureSamples.unreachable) == ["metab https://github.com/octo/absent --no-serve"])
        #expect(commands(GitHubFailureSamples.rateLimited) == [])
        #expect(commands(GitHubFailureSamples.serverError) == [])
        for line in [
            GitHubFailureSamples.notFound, GitHubFailureSamples.notFoundWithoutGh, GitHubFailureSamples.unreachable,
            GitHubFailureSamples.rateLimited, GitHubFailureSamples.serverError, GitHubFailureSamples.ghMissing,
        ] {
            let failure = try #require(diagnosed(line))
            #expect(!failure.headline.isEmpty && !failure.explanation.isEmpty)
            #expect(failure.steps.allSatisfy { $0.purpose.hasSuffix(":") })
        }
    }

    /// GitHub answered a rate-limited or failed request, so the window does not send the
    /// user to their network; and a not-found without `gh` says both possible causes.
    @Test func theHeadlineSaysWhatIsKnown() throws {
        let headline = { (line: String) in try #require(self.diagnosed(line)).headline }
        #expect(try headline(GitHubFailureSamples.rateLimited) == "GitHub is limiting the rate of requests")
        #expect(try headline(GitHubFailureSamples.serverError) == "GitHub answered with an error")
        for line in [GitHubFailureSamples.rateLimited, GitHubFailureSamples.serverError] {
            let failure = try #require(diagnosed(line))
            #expect(!failure.explanation.contains("network") && failure.explanation.contains("Retry"))
        }
        #expect(try headline(GitHubFailureSamples.notFoundWithoutGh)
            == "Not found, or private, and Metabrowser did not find GitHub CLI")
    }

    @Test func copyMessageCopiesTheFailureMetabsMessageAndTheCommands() throws {
        let failure = try #require(diagnosed(GitHubFailureSamples.notSignedIn))
        #expect(failure.copiedText(location: "github.com/octo/absent") == """
            Metabrowser could not open github.com/octo/absent: GitHub CLI is not signed in.
            GitHub CLI is not signed in to github.com. Run gh auth login --hostname github.com, then retry. (not_logged_in)

            Sign in to GitHub:
            gh auth login --hostname github.com
            """)
        let waiting = try #require(diagnosed(GitHubFailureSamples.rateLimited))
        #expect(waiting.copiedText(location: "github.com/octo/demo") == """
            Metabrowser could not open github.com/octo/demo: GitHub is limiting the rate of requests.
            https://github.com/octo/demo is limiting the rate of requests; try again later (rate_limited); nothing was published
            """)
    }

    /// Only a failure a sign-in in Terminal can fix starts again when the app becomes
    /// active: a network failure can be minutes into a clone, which a retry fetches from
    /// zero; a rate limit asks for fewer requests; and without `gh` nothing changes until
    /// Find Again.
    @Test func onlyWhatASignInFixesRechecksOnActivation() {
        #expect(GitHubFailure.Kind.allCases.filter(\.rechecksOnActivation) == [.notSignedIn, .notFound])
        let rechecks = { (line: String) in self.diagnosed(line)?.rechecksOnActivation }
        #expect(rechecks(GitHubFailureSamples.notFound) == true)
        #expect(rechecks(GitHubFailureSamples.notSignedIn) == true)
        for line in [
            GitHubFailureSamples.notFoundWithoutGh, GitHubFailureSamples.ghMissing, GitHubFailureSamples.unreachable,
            GitHubFailureSamples.timedOut, GitHubFailureSamples.rateLimited, GitHubFailureSamples.serverError,
        ] {
            #expect(rechecks(line) == false, "\(line)")
            let failed = ServerFailure(summary: "exit status 1", recentOutput: [line])
            #expect(!failed.diagnosingGitHub(repository: repository).rechecksOnActivation, "\(line)")
        }
    }

    /// Only a failure GitHub caused can start again when the app becomes active.
    @Test func onlyAGitHubFailureRechecksOnActivation() {
        let output = ["cloning https://github.com/octo/absent into ~/.cache/metabrowser", GitHubFailureSamples.notFound]
        let failed = ServerFailure(summary: "The server exited before it was ready (exit status 1).", recentOutput: output)
        #expect(!failed.rechecksOnActivation)
        let diagnosed = failed.diagnosingGitHub(repository: repository)
        #expect(diagnosed.gitHub?.kind == .notFound)
        #expect(diagnosed.rechecksOnActivation)
        #expect(diagnosed.summary == failed.summary && diagnosed.recentOutput == output)
        let crashed = ServerFailure(summary: "The server stopped unexpectedly (signal 9).", recentOutput: ["INFO: serving"])
        #expect(!crashed.diagnosingGitHub(repository: repository).rechecksOnActivation)
    }
}
