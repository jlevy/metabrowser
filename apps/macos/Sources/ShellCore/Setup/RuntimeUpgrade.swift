/// What the app offers when the `metab` it runs is upgraded under its servers.
///
/// `uv tool upgrade` run in Terminal rewrites the environment the servers import from
/// while they run, and the app notices only afterwards, so the offer shortens the time
/// old servers run against new files; it cannot prevent it.
public nonisolated enum RuntimeUpgrade {
    /// The indices of `running` whose servers started from `current`'s executable at
    /// another version. A server started from another `metab` is not outdated by this
    /// one; Restart Server moves it over.
    public static func outdated(_ running: [Runtime], current: Runtime) -> [Int] {
        running.indices.filter {
            running[$0].executable == current.executable && running[$0].version != current.version
        }
    }

    public struct Prompt: Equatable, Sendable {
        public var title: String
        public var message: String
    }

    public static func prompt(outdated: [Runtime], current: Runtime) -> Prompt {
        var versions: [String] = []
        for runtime in outdated where !versions.contains(shortVersion(runtime)) {
            versions.append(shortVersion(runtime))
        }
        let new = shortVersion(current)
        let count = outdated.count
        let subject = count == 1
            ? "1 open folder runs a server started from metab \(versions.joined(separator: " and "))."
            : "\(count) open folders run servers started from metab \(versions.joined(separator: " and "))."
        return Prompt(
            title: "metab was updated to \(new)",
            message: subject
                + " The update replaced the files they load code from, so they can fail on a page they have not shown yet."
                + " Restart them to run \(new)? Each window reloads its page.")
    }

    /// The version alone, without a checkout's description.
    private static func shortVersion(_ runtime: Runtime) -> String {
        MetabVersion(runtime.version)?.text ?? runtime.version
    }
}
