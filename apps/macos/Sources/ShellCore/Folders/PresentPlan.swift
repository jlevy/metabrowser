import Foundation

/// The links the app hands to `metab` to resolve: an `https` URL on a host that `metab`'s
/// GitHub reducer claims, `_WEB_HOSTS` and `_RAW_HOST` in
/// `src/metabrowser/builtin_plugins/github/urls.py`, which `tests/test_macos_app_pins.py`
/// pins.
///
/// A link is untrusted input: any local process can send one with `open -b`. Whether
/// `metab` opens one, and what it selects, is `metab`'s to say (`PresentDryRun`), so the
/// app reads nothing else of the link. What it does check, it checks on the string it
/// passes, not on Foundation's decoded host, so an encoded or bracketed host, a port, or
/// a user name cannot pass the check under one spelling and run under another.
public nonisolated enum GitHubLink {
    public static let hosts: Set<String> = ["github.com", "www.github.com", "raw.githubusercontent.com"]
    /// The longest link the app resolves, in bytes. Not measured: it bounds what a sender
    /// can make the app pass to `metab` and show in an alert, not a cost. A GitHub link to
    /// a deeply nested file is a few hundred bytes.
    public static let maximumLength = 8 * 1024
    /// How much of a link an alert shows: its start and its end, around an ellipsis.
    static let shownLength = 200

    public static func accepts(_ url: URL) -> Bool {
        let text = url.absoluteString
        guard text.utf8.count <= maximumLength, url.user == nil, url.password == nil,
              let match = text.firstMatch(of: prefix)
        else { return false }
        return hosts.contains(match.output.1.lowercased())
    }

    /// `https://`, a host of letters, digits, dots, and hyphens, no port but 443, and then
    /// the path, the query, the fragment, or the end, in any letter case. A user name, a
    /// percent-encoded or bracketed host, and any other port end the host early, so the
    /// host read here is never one Foundation decoded.
    nonisolated(unsafe) private static let prefix =
        #/^https://([A-Za-z0-9.-]+)(?::443)?(?:[/?#]|$)/#.ignoresCase()

    /// `link` for an alert: without a user name, a password, a query, or a fragment, any
    /// of which can carry a token onto a shared screen (a raw file's `?token=`), and whole
    /// up to `shownLength` characters, else its start and end. A query or fragment left
    /// out shows as `?…` or `#…`.
    public static func shown(_ link: URL) -> String {
        guard var parts = URLComponents(url: link, resolvingAgainstBaseURL: false) else { return "(a link that cannot be shown)" }
        let elided = parts.percentEncodedQuery != nil ? "?…" : parts.percentEncodedFragment != nil ? "#…" : ""
        parts.user = nil
        parts.password = nil
        parts.percentEncodedQuery = nil
        parts.percentEncodedFragment = nil
        guard let text = parts.string else { return "(a link that cannot be shown)" }
        return Self.shortened(text + elided, to: shownLength)
    }

    /// `text` cut to at most `limit` characters, keeping its start and its end.
    static func shortened(_ text: String, to limit: Int) -> String {
        guard text.count > limit else { return text }
        let half = (limit - 1) / 2
        return String(text.prefix(half)) + "…" + String(text.suffix(limit - 1 - half))
    }
}

