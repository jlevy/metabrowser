import Foundation

/// Where Metabrowser's own event log is, which Help > Open Event Log opens.
///
/// A served `metab` writes a structured log of its requests and its work to `events/` under
/// its state directory, and the event-log plugin opens one segment of it as spans and
/// latencies. The app does not know where that directory is, because `metab` takes it from
/// `METABROWSER_STATE_DIR`, `XDG_STATE_HOME`, or the home directory, so it asks the route that
/// lists it, newest segment first: `metab FOLDER --api '/api/event-log?limit=1' --format json`.
/// The route reads files alone and starts no server. `FOLDER` is any folder, as for
/// `RepositoryCache`, and not the log's directory, which `--api` would write as `<ROOT>`:
/// the app passes its own support folder. A state directory with no log yet is an answer, a
/// directory with no segment, and the app says so.
///
/// The newest segment is opened as any file is, in a window on its folder: that folder's
/// server writes no log of its own, which would change the files on screen.
public nonisolated enum EventLogLocation {
    public enum Answer: Equatable, Sendable {
        /// The newest segment, a file in the log's directory.
        case found(URL)
        /// The directory exists and holds no segment.
        case empty(URL)
        /// `metab` could not say, and why: what it printed, or how it ended.
        case unavailable(String)
    }

    static let route = "/api/event-log?limit=1"

    public static func arguments(folder: String) -> [String] {
        [folder, "--api", route, "--format", "json"]
    }

    /// The command, in a server's environment, run in `folder`.
    public static func spec(folder: String, with setup: RuntimeSetup, inherited: [String: String]) -> LaunchSpec {
        LaunchSpec(
            executable: setup.runtime.executable, arguments: arguments(folder: folder),
            environment: ChildEnvironment.build(inherited: inherited, toolDirectories: setup.tools.directories),
            workingDirectory: folder)
    }

    static func read(_ result: CommandResult) -> Answer {
        if let launchError = result.launchError { return .unavailable("could not run: \(launchError)") }
        if result.timedOut { return .unavailable("did not answer within \(RuntimeDiscovery.versionTimeout)") }
        guard result.succeeded else {
            let status = result.status.map { "\(ExitStatus(waitStatus: $0))" } ?? "no exit status"
            return .unavailable(result.output.last ?? status)
        }
        let data: Data
        switch JSONAnswer.object(in: result.output) {
        case .success(let found): data = found
        case .failure(let problem): return .unavailable(problem.description)
        }
        guard let answer = try? JSONSerialization.jsonObject(with: data) as? [String: Any],
              let directory = answer["directory"] as? String, !directory.isEmpty,
              let files = answer["files"] as? [[String: Any]]
        else { return .unavailable("printed no directory and list of segments") }
        let folder = URL(filePath: directory, directoryHint: .isDirectory)
        // Newest first, as the route lists them.
        guard let name = files.first?["name"] as? String, !name.isEmpty, !name.contains("/") else {
            return .empty(folder)
        }
        return .found(folder.appending(path: name, directoryHint: .notDirectory))
    }

    /// Asks `metab` where the log is.
    public static func locate(
        folder: String, with setup: RuntimeSetup, inherited: [String: String],
        run: CommandRunner.Run = CommandRunner.live
    ) async -> Answer {
        read(await run(spec(folder: folder, with: setup, inherited: inherited), RuntimeDiscovery.versionTimeout))
    }
}
