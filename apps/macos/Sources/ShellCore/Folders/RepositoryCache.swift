import Foundation

/// Whether `metab`'s cache holds a repository already, which decides whether a link that
/// opens it asks first: a first clone downloads the repository and reads it, and its pull
/// requests, with the user's `gh` sign-in, on the word of whatever process sent the link.
///
/// `metab` answers it, through the route it keeps for the cache's sources:
/// `metab FOLDER --api '/api/cache/sources?limit=…' --format json`, one page at a time.
/// The repository is cached when a source whose `identity.display_url` is its canonical
/// URL is published with no problems, which is the source `metab URL` serves from without
/// cloning. The route reads records alone, never Git or the network; `FOLDER` is any
/// folder, whose server is never started, and the app passes its own support folder.
public nonisolated enum RepositoryCache {
    public enum Answer: Equatable, Sendable {
        case cached
        case notCached
        /// The route could not be read, so the app asks, as for a repository not cached.
        case unknown(String)
    }

    /// `MAX_PAGE_LIMIT` in `src/metabrowser/cache/projection.py`, which
    /// `tests/test_macos_app_pins.py` pins: the largest page the route gives.
    static let pageLimit = 100
    /// How many pages are read before the answer is unknown: a thousand sources. One page
    /// takes about 0.8 s, most of it `metab`'s start (12 sources, measured 2026-11-18 on an
    /// Apple silicon Mac).
    static let maximumPages = 10

    public static func arguments(folder: String, after: String?) -> [String] {
        var route = "/api/cache/sources?limit=\(pageLimit)"
        if let after, let encoded = after.addingPercentEncoding(withAllowedCharacters: slugCharacters) {
            route += "&after=" + encoded
        }
        return [folder, "--api", route, "--format", "json"]
    }

    private static let slugCharacters = CharacterSet(charactersIn: "abcdefghijklmnopqrstuvwxyz0123456789-")

    /// One page's command, in a server's environment, run in `folder`.
    public static func spec(
        folder: String, after: String?, with setup: RuntimeSetup, inherited: [String: String]
    ) -> LaunchSpec {
        LaunchSpec(
            executable: setup.runtime.executable, arguments: arguments(folder: folder, after: after),
            environment: ChildEnvironment.build(inherited: inherited, toolDirectories: setup.tools.directories),
            workingDirectory: folder)
    }

    /// What one page said.
    enum Page: Equatable {
        case found
        /// Not on this page; the next starts after this slug.
        case next(String)
        /// Not on any page.
        case end
        case unreadable(String)
    }

    static func read(_ result: CommandResult, looking repository: URL) -> Page {
        if let launchError = result.launchError { return .unreadable("could not run: \(launchError)") }
        if result.timedOut { return .unreadable("did not answer within \(RuntimeDiscovery.versionTimeout)") }
        guard result.succeeded else {
            let status = result.status.map { "\(ExitStatus(waitStatus: $0))" } ?? "no exit status"
            return .unreadable("\(status): \(result.output.last ?? "no output")")
        }
        let data: Data
        switch JSONAnswer.object(in: result.output) {
        case .success(let found): data = found
        case .failure(let problem): return .unreadable(problem.description)
        }
        guard let page = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let sources = page["sources"] as? [[String: Any]]
        else { return .unreadable("printed no list of sources") }
        let wanted = repository.absoluteString
        for source in sources {
            let identity = source["identity"] as? [String: Any]
            guard identity?["display_url"] as? String == wanted, source["publication"] as? String == "published"
            else { continue }
            if (source["problems"] as? [Any])?.isEmpty ?? true { return .found }
        }
        guard let after = page["next_after"] as? String else { return .end }
        return .next(after)
    }

    /// Asks `metab` whether it has `repository`, page by page.
    public static func lookUp(
        _ repository: URL, folder: String, with setup: RuntimeSetup, inherited: [String: String],
        run: CommandRunner.Run = CommandRunner.live
    ) async -> Answer {
        var after: String?
        for _ in 0..<maximumPages {
            let spec = spec(folder: folder, after: after, with: setup, inherited: inherited)
            switch read(await run(spec, RuntimeDiscovery.versionTimeout), looking: repository) {
            case .found: return .cached
            case .end: return .notCached
            case .next(let slug):
                guard slug != after else { return .unknown("the route repeated a page") }
                after = slug
            case .unreadable(let reason): return .unknown(reason)
            }
        }
        return .unknown("the cache lists more than \(maximumPages * pageLimit) sources")
    }
}
