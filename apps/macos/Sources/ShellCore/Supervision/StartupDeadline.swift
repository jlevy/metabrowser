import Foundation

/// When a start that has not become ready is given up on (`SupervisorPolicy.startupTimeout`
/// and `startupLimit`).
///
/// A folder's server is ready within seconds, so without a limit its start gets `quiet`
/// from its spawn, whatever it writes. A repository's server clones the repository first,
/// which for a large one runs for minutes, so with a limit the start is given up on only
/// once it has written nothing for `quiet`, or once `limit` has passed since its spawn,
/// whichever comes first. A start that keeps writing is making progress: `metab` writes a
/// line of a clone's progress at least every `MetabAcquisition.progressLineInterval` when
/// its stderr is not a terminal, as the app's server log is, and keeps writing them, with
/// the same numbers under a growing time, while the transfer stalls, until its own stall
/// bound ends the fetch.
public nonisolated struct StartupDeadline: Equatable, Sendable {
    public typealias Instant = ContinuousClock.Instant

    /// Why a start was given up on.
    public enum Expiry: Equatable, Sendable {
        /// It wrote nothing for `quiet`, or, without a limit, `quiet` passed since the spawn.
        case quiet
        /// `limit` passed since the spawn, however much it wrote.
        case limit
    }

    public let quiet: Duration
    /// Nil for a start that `quiet` bounds from its spawn.
    public let limit: Duration?
    public let spawned: Instant
    /// When the child's output was last seen to grow, or the spawn.
    public private(set) var lastOutput: Instant
    private var written: Int

    /// - Parameter written: the child's `ServerProcess.outputProgress` at the spawn.
    public init(quiet: Duration, limit: Duration?, spawned: Instant, written: Int = 0) {
        self.quiet = quiet
        self.limit = limit
        self.spawned = spawned
        lastOutput = spawned
        self.written = written
    }

    /// Notes the child's `ServerProcess.outputProgress` as read at `now`: a count that
    /// changed since the last look means it wrote something.
    public mutating func observe(written: Int, at now: Instant) {
        guard written != self.written else { return }
        self.written = written
        lastOutput = max(lastOutput, now)
    }

    /// Notes output seen at `now`, such as the line that announces the server's address.
    public mutating func noteOutput(at now: Instant) {
        lastOutput = max(lastOutput, now)
    }

    /// The moment the start is given up on, as things stand.
    public var expiry: Instant {
        guard let limit else { return spawned.advanced(by: quiet) }
        return min(spawned.advanced(by: limit), lastOutput.advanced(by: quiet))
    }

    /// The longest the start can last from its spawn, however much it writes.
    public var longest: Duration { limit ?? quiet }

    /// Why the start is given up on at `now`, or nil while it has time.
    public func expired(at now: Instant) -> Expiry? {
        guard now >= expiry else { return nil }
        guard let limit, now >= spawned.advanced(by: limit) else { return .quiet }
        return .limit
    }

    /// The failure's summary for a start given up on for `expiry` while it waited to `what`
    /// ("announce its address"), or, once it had `announced` its address, to answer.
    /// After the announcement nothing watches the output, so `quiet` then runs from it.
    public func summary(_ expiry: Expiry, waitingFor what: String, announced: Bool = false) -> String {
        switch (expiry, limit) {
        case (.quiet, nil), (.limit, nil):
            "The server did not \(what) within \(quiet)."
        case (.quiet, .some) where announced:
            "The server did not \(what) within \(quiet) of announcing its address."
        case (.quiet, .some):
            "The server wrote nothing for \(quiet) and did not \(what)."
        case (.limit, .some(let limit)) where announced:
            "The server did not \(what) within \(Self.spoken(limit))."
        case (.limit, .some(let limit)):
            "The server did not \(what) within \(Self.spoken(limit)), though it was still writing."
        }
    }

    /// `duration` as the failure says it: whole minutes once it is longer than two of
    /// them, as a repository's limit is, and otherwise as `Duration` prints itself.
    static func spoken(_ duration: Duration) -> String {
        let seconds = duration.components.seconds
        guard seconds > 120 else { return "\(duration)" }
        let minutes = Int((Double(seconds) / 60).rounded())
        return "\(minutes) minutes"
    }
}

/// The bounds `metab` puts on acquiring a source, which a repository's start must outlast:
/// a shorter limit would stop a clone that `metab` would have finished. Each is a copy of
/// the constant named beside it, and `tests/test_macos_app_pins.py` pins it to that
/// definition, in the CI job that runs on every change, whichever side moved.
public nonisolated enum MetabAcquisition {
    /// `REMOTE_PROBE_TIMEOUT_S` in `src/metabrowser/cache/origin.py`: the probe of the
    /// origin before a fetch.
    public static let remoteProbe: Duration = .seconds(30)
    /// `GIT_ACQUISITION_TIMEOUT_S` in `src/metabrowser/git/process.py`: one fetch.
    public static let fetch: Duration = .seconds(900)
    /// The minute `RESERVATION_WAIT_S` in `src/metabrowser/cache/acquire.py` gives the
    /// local validation and publication after each attempt.
    public static let validation: Duration = .seconds(60)
    /// The attempts `RESERVATION_WAIT_S` allows for: a refused borrow falls back to a full
    /// clone.
    public static let attempts = 2
    /// `RESERVATION_WAIT_S`, `metab`'s own bound on another process's acquisition of the
    /// same source, which is its worst case for one: 1,980 s.
    public static var reservationWait: Duration { (remoteProbe + fetch + validation) * attempts }
    /// `LOG_INTERVAL_S` in `src/metabrowser/cli/clone_report.py`: how often a clone whose
    /// stderr is not a terminal writes a line of its progress. Its comment holds the
    /// measurement (2026-10-01: a 740 MB clone in about 100 s wrote nine). Measured again
    /// for this app on 2026-11-17, `metab https://github.com/git/git --no-open` (0.12.1.dev1656,
    /// an Apple silicon Mac, an empty cache) with stderr to a file, as the server log is:
    /// the first line 1.7 s after the spawn, then one every 10.0 to 10.5 s, through
    /// receiving 311.2 MiB and resolving deltas, and the announcement 43.9 s after it.
    public static let progressLineInterval: Duration = .seconds(10)
}
