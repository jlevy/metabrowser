import Foundation

/// The links the app hands to `metab` to resolve: an `https` URL on a host that `metab`'s
/// GitHub reducer claims, `_WEB_HOSTS` and `_RAW_HOST` in
/// `src/metabrowser/builtin_plugins/github/urls.py`, which `MetabAcquisitionTests` pins.
///
/// Whether `metab` opens one, and what it selects, is `metab`'s to say (`PresentDryRun`),
/// so the app reads nothing else of the link.
public nonisolated enum GitHubLink {
    public static let hosts: Set<String> = ["github.com", "www.github.com", "raw.githubusercontent.com"]

    public static func accepts(_ url: URL) -> Bool {
        guard url.scheme?.lowercased() == "https", let host = url.host(percentEncoded: false)?.lowercased() else {
            return false
        }
        return hosts.contains(host)
    }
}

/// What `metab TARGET --present --dry-run --json` resolved a target to: what to serve,
/// and the page of it to show. Resolving clones and fetches nothing.
///
///     {"kind": "pull_request", "root": "https://github.com/jlevy/tbd", "page": "/pull/12",
///      "refusal": null}
///
/// `root` is an absolute path, or a repository's canonical URL, which keys its session
/// (`SessionRoot`).
public nonisolated struct PresentPlan: Equatable, Sendable {
    public enum Kind: String, CaseIterable, Equatable, Sendable {
        case folder
        case file
        case repository
        case pullRequest = "pull_request"
        case commit
        case tree
    }

    public enum Root: Equatable, Sendable {
        /// An absolute path on this Mac.
        case local(String)
        /// A repository's canonical URL, `https://github.com/<owner>/<repo>`.
        case repository(URL)
    }

    public var kind: Kind
    public var root: Root
    /// The page to show, or nil for the server's entry page.
    public var page: PageAddress?

    public init(kind: Kind, root: Root, page: PageAddress?) {
        self.kind = kind
        self.root = root
        self.page = page
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

/// How `metab TARGET --present --dry-run --json` answered.
public nonisolated enum PresentAnswer: Equatable, Sendable {
    case plan(PresentPlan)
    case refused(PresentRefusal)
    /// This `metab` has no `--present`: click rejected the flag as an unknown option.
    case unsupported
    /// It could not run, did not finish, or printed nothing this app reads as an answer.
    case unreadable(reason: String, output: [String])

    /// What the app says about `link` when it does not open it, or nil for a plan.
    /// `metab` names the `metab` that answered.
    public func alert(link: URL, metab: String) -> (message: String, detail: String)? {
        switch self {
        case .plan:
            return nil
        case .refused(let refusal):
            return ("Metabrowser cannot open this link", "\(refusal.message)\n\n\(link.absoluteString)")
        case .unsupported:
            let fix =
                MetabRequirement.isReleased
                ? "Upgrade it with \(MetabRequirement.upgradeCommand), then open the link again."
                : "Run make install in the Metabrowser source checkout, which builds a metab that has it, then open the link again."
            return (
                "This metab cannot open links",
                "\(metab) has no \(PresentDryRun.flag), which opening a GitHub link needs. \(fix)"
            )
        case .unreadable(let reason, let output):
            var detail = "\(link.absoluteString)\n\n\(metab) \(reason)."
            let tail = output.suffix(PresentDryRun.shownLines)
            if !tail.isEmpty { detail += " Its last output:\n" + tail.joined(separator: "\n") }
            return ("metab could not resolve this link", detail)
        }
    }
}

/// Asks `metab` what a link opens: `metab LINK --present --dry-run --json`, a short command
/// that clones, fetches, and shows nothing.
///
/// Exit 0 prints a plan with a null `refusal`; a refusal exits nonzero and prints
/// `{"kind": null, "root": null, "page": null, "refusal": {"code": …, "message": …}}`. The
/// command's stdout and stderr share one pipe (`CommandRunner`), so the answer is the JSON
/// object found among the lines it printed.
public nonisolated enum PresentDryRun {
    public static let flag = "--present"
    /// `--present` is a client mode that imports no server, so it answers about as fast as
    /// `metab --version`, which takes 0.4 s; the bound is `RuntimeDiscovery.versionTimeout`'s,
    /// for a first run after an install, which compiles bytecode.
    public static let timeout: Duration = .seconds(20)
    /// An answer is a few hundred bytes; output past this holds no answer worth reading.
    static let byteLimit = 64 * 1024
    /// How many of its last lines an unreadable answer's alert shows.
    static let shownLines = 5

    public static func arguments(for link: URL) -> [String] {
        [link.absoluteString, flag, "--dry-run", "--json"]
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
        guard output.reduce(0, { $0 + $1.utf8.count + 1 }) <= byteLimit else {
            return .unreadable(reason: "printed more than \(byteLimit) bytes (\(status))", output: output)
        }
        guard let data = jsonObject(in: output) else {
            return rejectsFlag(result) ? .unsupported : .unreadable(reason: "printed no answer (\(status))", output: output)
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

    /// The contract's four keys; a key left out reads as null.
    private struct Wire: Decodable {
        var kind: String?
        var root: String?
        var page: String?
        var refusal: PresentRefusal?
    }

    struct Problem: Error, CustomStringConvertible {
        var description: String
    }

    private static func plan(_ wire: Wire) -> Result<PresentPlan, Problem> {
        guard let kindText = wire.kind, let kind = PresentPlan.Kind(rawValue: kindText) else {
            return .failure(Problem(description: "the kind \(wire.kind.map { "\"\($0)\"" } ?? "null")"))
        }
        let root: PresentPlan.Root
        if let text = wire.root, text.hasPrefix("/"), !text.contains(where: { $0.isNewline || $0 == "\0" }) {
            root = .local(text)
        } else if let text = wire.root, let url = PresentPlan.repositoryURL(text) {
            root = .repository(url)
        } else {
            return .failure(Problem(description: "a root that is neither a path nor a GitHub repository"))
        }
        var page: PageAddress?
        if let text = wire.page {
            guard let address = PageAddress(reference: text) else {
                return .failure(Problem(description: "a page that is not a path of the server"))
            }
            page = address
        }
        return .success(PresentPlan(kind: kind, root: root, page: page))
    }

    /// The JSON object among `lines`: all of them, else from the first line that starts one
    /// to the last that ends one, as indented JSON prints, else a line that is one. A line
    /// stderr wrote before or after the answer is passed over.
    static func jsonObject(in lines: [String]) -> Data? {
        func object(_ text: String) -> Data? {
            let data = Data(text.utf8)
            guard (try? JSONSerialization.jsonObject(with: data)) is [String: Any] else { return nil }
            return data
        }
        let trimmed = lines.map { $0.trimmingCharacters(in: .whitespaces) }
        if let whole = object(lines.joined(separator: "\n")) { return whole }
        if let first = trimmed.firstIndex(where: { $0.hasPrefix("{") }),
           let last = trimmed.lastIndex(where: { $0.hasSuffix("}") }), first <= last,
           let span = object(lines[first...last].joined(separator: "\n")) {
            return span
        }
        return trimmed.lazy.filter { $0.hasPrefix("{") && $0.hasSuffix("}") }.compactMap(object).first
    }

    /// Whether `result` is click's rejection of `--present` as an unknown option: exit
    /// status 2, with the flag named in what it printed, as `RuntimeDiscovery` recognizes a
    /// `metab` built before `--exit-on-eof`.
    static func rejectsFlag(_ result: CommandResult) -> Bool {
        guard let status = result.status, ExitStatus(waitStatus: status) == .exited(2) else { return false }
        return result.output.contains { $0.contains(flag) }
    }
}
