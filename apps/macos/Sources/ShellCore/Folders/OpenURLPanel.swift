import Foundation

/// What File > Open URL… takes: a full GitHub URL, which the panel hands to `metab` only
/// once `GitHubLink` accepts it, the check every link sent to the app passes first.
///
/// `metab TARGET --present --dry-run` reads a target with no scheme as a local path, so
/// `owner/repo` or `github.com/owner/repo` would name a folder under its working
/// directory: the panel takes no shorthand, and says so. Every other problem here is one
/// `metab` would refuse as well (`insecure_http`, `credentials_in_url`,
/// `unsupported_source`); the panel says it first, in its own words, since `metab`'s
/// answer for another site is about the command line's `--present`.
public nonisolated enum OpenURLEntry {
    public enum Problem: Error, Equatable, Sendable {
        /// Nothing but white space.
        case empty
        /// Longer than `GitHubLink.maximumLength`.
        case tooLong
        /// No scheme: a shorthand such as `owner/repo`, or a URL without `https://`.
        case notAFullURL
        /// A scheme other than `https`.
        case notHTTPS
        /// A user name or a password before the host.
        case credentials
        /// A port, other than 443, after the host.
        case port
        /// A host other than GitHub's.
        case notGitHub
        /// Not a URL the app takes in any other way, such as one holding a space.
        case notAURL

        /// What the panel says under the field.
        public var message: String {
            switch self {
            case .empty:
                "Enter a GitHub URL."
            case .tooLong:
                "This URL is longer than Metabrowser opens."
            case .notAFullURL:
                "Enter the full URL, starting with https://github.com/: a repository, a pull request, a commit, or a file or folder."
            case .notHTTPS:
                "Metabrowser opens only https URLs, such as https://github.com/owner/repo."
            case .credentials:
                "This URL has a user name or password in it. Remove it, and the @ after it."
            case .port:
                "This URL names a port. Remove it: Metabrowser opens GitHub on its usual port."
            case .notGitHub:
                "Metabrowser opens only GitHub URLs: a repository, a pull request, a commit, or a file or folder on github.com."
            case .notAURL:
                "This is not a URL Metabrowser can open. Check for a space or another character a URL cannot hold."
            }
        }
    }

    /// `text` without the white space around it, as a paste brings it.
    public static func trimmed(_ text: String) -> String {
        text.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// The link `text` names, if `GitHubLink` accepts it, else why not. The text is read as
    /// typed: Foundation encodes nothing in it, so the link `metab` is given is the text.
    public static func link(_ text: String) -> Result<URL, Problem> {
        let text = trimmed(text)
        if text.isEmpty { return .failure(.empty) }
        if text.utf8.count > GitHubLink.maximumLength { return .failure(.tooLong) }
        guard let scheme = text.firstMatch(of: schemePattern)?.output.1 else { return .failure(.notAFullURL) }
        guard scheme.lowercased() == "https" else { return .failure(.notHTTPS) }
        let authority = text.dropFirst(scheme.count + 3).prefix { !"/?#".contains($0) }
        if authority.contains("@") { return .failure(.credentials) }
        var host = authority
        // A bracketed host is an address, whose colons are its own; it is not GitHub's.
        if !authority.hasPrefix("["), let colon = authority.lastIndex(of: ":") {
            if authority[authority.index(after: colon)...] != "443" { return .failure(.port) }
            host = authority[..<colon]
        }
        guard GitHubLink.hosts.contains(host.lowercased()) else { return .failure(.notGitHub) }
        guard let url = URL(string: text, encodingInvalidCharacters: false), GitHubLink.accepts(url) else {
            return .failure(.notAURL)
        }
        return .success(url)
    }

    /// A scheme, as RFC 3986 spells one, and `://`.
    nonisolated(unsafe) private static let schemePattern = #/^([A-Za-z][A-Za-z0-9+.-]*):\/\//#
}

/// File > Open URL…: one field for a GitHub URL, and what pressing Open, editing, and
/// Cancel do (`OpenURLWindowController` shows it).
///
/// Open checks the text (`OpenURLEntry`) and asks `metab` about the link with the command
/// every link sent to the app is resolved with, `metab LINK --present --dry-run --format
/// json` (`PresentDryRun`). A plan closes the panel, and the app opens it as it opens such
/// a link (`AppDelegate.open(_:with:)`): in the repository's mirror, always, never a
/// checkout of it, as The File Menu in `docs/project/architecture/arch-open-modes.md`
/// designs it. A problem with the text, a refusal, or an answer the app cannot read is
/// said under the field, and the panel stays open so the text can be fixed. An edit
/// while `metab` is asked drops its answer, and so does Cancel.
public nonisolated struct OpenURLPanel: Equatable, Sendable {
    public enum Phase: Equatable, Sendable {
        /// The field takes text, and Open checks it.
        case editing
        /// `metab` is asked about this link.
        case checking(URL)
        /// It opened a plan, handed its link on, or was cancelled: nothing more happens.
        case closed
    }

    public private(set) var text = ""
    public private(set) var phase = Phase.editing
    /// Why the text was not opened, said under the field until the next edit.
    public private(set) var message: String?

    public init() {}

    /// Whether Open does anything: some text, and no answer awaited.
    public var canOpen: Bool { phase == .editing && !OpenURLEntry.trimmed(text).isEmpty }

    public var isChecking: Bool {
        if case .checking = phase { return true }
        return false
    }

    /// The field now holds `newText`. Any message goes, and an answer awaited is dropped.
    public mutating func edit(_ newText: String) {
        guard phase != .closed, newText != text else { return }
        text = newText
        message = nil
        phase = .editing
    }

    /// Open was pressed: the link to ask `metab` about, which the panel now awaits, or nil,
    /// with `message` saying why the text is not one.
    public mutating func open() -> URL? {
        guard canOpen else { return nil }
        switch OpenURLEntry.link(text) {
        case .success(let link):
            phase = .checking(link)
            message = nil
            return link
        case .failure(let problem):
            message = problem.message
            return nil
        }
    }

    /// `metab` answered about `link`: the plan to open, which closes the panel, or nil.
    /// A refusal or an unreadable answer is said under the field; an answer the panel no
    /// longer awaits changes nothing. `metab` names the `metab` that answered.
    public mutating func answered(_ answer: PresentAnswer, for link: URL, metab: String) -> PresentPlan? {
        guard phase == .checking(link) else { return nil }
        switch answer {
        case .plan(let plan):
            phase = .closed
            return plan
        case .refused(let refusal):
            message = GitHubLink.shortened(refusal.message, to: PresentAnswer.shownLineLength)
        case .unreadable(let reason, _):
            // The output stays in the app's log: it can hold a traceback.
            message = "Metabrowser could not check this URL: \(metab) \(GitHubLink.shortened(reason, to: PresentAnswer.shownLineLength))."
        }
        phase = .editing
        return nil
    }

    /// The link being checked goes to the link queue instead, as when no `metab` can run
    /// now, which closes the panel: the queue waits for one, as it does for a link sent to
    /// the app.
    public mutating func handOff() -> URL? {
        guard case .checking(let link) = phase else { return nil }
        phase = .closed
        return link
    }

    public mutating func cancel() {
        phase = .closed
    }
}
