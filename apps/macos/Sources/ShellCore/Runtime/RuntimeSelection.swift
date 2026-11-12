import Foundation

/// Which `metab` the app starts for folders, and the searches and choices that change it.
///
/// Find Again (a discovery) and Choose metab… (validating the chosen file) both wait on
/// subprocesses, so one can start while the other is still running. Each takes a ticket
/// when it starts, and only the newest one's result applies: an older search that
/// finishes after a newer choice changes nothing, not the setup, the saved settings,
/// the window, or the folders waiting for a runtime. A search a choice overtook stops
/// counting as running at once.
///
/// `setup` is the one place the current runtime lives, and the saved settings follow
/// it. A search that finds nothing clears both, not only the display, so neither a
/// folder opened next nor the next launch starts the runtime that failed; servers
/// already running keep theirs.
public final class RuntimeSelection {
    /// What finishing an operation did.
    public enum Outcome: Equatable, Sendable {
        /// The runtime is now this one, and it is saved.
        case adopted(RuntimeSetup)
        /// The search found nothing, and the runtime is now none, also when saved.
        case notFound
        /// The chosen file is not a working `metab`; nothing changed.
        case rejected(CandidateResult)
        /// A newer search or choice started meanwhile; nothing changed.
        case superseded
    }

    /// Identifies one search or choice, from its start to its finish.
    public struct Ticket: Equatable, Sendable {
        fileprivate let number: Int
    }

    public private(set) var setup: RuntimeSetup?
    public private(set) var isSearching = false
    /// Whether the current runtime is being checked again, because its file changed or
    /// its version is one this app no longer accepts. Folders asked for meanwhile wait,
    /// so none starts the file that changed before the check says what it is.
    public private(set) var isRechecking = false
    /// What the last search that counted looked at.
    public private(set) var tried: [CandidateOutcome] = []
    /// Folders asked for while there was no runtime, in the order asked.
    public private(set) var waitingFolders: [URL] = []
    private let settings: RuntimeSettings
    private var latest = 0

    public init(settings: RuntimeSettings, setup: RuntimeSetup?) {
        self.settings = settings
        self.setup = setup
    }

    /// The runtime to open `folder` with, or nil after adding it to the folders waiting
    /// for one.
    public func setupForOpening(_ folder: URL) -> RuntimeSetup? {
        if let setup, !isRechecking { return setup }
        if !waitingFolders.contains(folder) { waitingFolders.append(folder) }
        return nil
    }

    /// The waiting folders, which the caller now opens, emptying the list.
    public func takeWaitingFolders() -> [URL] {
        defer { waitingFolders.removeAll() }
        return waitingFolders
    }

    /// Starts a search: it is running from this call on, so a folder asked for in the
    /// same run-loop turn waits for it.
    public func startSearch() -> Ticket {
        isSearching = true
        isRechecking = false
        return next()
    }

    public func finishSearch(_ ticket: Ticket, with report: DiscoveryReport) -> Outcome {
        guard ticket.number == latest else { return .superseded }
        isSearching = false
        tried = report.tried
        guard let found = report.setup else {
            settings.clear()
            setup = nil
            return .notFound
        }
        return adopt(found)
    }

    /// Starts validating a chosen file, which overtakes any search still running.
    public func startChoice() -> Ticket {
        isSearching = false
        isRechecking = false
        return next()
    }

    /// `tools` supplies the tool paths when there is no current setup to keep them from.
    /// `fingerprint` is the chosen file's, taken before it was validated.
    public func finishChoice(
        _ ticket: Ticket, path: String, result: CandidateResult, fingerprint: FileFingerprint? = nil,
        tools: () -> ToolPaths
    ) -> Outcome {
        guard ticket.number == latest else { return .superseded }
        guard case .valid(let version) = result else { return .rejected(result) }
        return adopt(RuntimeSetup(
            runtime: Runtime(executable: path, version: version, source: .chosen, fingerprint: fingerprint),
            tools: setup?.tools ?? tools()))
    }

    /// Starts checking the current runtime again, which a search or choice started later
    /// overtakes. Call it only while there is a runtime.
    public func startRecheck() -> Ticket {
        isRechecking = true
        return next()
    }

    /// A valid result keeps the runtime's executable, source, and tools, with the new
    /// version and `fingerprint`, taken before it was validated. Anything else leaves no
    /// runtime, and the caller searches again.
    public func finishRecheck(_ ticket: Ticket, fingerprint: FileFingerprint?, result: CandidateResult) -> Outcome {
        guard ticket.number == latest else { return .superseded }
        isRechecking = false
        guard let current = setup else { return .notFound }
        tried = [CandidateOutcome(path: current.runtime.executable, source: current.runtime.source, result: result)]
        guard case .valid(let version) = result else {
            setup = nil
            return .notFound
        }
        var runtime = current.runtime
        runtime.version = version
        runtime.fingerprint = fingerprint
        return adopt(RuntimeSetup(runtime: runtime, tools: current.tools))
    }

    private func next() -> Ticket {
        latest += 1
        return Ticket(number: latest)
    }

    private func adopt(_ found: RuntimeSetup) -> Outcome {
        settings.save(found)
        setup = found
        return .adopted(found)
    }
}
