import Foundation

/// The searches, rechecks, and choices that settle which `metab` the app runs, and what
/// each one that ends starts next.
///
/// `RuntimeSelection` holds the tickets that decide which result counts; this runs the
/// work for each operation and keeps the follow-ups in one place:
///
/// - A recheck that rejects the runtime leaves none, so a search looks for another.
/// - A choice that is rejected changes nothing, so what it overtook or held off still
///   needs an answer: a runtime whose file changed while it ran is checked again, and a
///   search it overtook runs again, with a fresh ticket, so the overtaken one's late
///   result still changes nothing. Without that, a choice rejected during the first
///   search left no runtime, no search, and no first-run steps, and the folders opened
///   meanwhile waited for Find Again.
///
/// The app (`AppDelegate`) supplies the work, which runs `metab` and the login shell, and
/// shows each operation's end; `RuntimeOperationsTests` drive it with fakes.
public final class RuntimeOperations {
    /// What the operations run.
    public struct Work {
        /// A search of the documented places (`RuntimeDiscovery.discover`).
        public var discover: () async -> DiscoveryReport
        /// A file's fingerprint, taken before it is validated, and its validation, given
        /// where it came from (`RuntimeDiscovery.validate`).
        public var validate: (String, RuntimeSource) async -> (FileFingerprint?, CandidateResult)
        /// The tool paths for a chosen file when there is no runtime to keep them from.
        public var tools: () -> ToolPaths
        /// Why the app may not run a file it found by itself now, or nil if it may
        /// (`ExecutableTrust`).
        public var refusal: (String) -> String?

        public init(
            discover: @escaping () async -> DiscoveryReport,
            validate: @escaping (String, RuntimeSource) async -> (FileFingerprint?, CandidateResult),
            tools: @escaping () -> ToolPaths,
            refusal: @escaping (String) -> String? = { ExecutableTrust.refusal($0) }
        ) {
            self.discover = discover
            self.validate = validate
            self.tools = tools
            self.refusal = refusal
        }
    }

    /// An operation that started.
    public enum Start: Equatable, Sendable {
        case search
        /// The runtime at this path is checked again.
        case recheck(String)
        /// The file at this path, chosen with Choose metab…, is checked.
        case choice(String)
    }

    /// An operation that ended, and what it did.
    public struct Finish: Equatable, Sendable {
        public enum Operation: Equatable, Sendable {
            case search(DiscoveryReport)
            case recheck(String, CandidateResult)
            case choice(String)
        }

        public var operation: Operation
        public var outcome: RuntimeSelection.Outcome
        /// The folders that waited for a runtime, handed over for the app to open when this
        /// one adopted a runtime.
        public var released: [URL]
    }

    public let selection: RuntimeSelection
    /// After each change to what `selection` holds, so the window can show it.
    public var onChange: () -> Void = {}
    public var onStart: (Start) -> Void = { _ in }
    /// After an operation ends, before anything it starts next.
    public var onFinish: (Finish) async -> Void = { _ in }
    private let work: Work

    public init(selection: RuntimeSelection, work: Work) {
        self.selection = selection
        self.work = work
    }

    /// The runtime a server may start from at this moment, which every start, restart, and
    /// retry asks, the last time just before its child spawns, after the launch gate and
    /// any earlier child's termination (`FolderServer`, `ServerSupervisor.mayLaunch`).
    ///
    /// It is the selection's runtime, and one the app found by itself only while no other
    /// account can change its file (`ExecutableTrust`), checked now: a folder on its path
    /// made writable by its group, a changed access control list, or a link on the path
    /// that now leads elsewhere changes no fingerprint, so neither the watch nor the
    /// selection notices it. One that fails is held off, and a recheck, which refuses it
    /// as well, searches for another; whatever waited starts once one is accepted. A file
    /// the user chose is run as chosen.
    public func launchableSetup() -> RuntimeSetup? {
        guard let setup = selection.launchableSetup, setup.runtime.source != .chosen else {
            return selection.launchableSetup
        }
        // An `lstat` and an access control list read for each component of the path: 54 µs
        // for an eleven-component path, measured in a debug build on macOS 26.5.2. A launch
        // asks two or three times.
        guard let reason = work.refusal(setup.runtime.executable) else { return setup }
        onRefusal(setup.runtime.executable, reason)
        beginRecheck()  // which holds the runtime off first, whether or not it runs now
        return nil
    }

