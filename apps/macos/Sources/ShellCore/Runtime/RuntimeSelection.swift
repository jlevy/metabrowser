import Foundation

/// Which `metab` the app starts for folders, and the searches and choices that change it.
///
/// Find Again (a discovery) and Choose metab… (validating the chosen file) both wait on
/// subprocesses, so one can start while the other is still running. Each takes a ticket
/// when it starts, and only the newest one's result applies: an older search that
/// finishes after a newer choice changes nothing, not the setup, the saved settings,
/// the window, or the folders waiting for a runtime. A search a choice overtook stops
/// counting as running at once, and if the choice adopts nothing, the search is owed
/// again (`needsSearch`).
///
/// `setup` is the one place the current runtime lives, and the saved settings follow
/// it. A search that finds nothing clears both, not only the display, so neither a
/// folder opened next nor the next launch starts the runtime that failed; servers
/// already running keep theirs.
///
/// A runtime whose file changed is unverified until a recheck, a search, or a choice
/// validates what to run, whichever of them finishes it: no server starts from it
/// meanwhile (`launchableSetup`), however those operations overtake each other.
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

    /// The operation holding the newest ticket, while it runs.
    private enum Operation { case search, recheck, choice }

    public private(set) var setup: RuntimeSetup?
    /// Whether `setup`'s file changed, or its version is one this app no longer accepts,
    /// and nothing has validated it since. Folders asked for meanwhile wait, so none
    /// starts the file that changed before a check says what it is.
    public private(set) var isUnverified = false
    /// What the last search that counted looked at.
    public private(set) var tried: [CandidateOutcome] = []
    /// Folders asked for while there was no runtime, in the order asked.
    public private(set) var waitingFolders: [URL] = []
    private let settings: RuntimeSettings
    private var latest = 0
    private var operation: Operation?
    /// Whether a choice overtook a running search, and nothing has answered that search
    /// since: no newer search started, and no choice was adopted.
    private var isSearchUnanswered = false

    public init(settings: RuntimeSettings, setup: RuntimeSetup?) {
        self.settings = settings
        self.setup = setup
    }

    public var isSearching: Bool { operation == .search }
    /// Whether the current runtime is being checked again.
    public var isRechecking: Bool { operation == .recheck }
    /// Whether a file chosen with Choose metab… is being validated.
    public var isChoosing: Bool { operation == .choice }
    /// Whether a search, recheck, or choice is running. Checks the app starts by itself
    /// wait for it, so none overtakes what the user asked for.
    public var isBusy: Bool { operation != nil }

    /// The runtime a server may start from now: the current one, unless it is
    /// unverified. Every start, restart, and retry asks at the moment it would launch.
    public var launchableSetup: RuntimeSetup? { isUnverified ? nil : setup }

    /// Whether the runtime is unverified and nothing running will validate it.
    public var needsRecheck: Bool { setup != nil && isUnverified && operation == nil }

    /// Whether a search was overtaken by a choice that adopted nothing, so nothing running
    /// will answer it: its own result no longer counts, and the folders and the restore
    /// waiting for it would wait for Find Again. The caller searches again, with a fresh
    /// ticket, so the overtaken search's late result still changes nothing.
    public var needsSearch: Bool { isSearchUnanswered && operation == nil }

    /// The runtime to open `folder` with, or nil after adding it to the folders waiting
    /// for one.
    public func setupForOpening(_ folder: URL) -> RuntimeSetup? {
        if let setup = launchableSetup { return setup }
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
        next(.search)
    }

    public func finishSearch(_ ticket: Ticket, with report: DiscoveryReport) -> Outcome {
        guard ticket.number == latest else { return .superseded }
        operation = nil
        tried = report.tried
        guard let found = report.setup else {
            settings.clear()
            clear()
            return .notFound
        }
        return adopt(found)
    }

    /// Starts validating a chosen file, which overtakes any search still running.
    public func startChoice() -> Ticket {
        next(.choice)
    }

    /// `tools` supplies the tool paths when there is no current setup to keep them from.
    /// `fingerprint` is the chosen file's, taken before it was validated.
    public func finishChoice(
        _ ticket: Ticket, path: String, result: CandidateResult, fingerprint: FileFingerprint? = nil,
        tools: () -> ToolPaths
    ) -> Outcome {
        guard ticket.number == latest else { return .superseded }
        operation = nil
        guard case .valid(let version) = result else { return .rejected(result) }
        isSearchUnanswered = false  // the chosen runtime answers it
        return adopt(RuntimeSetup(
            runtime: Runtime(executable: path, version: version, source: .chosen, fingerprint: fingerprint),
            tools: setup?.tools ?? tools()))
    }

    /// Holds new servers off the current runtime until something validates it again,
    /// starting nothing: a search or choice already running settles it, and otherwise
    /// the caller starts a recheck (`needsRecheck`).
    public func markUnverified() {
        if setup != nil { isUnverified = true }
    }

    /// Starts checking the current runtime again, which a search or choice started later
    /// overtakes. Call it only while there is a runtime.
    public func startRecheck() -> Ticket {
        markUnverified()
        return next(.recheck)
    }

    /// A valid result keeps the runtime's executable, source, and tools, with the new
    /// version and `fingerprint`, taken before it was validated. Anything else leaves no
    /// runtime, and the caller searches again.
    public func finishRecheck(_ ticket: Ticket, fingerprint: FileFingerprint?, result: CandidateResult) -> Outcome {
        guard ticket.number == latest else { return .superseded }
        operation = nil
        guard let current = setup else { return .notFound }
        tried = [CandidateOutcome(path: current.runtime.executable, source: current.runtime.source, result: result)]
        guard case .valid(let version) = result else {
            clear()
            return .notFound
        }
        var runtime = current.runtime
        runtime.version = version
        runtime.fingerprint = fingerprint
        return adopt(RuntimeSetup(runtime: runtime, tools: current.tools))
    }

    private func next(_ started: Operation) -> Ticket {
        switch started {
        case .search: isSearchUnanswered = false
        case .choice: if operation == .search { isSearchUnanswered = true }
        case .recheck: break
        }
        operation = started
        latest += 1
        return Ticket(number: latest)
    }

    private func clear() {
        setup = nil
        isUnverified = false
    }

    /// Adopts a setup that was just validated.
    private func adopt(_ found: RuntimeSetup) -> Outcome {
        settings.save(found)
        setup = found
        isUnverified = false
        return .adopted(found)
    }
}