/// What `metab LINK --present --dry-run --format json` resolved a link to: the repository
/// to serve, and the canonical link to serve it with. Resolving clones and fetches nothing.
///
///     {"kind": "pull_request", "root": "https://github.com/jlevy/tbd", "page": "/pull/12",
///      "handoff": ["https://github.com/jlevy/tbd/pull/12"], "refusal": null}
///
/// `root` is the repository's canonical URL, which keys its session (`SessionRoot`).
/// `handoff` is the link as `metab` rebuilds it from what its reducer kept, with no
/// credentials, query, or tracking: it is what the server is started with, so what a
/// sender put in the link beyond what `metab` reads never reaches the server's arguments
/// or its log. The dry run itself is given the link as sent, so the process table shows
/// it for the dry run's lifetime, about a third of a second and at most
/// `PresentDryRun.timeout`. `page` is not read: a repository's server resolves the
/// link against its mirror and announces the page itself, which a dry run cannot always
/// know (it is null where a ref may hold a `/`), so a window shows the server's entry page.
public nonisolated struct PresentPlan: Equatable, Sendable {
    /// The kinds a GitHub link resolves to. `folder` is a local kind, which no link gives.
    public enum Kind: String, CaseIterable, Equatable, Sendable {
        case repository
        case pullRequest = "pull_request"
        case commit
        case tree
        case file
    }

    public var kind: Kind
    /// The repository's canonical URL, `https://github.com/<owner>/<repo>`.
    public var repository: URL
    /// What the repository's server is started with (`handoff`).
    public var link: URL

    public init(kind: Kind, repository: URL, link: URL) {
        self.kind = kind
        self.repository = repository
        self.link = link
    }

    /// `text` as a URL if it is a canonical repository URL: `https://github.com/`, an owner
    /// and a repository name in the characters GitHub allows them (`OWNER` and `REPOSITORY`
    /// in `urls.py`), and nothing else.
    public static func repositoryURL(_ text: String) -> URL? {
        guard let match = text.wholeMatch(of: repositoryPattern), !["." , ".."].contains(match.output.2) else {
            return nil
        }
        return URL(string: text)
    }

    nonisolated(unsafe) private static let repositoryPattern =
        #/https://github\.com/([A-Za-z0-9-]{1,39})/([A-Za-z0-9._-]{1,100})/#

    /// `text` as the link a plan's server is started with: a link the app would accept
    /// itself, on `github.com`, that is `repository` or a page under it.
    static func handoffURL(_ text: String, in repository: URL) -> URL? {
        let root = repository.absoluteString
        guard text == root || text.hasPrefix(root + "/"), let url = URL(string: text), url.absoluteString == text,
              GitHubLink.accepts(url), url.host(percentEncoded: true) == "github.com"
        else { return nil }
        return url
    }
}

/// Why `metab` will not open a target, in its words, which name the step that fixes it.
public nonisolated struct PresentRefusal: Codable, Equatable, Sendable {
    public var code: String
    public var message: String

    public init(code: String, message: String) {
        self.code = code
        self.message = message
    }
}

/// What the app says about a link it does not open: one alert's title and text.
public nonisolated struct LinkAlert: Equatable, Sendable {
    /// Which links an alert is about, which the alert for a burst counts (`LinkProblems`,
    /// review D3 on #539).
    public enum Links: Equatable, Sendable {
        /// Links that were not opened: one refused, unreadable, or not a GitHub link, or
        /// those a decline turned away.
        case notOpened(Int)
        /// A link that opened, on another revision than it names (`selectionMissing`).
        case openedElsewhere
    }

    public var message: String
    public var detail: String
    public var links: Links

    public init(message: String, detail: String, links: Links = .notOpened(1)) {
        self.message = message
        self.detail = detail
        self.links = links
    }

    /// How many links one combined alert describes; the rest are counted.
    static let shownInBatch = 5

    /// What the app says when the user declined to clone `name` and `count` more links
    /// into it, waiting with its question or sent before the burst ended, were not opened
    /// (`CloneQuestions`).
    public static func declined(_ name: String, count: Int) -> LinkAlert {
        LinkAlert(
            message: "Metabrowser did not clone \(name)",
            detail: "\(count) more \(count == 1 ? "link" : "links") into \(name) \(count == 1 ? "was" : "were") not opened, since you declined to clone it. Sending a link to it again asks again.",
            links: .notOpened(count))
    }
}

