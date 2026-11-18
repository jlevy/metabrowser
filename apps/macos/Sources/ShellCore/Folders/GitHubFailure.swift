import Foundation

/// Why a repository's server did not start, when GitHub, or the way to it, is the reason:
/// what the status view says, the commands that fix it, and what Copy Message copies.
///
/// `metab` ends a start that fails with one line, `Error: MESSAGE`, and a message about
/// reaching or reading a source names its state in parentheses, as `describe_remote_failure`
/// in `src/metabrowser/cache/origin.py` writes it for a clone:
///
///     Error: https://github.com/owner/repo was not found, or it is private and could not be read (not_found_or_private); if it is private, sign in with gh auth login to an account that can read it; nothing was published
///
/// and as the GitHub plugin writes a `GhFailureState` (`builtin_plugins/github/gh.py`).
/// The app reads the state and nothing else of the message, which it shows as written.
/// `tests/test_macos_app_pins.py` holds the states in `kinds` to `metab`'s, and the
/// sample lines in `GitHubFailureTests` to what `metab` prints.
///
/// GitHub answers alike for a repository that does not exist and for a private one the
/// credential cannot read, so a clone cannot tell a missing repository from a `gh` that is
/// signed out, signed in to another account, or signed in without the `repo` scope:
/// `notFound` covers all four, and its steps show which it is.
public nonisolated struct GitHubFailure: Equatable, Sendable {
    public enum Kind: Equatable, Sendable {
        /// GitHub CLI is not signed in to github.com (`not_logged_in`).
        case notSignedIn
        /// `metab` found no GitHub CLI, so it can read only public repositories
        /// (`gh_missing`, or `not_found_or_private` with the hint to install it).
        case noGitHubCLI
        /// The repository does not exist, or the account GitHub CLI uses cannot read it
        /// (`not_found_or_private`).
        case notFound
        /// GitHub could not be reached, or did not finish answering (the connection's
        /// states, and `rate_limited`).
        case network
    }

    /// One command that helps, and what it does.
    public struct Step: Equatable, Sendable {
        public var purpose: String
        public var command: String
    }

    public var kind: Kind
    /// The state `metab` named, such as `not_found_or_private`.
    public var state: String
    /// `metab`'s message: its `Error:` line without the prefix.
    public var message: String
    /// The repository's canonical URL, `https://github.com/<owner>/<repo>`.
    public var repository: URL

    /// The states that make a failure GitHub's. Every other state, and a failure with
    /// none, such as `too_large` or a crash, shows the server's output and Retry.
    static let kinds: [String: Kind] = [
        "not_logged_in": .notSignedIn,
        "gh_missing": .noGitHubCLI,
        "not_found_or_private": .notFound,
        "network_unreachable": .network,
        "connection_interrupted": .network,
        "tls_failed": .network,
        "timed_out": .network,
        "server_error": .network,
        "proxy_auth_required": .network,
        "rate_limited": .network,
        "network_error": .network,
    ]

    /// What `metab` adds to `not_found_or_private` when it found no `gh` to ask for a
    /// credential (`GithubProvider.credential_hint`).
    static let installHint = "install GitHub CLI (gh)"
    static let errorPrefix = "Error: "

    /// The failure that ends `output`, the server's newest lines, when it is GitHub's.
    ///
    /// Only the last line counts: `metab` writes its `Error:` line as it exits, and nothing
    /// after it. A line from earlier in the run, such as a refresh that failed while the
    /// server served, is not why the server stopped.
    public static func diagnose(_ output: [String], repository: URL) -> GitHubFailure? {
        guard let last = output.last, last.hasPrefix(errorPrefix) else { return nil }
        let message = String(last.dropFirst(errorPrefix.count))
        guard let state = state(in: message), var kind = kinds[state] else { return nil }
        if kind == .notFound, message.contains(installHint) { kind = .noGitHubCLI }
        return GitHubFailure(kind: kind, state: state, message: message, repository: repository)
    }

    /// The first `(state)` in `message` that ends a clause, before `;` or at the end.
    static func state(in message: String) -> String? {
        var rest = Substring(message)
        while let open = rest.firstIndex(of: "(") {
            let after = rest[rest.index(after: open)...]
            guard let close = after.firstIndex(of: ")") else { return nil }
            let name = after[..<close]
            let next = after[after.index(after: close)...]
            if !name.isEmpty, name.allSatisfy({ $0.isLowercase || $0 == "_" }),
               next.isEmpty || next.hasPrefix(";") {
                return String(name)
            }
            rest = next
        }
        return nil
    }

    /// What went wrong, in a line.
    public var headline: String {
        switch kind {
        case .notSignedIn: "GitHub CLI is not signed in"
        case .noGitHubCLI: "Metabrowser did not find GitHub CLI"
        case .notFound: "Not found, or this account cannot read it"
        case .network: "The connection to GitHub failed"
        }
    }

    /// What to do about it.
    public var explanation: String {
        switch kind {
        case .notSignedIn:
            "Metabrowser clones and reads repositories with your GitHub CLI (gh) sign-in. Sign in in Terminal."
        case .noGitHubCLI:
            "Without GitHub CLI (gh), Metabrowser reads only public repositories. Install it from https://cli.github.com and sign in, then choose Find Again in Runtime Settings so that Metabrowser finds it."
        case .notFound:
            "GitHub answers the same way for a repository that does not exist and for a private one it will not show: GitHub CLI is not signed in, its account cannot read the repository, or its sign-in lacks the repo scope."
        case .network:
            "Check the network connection. Trying the same clone in Terminal shows whether this Mac reaches GitHub, and Retry then opens what it cloned."
        }
    }

    /// Said under every GitHub failure: what happens when the user comes back.
    public static let recheckNote = "Metabrowser tries again when you switch back to it."

    /// The commands that fix it, or show what is wrong, in the order to run them.
    public var steps: [Step] {
        let signIn = Step(purpose: "Sign in to GitHub:", command: "gh auth login --hostname github.com")
        switch kind {
        case .notSignedIn:
            return [signIn]
        case .noGitHubCLI:
            return [Step(purpose: "Once GitHub CLI is installed, sign in to GitHub:", command: signIn.command)]
        case .notFound:
            return [
                Step(
                    purpose: "See which account GitHub CLI uses, and its scopes:",
                    command: "gh auth status --hostname github.com"),
                Step(purpose: "Sign in to an account that can read the repository:", command: signIn.command),
                Step(
                    purpose: "Or add the repo scope to the account signed in:",
                    command: "gh auth refresh --hostname github.com --scopes repo"),
            ]
        case .network:
            let root = LaunchSpec.quoted(repository.absoluteString)
            return [Step(purpose: "Try the same clone in Terminal:", command: "metab \(root) --no-serve")]
        }
    }

    /// What Copy Message copies: the failure, `metab`'s message, and the steps, as text to
    /// paste into a message or a note. `location` names the repository, as the window does.
    public func copiedText(location: String) -> String {
        var lines = ["Metabrowser could not open \(location): \(headline).", message, ""]
        for step in steps {
            lines.append(step.purpose)
            lines.append(step.command)
        }
        return lines.joined(separator: "\n")
    }
}

extension ServerFailure {
    /// This failure of a repository's server, with `gitHub` set when GitHub is why
    /// (`GitHubFailure.diagnose`).
    public func diagnosingGitHub(repository: URL) -> ServerFailure {
        var failure = self
        failure.gitHub = GitHubFailure.diagnose(recentOutput, repository: repository)
        return failure
    }

    /// Whether the app starts the server again when it becomes active: only when GitHub is
    /// why it failed, since the fix, such as a sign-in in Terminal, happens in another app.
    /// Any other failure waits for Retry, as nothing outside the app is likely to have
    /// changed it.
    public var rechecksOnActivation: Bool { gitHub != nil }
}