    /// A runtime the app found by itself failed `ExecutableTrust` at a launch: its path,
    /// and why.
    public var onRefusal: (String, String) -> Void = { _, _ in }

    /// Starts a search unless one is running. It counts as running from this call on, so
    /// a folder asked for in the same run-loop turn waits for it.
    public func beginDiscovery() {
        guard !selection.isSearching else { return }
        let ticket = selection.startSearch()
        onStart(.search)
        onChange()
        Task { await search(ticket) }
    }

    /// Holds new servers off the runtime, whose file changed, and checks it again, unless
    /// a search, recheck, or choice already running settles it first.
    public func beginRecheck() {
        selection.markUnverified()
        guard selection.needsRecheck, let previous = selection.setup else { return }
        let ticket = selection.startRecheck()
        onStart(.recheck(previous.runtime.executable))
        Task { await recheck(previous, ticket) }
    }

    /// Validates a chosen file and uses it, which overtakes a search still running; returns
    /// once its end is shown.
    public func choose(_ path: String) async {
        let ticket = selection.startChoice()
        onStart(.choice(path))
        onChange()
        let (fingerprint, result) = await work.validate(path, .chosen)
        let outcome = selection.finishChoice(
            ticket, path: path, result: result, fingerprint: fingerprint, tools: work.tools)
        onChange()
        await finish(.choice(path), outcome)
        // A rejected choice leaves a runtime whose file changed meanwhile still unchecked,
        // and a search it overtook unanswered.
        if selection.needsRecheck {
            beginRecheck()
        } else if selection.needsSearch {
            beginDiscovery()
        }
    }

    private func search(_ ticket: RuntimeSelection.Ticket) async {
        let report = await work.discover()
        let outcome = selection.finishSearch(ticket, with: report)
        onChange()
        await finish(.search(report), outcome)
    }

    /// A new compatible version is adopted; anything else leaves no runtime, and a search
    /// looks for another. The file is validated as where it came from, so one the app found
    /// by itself runs again only if no other account can change it.
    private func recheck(_ previous: RuntimeSetup, _ ticket: RuntimeSelection.Ticket) async {
        let path = previous.runtime.executable
        let (fingerprint, result) = await work.validate(path, previous.runtime.source)
        let outcome = selection.finishRecheck(ticket, fingerprint: fingerprint, result: result)
        onChange()
        await finish(.recheck(path, result), outcome)
        // A search a rejected choice overtook while this recheck was owed runs now too.
        if outcome == .notFound || selection.needsSearch { beginDiscovery() }
    }

    private func finish(_ operation: Finish.Operation, _ outcome: RuntimeSelection.Outcome) async {
        let released: [URL]
        if case .adopted = outcome {
            released = selection.takeWaitingFolders()
        } else {
            released = []
        }
        await onFinish(Finish(operation: operation, outcome: outcome, released: released))
    }
}

/// What Settings says while it has neither a runtime nor first-run steps to show, from
/// what is running now (`RuntimeView`). It says it is looking only while a search runs:
/// it said so whenever both were missing, so a choice rejected during the first search
/// left it looking forever.
public nonisolated enum RuntimeActivity: Equatable, Sendable {
    /// A search for `metab` is running.
    case searching
    /// A file chosen with Choose metab… is being checked.
    case checkingChoice
    /// A search found nothing, and the steps to install `metab` are being worked out.
    case preparingSteps
    /// Nothing is running: Find Again and Choose metab… are what remain.
    case idle

    public init(isSearching: Bool, isChoosing: Bool, isPreparingSteps: Bool) {
        self = isSearching ? .searching : isChoosing ? .checkingChoice : isPreparingSteps ? .preparingSteps : .idle
    }
}