/// What the links since the last alert could not open, said in one alert once the burst
/// has ended, so a burst raises one modal, not one per link. It keeps the first
/// `LinkAlert.shownInBatch` problems and counts the rest, so links that keep arriving
/// keep no list that grows with them (review C9 on #539).
public nonisolated struct LinkProblems: Equatable, Sendable {
    /// Why links were turned away before `metab` resolved them.
    public enum Turnaway: CaseIterable, Equatable, Hashable, Sendable {
        /// `LinkQueue.limit` links waited to be resolved.
        case queueFull
        /// `LinkQueue.limit` links waited for a `metab` the app can run
        /// (`RuntimeSelection.setupForOpening`).
        case runtimeWaitFull
        /// `CloneQuestions.limit` repositories waited for the cache or a question.
        case questionsFull

        var reason: String {
            switch self {
            case .queueFull: "Metabrowser resolves one link at a time and keeps \(LinkQueue.limit) waiting"
            case .runtimeWaitFull: "Metabrowser keeps \(LinkQueue.limit) links waiting for a metab it can run"
            case .questionsFull: "Metabrowser asks about \(CloneQuestions.limit) repositories it has no copy of at a time"
            }
        }
    }

    public private(set) var shown: [LinkAlert] = []
    /// Problems past `shown`, counted.
    public private(set) var more = 0
    /// Links never resolved, by why.
    public private(set) var turnedAway: [Turnaway: Int] = [:]
    /// The links the problems noted stand for, shown or not (`LinkAlert.links`): a decline
    /// stands for every link it turned away, and a link that opened on another revision
    /// is no link that was not opened (review D3 on #539).
    private var notOpened = 0
    private var openedElsewhere = 0

    public init() {}

    public var isEmpty: Bool { shown.isEmpty && turnedAway.isEmpty }

    public mutating func note(_ alert: LinkAlert) {
        if shown.count < LinkAlert.shownInBatch { shown.append(alert) } else { more += 1 }
        switch alert.links {
        case .notOpened(let count): notOpened += count
        case .openedElsewhere: openedElsewhere += 1
        }
    }

    public mutating func noteTurnedAway(_ count: Int, _ why: Turnaway) {
        guard count > 0 else { return }
        turnedAway[why, default: 0] += count
    }

    /// The one alert for everything noted, which empties it; nil for nothing.
    public mutating func take() -> LinkAlert? {
        defer { self = LinkProblems() }
        let dropped = turnedAway.values.reduce(0, +)
        if shown.count == 1, more == 0, dropped == 0 { return shown[0] }
        guard !isEmpty else { return nil }
        var detail = Turnaway.allCases.compactMap { why in
            turnedAway[why].map { "\($0) more \($0 == 1 ? "link was" : "links were") not opened: \(why.reason)." }
        }
        detail += shown.map { "\($0.message): \($0.detail)" }
        if more > 0 { detail.append("and \(more) more.") }
        let unopened = notOpened + dropped
        return LinkAlert(
            message: Self.title(notOpened: unopened, openedElsewhere: openedElsewhere),
            detail: detail.joined(separator: "\n\n"), links: .notOpened(unopened))
    }

    /// A burst's title, which counts links, not the problems listed: `notOpened` links
    /// not opened, and `openedElsewhere` that opened on another revision than they name.
    static func title(notOpened: Int, openedElsewhere: Int) -> String {
        let links = { (count: Int) in "\(count) \(count == 1 ? "link" : "links")" }
        let named = { (count: Int) in count == 1 ? "names" : "name" }
        switch (notOpened, openedElsewhere) {
        case (_, 0):
            return "Metabrowser could not open \(links(notOpened))"
        case (0, _):
            return "Metabrowser could not show what \(links(openedElsewhere)) \(named(openedElsewhere))"
        default:
            return "Metabrowser could not open \(links(notOpened)), or show what \(openedElsewhere) more \(named(openedElsewhere))"
        }
    }
}

