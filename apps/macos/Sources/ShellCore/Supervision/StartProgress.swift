import Foundation

/// What a repository's server says it is doing before it is ready, which the status view
/// shows under "Starting…" (`ServerSupervisor.startProgress`).
///
/// It is read from the account `metab` writes to stderr while it acquires a source
/// (`src/metabrowser/cli/clone_report.py`). Without a terminal, as in the app's server log,
/// `metab` writes a whole line at each step, and a line of the clone's progress every
/// `MetabAcquisition.progressLineInterval`:
///
///     cloning https://github.com/owner/repo into ~/.cache/metabrowser
///     cloning https://github.com/owner/repo: receiving objects: 45%, 334.0 MiB at 9.5 MiB/s (40 s)
///     cloned https://github.com/owner/repo in 104 s (742.0 MiB); starting the server
///
/// A repository the cache holds says `using the clone of URL cached in DIRECTORY,
/// fetched … ago` instead, and a link to a pull request then says
/// `reading pull request N (5.5 s)` while `metab` reads it from GitHub.
///
/// Those lines are `metab`'s own words around Git's numbers, never text Git or the origin
/// wrote, so the view shows them as written, less the repository's URL, which the window
/// already names. The newest such line is the progress, and every other line is passed
/// over. `StartProgressTests` holds samples of each, and `tests/test_macos_app_pins.py`
/// holds those samples to what `metab` writes.
public nonisolated enum StartProgress: Equatable, Sendable {
    /// A first clone began, into the cache directory named here.
    case cloning(into: String)
    /// How far the clone has got, in `metab`'s words, with the time it has taken so far.
    case status(String)
    /// The clone finished: how long it took, how much it fetched, and what comes next.
    case cloned(String)
    /// The cache held the repository: where, and how long ago it was fetched.
    case cached(String)
    /// A step after the clone with no progress of its own, such as reading a pull request.
    case waiting(String)

    /// What the status view says.
    public var text: String {
        switch self {
        case .cloning(let directory): "Cloning into \(directory)"
        case .status(let status): Self.sentence(status)
        case .cloned(let rest): "Cloned \(rest)"
        case .cached(let rest): "Using the clone \(rest)"
        case .waiting(let step): Self.sentence(step)
        }
    }

    /// What the newest progress line among `output` reports, or nil when none is one.
    public static func latest(in output: [String]) -> StartProgress? {
        output.lazy.reversed().compactMap(parse).first
    }

    /// The progress `line` reports, or nil when it is not one of `metab`'s progress lines.
    public static func parse(_ line: String) -> StartProgress? {
        if let rest = line.removing(prefix: "cloning ") {
            guard let (url, after) = splitURL(rest) else { return nil }
            if url.hasSuffix(":") { return after.isEmpty ? nil : .status(after) }
            return after.removing(prefix: "into ").map { .cloning(into: $0) }
        }
        if let rest = line.removing(prefix: "cloned ") {
            guard let (_, after) = splitURL(rest), after.hasPrefix("in ") else { return nil }
            return .cloned(after)
        }
        if let rest = line.removing(prefix: "using the clone of ") {
            guard let (_, after) = splitURL(rest), after.hasPrefix("cached in ") else { return nil }
            return .cached(after)
        }
        // `saying_while_waiting` in `clone_report.py`: the step, then its time so far.
        if line.hasPrefix(pullRequestStep), line.hasSuffix(" s)") {
            return .waiting(line)
        }
        return nil
    }

    /// The step `metab URL` names while it reads the pull request a link names from GitHub.
    static let pullRequestStep = "reading pull request "

    /// The source URL that starts `text`, which holds no space, and what follows it.
    private static func splitURL(_ text: String) -> (url: String, after: String)? {
        guard let space = text.firstIndex(of: " ") else { return nil }
        let url = String(text[..<space])
        guard url.contains("://") else { return nil }
        return (url, String(text[text.index(after: space)...]))
    }

    /// `text` with its first letter capitalized, as the start of a line in the view.
    private static func sentence(_ text: String) -> String {
        text.prefix(1).uppercased() + text.dropFirst()
    }
}

extension String {
    /// What follows `prefix`, or nil when the string does not start with it.
    fileprivate nonisolated func removing(prefix: String) -> String? {
        hasPrefix(prefix) ? String(dropFirst(prefix.count)) : nil
    }
}