/// How `metab LINK --present --dry-run --format json` answered.
public nonisolated enum PresentAnswer: Equatable, Sendable {
    case plan(PresentPlan)
    case refused(PresentRefusal)
    /// It could not run, did not finish, or printed nothing this app reads as an answer.
    case unreadable(reason: String, output: [String])

    /// The most of a refusal's message, or of one output line, an alert shows. `metab`'s
    /// messages are one line of well under this.
    static let shownLineLength = 300

    /// What the app says about `link` when it does not open it, or nil for a plan.
    /// `metab` names the `metab` that answered.
    public func alert(link: URL, metab: String) -> LinkAlert? {
        let shown = GitHubLink.shown(link)
        switch self {
        case .plan:
            return nil
        case .refused(let refusal):
            let message = GitHubLink.shortened(refusal.message, to: Self.shownLineLength)
            return LinkAlert(message: "Metabrowser cannot open this link", detail: "\(message)\n\n\(shown)")
        case .unreadable(let reason, let output):
            var detail = "\(shown)\n\n\(metab) \(GitHubLink.shortened(reason, to: Self.shownLineLength))."
            let tail = output.suffix(PresentDryRun.shownLines).map { GitHubLink.shortened($0, to: Self.shownLineLength) }
            if !tail.isEmpty { detail += " Its last output:\n" + tail.joined(separator: "\n") }
            return LinkAlert(message: "metab could not resolve this link", detail: detail)
        }
    }
}

/// Asks `metab` what a link opens: `metab LINK --present --dry-run --format json`, a short
/// command that clones, fetches, and shows nothing.
///
/// Exit 0 prints a plan with a null `refusal`; a refusal exits nonzero and prints
/// `{"kind": null, "root": null, "page": null, "handoff": null, "refusal": {"code": …,
/// "message": …}}`. The command's stdout and stderr share one pipe (`CommandRunner`), so
/// the answer is the one JSON object among the lines it printed (`JSONAnswer`).
///
/// `RuntimeDiscovery.validate` refuses a `metab` without `--present` at setup, so every
/// runtime the app runs has it.
public nonisolated enum PresentDryRun {
    public static let flag = "--present"
    /// `--present` is a client mode that imports no server, so it answers about as fast as
    /// `metab --version`: 0.32 to 0.33 s for a link, measured 2026-11-18 on an Apple
    /// silicon Mac. The bound is `--version`'s, for a first run after an install, which
    /// compiles bytecode.
    public static let timeout = RuntimeDiscovery.versionTimeout
    /// How many of its last lines an unreadable answer's alert shows.
    static let shownLines = 5
    /// The most of an unknown `kind` a reason quotes: every kind the app knows is shorter.
    static let quotedKindLength = 40

    public static func arguments(for link: URL) -> [String] {
        [link.absoluteString, flag, "--dry-run", "--format", "json"]
    }

    /// The command, in a server's environment and working directory.
    public static func spec(
        for link: URL, with setup: RuntimeSetup, inherited: [String: String], home: String
    ) -> LaunchSpec {
        LaunchSpec(
            executable: setup.runtime.executable, arguments: arguments(for: link),
            environment: ChildEnvironment.build(inherited: inherited, toolDirectories: setup.tools.directories),
            workingDirectory: CLIServeLaunch.workingDirectory(serving: link, home: home))
    }

    public static func answer(_ result: CommandResult) -> PresentAnswer {
        let output = result.output
        if let launchError = result.launchError {
            return .unreadable(reason: "could not run: \(launchError)", output: [])
        }
        if result.timedOut {
            return .unreadable(reason: "did not answer within \(timeout)", output: output)
        }
        let status = result.status.map { "\(ExitStatus(waitStatus: $0))" } ?? "no exit status"
        let data: Data
        switch JSONAnswer.object(in: output) {
        case .success(let found): data = found
        case .failure(let problem): return .unreadable(reason: "\(problem.description) (\(status))", output: output)
        }
        let wire: Wire
        do {
            wire = try JSONDecoder().decode(Wire.self, from: data)
        } catch {
            return .unreadable(reason: "printed an answer this app cannot read (\(status))", output: output)
        }
        if let refusal = wire.refusal { return .refused(refusal) }
        guard result.succeeded else {
            return .unreadable(reason: "exited without a refusal (\(status))", output: output)
        }
        switch plan(wire) {
        case .success(let plan): return .plan(plan)
        case .failure(let problem): return .unreadable(reason: "answered \(problem.description)", output: output)
        }
    }

    /// The keys of the contract the app reads; a key left out reads as null. `page` is not
    /// read (`PresentPlan`).
    private struct Wire: Decodable {
        var kind: String?
        var root: String?
        var handoff: [String]?
        var refusal: PresentRefusal?
    }

    private static func plan(_ wire: Wire) -> Result<PresentPlan, JSONAnswer.Problem> {
        guard let kindText = wire.kind, let kind = PresentPlan.Kind(rawValue: kindText) else {
            let quoted = wire.kind.map { "\"\(GitHubLink.shortened($0, to: quotedKindLength))\"" } ?? "null"
            return .failure(JSONAnswer.Problem("the kind \(quoted) for a link"))
        }
        guard let text = wire.root, let repository = PresentPlan.repositoryURL(text) else {
            return .failure(JSONAnswer.Problem("a root that is not a GitHub repository"))
        }
        guard let handoff = wire.handoff, handoff.count == 1,
              let link = PresentPlan.handoffURL(handoff[0], in: repository)
        else {
            return .failure(JSONAnswer.Problem("a handoff that is not one link into its repository"))
        }
        return .success(PresentPlan(kind: kind, repository: repository, link: link))
    }
}

/// The one JSON object a short `metab` command printed among its lines, whose stdout and
/// stderr share a pipe (`CommandRunner`).
///
/// A candidate is a line that is a whole object, or a block from a line that is exactly
/// `{` to the next line that is exactly `}`, as `json.dumps(…, indent=2)` prints one. Lines
/// around it, such as a warning on stderr, are passed over. Two candidates are an answer
/// the app cannot trust, since a line on stderr that repeats decoded input could then
/// stand in for the real answer, so they are refused, as are none. A block that does not
/// parse is a candidate too, and one the app cannot read: a stray `{` line before the
/// real answer swallows it into such a block, which must not leave a one-line object
/// after it to stand in (review C10 on #539).
nonisolated enum JSONAnswer {
    /// Output past this holds no answer worth reading: an answer is a few hundred bytes,
    /// and a page of the cache's sources at most about 100 KB.
    static let byteLimit = 512 * 1024

    struct Problem: Error, Equatable, CustomStringConvertible {
        var description: String
        init(_ description: String) { self.description = description }
    }

    static func object(in lines: [String]) -> Result<Data, Problem> {
        guard lines.reduce(0, { $0 + $1.utf8.count + 1 }) <= byteLimit else {
            return .failure(Problem("printed more than \(byteLimit) bytes"))
        }
        func object(_ text: String) -> Data? {
            let data = Data(text.utf8)
            guard (try? JSONSerialization.jsonObject(with: data)) is [String: Any] else { return nil }
            return data
        }
        // nil for a block that does not parse.
        var candidates: [Data?] = []
        var index = lines.startIndex
        while index < lines.endIndex {
            let line = lines[index]
            if line == "{", let end = lines[index...].firstIndex(of: "}") {
                candidates.append(object(lines[index...end].joined(separator: "\n")))
                index = end + 1
                continue
            }
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.hasPrefix("{"), trimmed.hasSuffix("}"), let single = object(trimmed) { candidates.append(single) }
            index += 1
        }
        switch candidates.count {
        case 0: return .failure(Problem("printed no answer"))
        case 1:
            guard let only = candidates[0] else { return .failure(Problem("printed an answer this app cannot read")) }
            return .success(only)
        default: return .failure(Problem("printed \(candidates.count) answers"))
        }
    }
}
