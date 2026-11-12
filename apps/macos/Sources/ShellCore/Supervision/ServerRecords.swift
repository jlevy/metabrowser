import Darwin
import Foundation
import os

/// When a process started, as the kernel records it. A pid alone does not name a
/// process: once one exits and is reaped, the kernel can give its pid to another.
public nonisolated struct ProcessStart: Codable, Equatable, Sendable {
    public var seconds: Int64
    public var microseconds: Int32

    public init(seconds: Int64, microseconds: Int32) {
        self.seconds = seconds
        self.microseconds = microseconds
    }
}

/// What tells one process from another that later got its pid: when it started, and the
/// process group it leads.
public nonisolated struct ProcessIdentity: Codable, Equatable, Sendable {
    public var start: ProcessStart
    public var group: pid_t

    public init(start: ProcessStart, group: pid_t) {
        self.start = start
        self.group = group
    }
}

/// What the records and the reaper ask of the system. Tests substitute both fields.
public nonisolated struct ProcessTable: Sendable {
    /// The identity of the running process with `pid`, or nil if there is none. A zombie
    /// counts as none: it runs nothing, and its parent holds its pid.
    public var lookup: @Sendable (pid_t) -> ProcessIdentity?
    public var signalGroup: @Sendable (pid_t, Int32) -> Void

    public init(
        lookup: @escaping @Sendable (pid_t) -> ProcessIdentity?, signalGroup: @escaping @Sendable (pid_t, Int32) -> Void
    ) {
        self.lookup = lookup
        self.signalGroup = signalGroup
    }

    public static let live = ProcessTable(lookup: liveLookup, signalGroup: { kill(-$0, $1) })

    /// `sysctl` `KERN_PROC_PID`: the start time and group of one process.
    static func liveLookup(_ pid: pid_t) -> ProcessIdentity? {
        var info = kinfo_proc()
        var size = MemoryLayout<kinfo_proc>.stride
        var name: [Int32] = [CTL_KERN, KERN_PROC, KERN_PROC_PID, pid]
        guard sysctl(&name, u_int(name.count), &info, &size, nil, 0) == 0, size > 0,
              info.kp_proc.p_pid == pid, Int32(info.kp_proc.p_stat) != SZOMB
        else { return nil }
        let started = info.kp_proc.p_un.__p_starttime
        return ProcessIdentity(
            start: ProcessStart(seconds: Int64(started.tv_sec), microseconds: Int32(started.tv_usec)),
            group: info.kp_eproc.e_pgid)
    }
}

/// One server this app started and has not yet seen exit.
public nonisolated struct ServerRecord: Codable, Equatable, Sendable {
    public var pid: pid_t
    public var identity: ProcessIdentity
    /// The folder it serves, for the logs.
    public var root: String

    public init(pid: pid_t, identity: ProcessIdentity, root: String) {
        self.pid = pid
        self.identity = identity
        self.root = root
    }
}

/// One running app process: whose records a file holds.
public nonisolated struct AppOwner: Codable, Equatable, Sendable {
    public var pid: pid_t
    public var identity: ProcessIdentity

    public init(pid: pid_t, identity: ProcessIdentity) {
        self.pid = pid
        self.identity = identity
    }

    /// This process. The kernel always describes a process to itself.
    public static func current(table: ProcessTable = .live) -> AppOwner {
        guard let identity = table.lookup(getpid()) else { preconditionFailure("sysctl did not describe this process") }
        return AppOwner(pid: getpid(), identity: identity)
    }
}

/// The servers each app process has running, so the next launch can end those that a
/// crashed or force-quit app left behind (`OrphanReaper`). Host mode's exit on stdin EOF
/// will make this unnecessary.
///
/// Each app process keeps its own owner-only file, `app-<pid>.json`, in a `servers`
/// folder of the variant's Application Support folder, naming the process that owns it.
/// So a second copy of the app with the same bundle identifier, such as a development
/// build run from another checkout, never takes the first one's live servers for
/// orphans: a file is an orphan's only once its owner is no longer running.
///
/// A server is added once it has spawned and removed once it has exited; every change
/// rewrites the file whole (`AtomicFile`), and the last removal deletes it. Thread-safe,
/// since a child that outlives its stop is forgotten whenever it exits.
public nonisolated final class ServerRecords: Sendable {
    private struct Contents: Codable {
        var owner: AppOwner
        var servers: [ServerRecord]
    }

    /// Far more than a run's records, and the bound on what a launch reads of each file.
    static let byteLimit = 256 * 1024
    /// The most files a launch reads; more than that are not this app's to have made.
    static let fileLimit = 64

    public let directory: URL
    /// This process's file.
    public let file: URL
    /// The servers of app processes no longer running: what a launch reaps.
    public let orphans: [ServerRecord]
    private let owner: AppOwner
    private let orphanFiles: [URL]
    private let records = OSAllocatedUnfairLock(initialState: [ServerRecord]())
    /// Told about a file that cannot be read or saved. Neither stops a server: without
    /// its record, only the cleanup after a crash is lost.
    private let onError: @Sendable (String) -> Void

    public init(
        directory: URL, owner: AppOwner = .current(), table: ProcessTable = .live,
        onError: @escaping @Sendable (String) -> Void
    ) {
        self.directory = directory
        self.owner = owner
        self.onError = onError
        file = directory.appending(path: "app-\(owner.pid).json")
        let (orphans, files) = Self.loadOrphans(in: directory, except: file, table: table, onError: onError)
        self.orphans = orphans
        orphanFiles = files
    }

    /// This process's records.
    public var all: [ServerRecord] { records.withLock { $0 } }

    public func add(_ record: ServerRecord) {
        update { $0.append(record) }
    }

    public func forget(_ gone: [ServerRecord]) {
        update { $0.removeAll { gone.contains($0) } }
    }

    /// After a reap: the orphans' files go, and any orphan still running becomes this
    /// process's, so the next launch tries again.
    public func settleOrphans(_ outcomes: [OrphanReaper.Outcome]) {
        let survivors = outcomes.compactMap { if case .survived(let record) = $0 { record } else { nil } }
        if !survivors.isEmpty { update { $0 += survivors } }
        for orphanFile in orphanFiles where unlink(orphanFile.path(percentEncoded: false)) != 0 && errno != ENOENT {
            onError("could not remove the server records \(orphanFile.path(percentEncoded: false)): \(String(cString: strerror(errno)))")
        }
    }

    /// `makeProcess`, with each child recorded while it runs.
    public func recording(
        table: ProcessTable = .live, _ makeProcess: @escaping ServerSupervisor.ProcessFactory
    ) -> ServerSupervisor.ProcessFactory {
        { [self] spec in
            let child = try makeProcess(spec)
            // A child that is already gone needs no cleanup, and has no start time to read.
            guard let identity = table.lookup(child.pid) else { return child }
            let record = ServerRecord(pid: child.pid, identity: identity, root: spec.workingDirectory ?? "")
            add(record)
            return RecordedProcess(child) { [self] in forget([record]) }
        }
    }

    private func update(_ change: (inout [ServerRecord]) -> Void) {
        let failure: String? = records.withLockUnchecked { records in
            change(&records)
            let path = file.path(percentEncoded: false)
            guard !records.isEmpty else {
                return unlink(path) == 0 || errno == ENOENT
                    ? nil : "could not remove the server records \(path): \(String(cString: strerror(errno)))"
            }
            do {
                let data = try JSONEncoder.records.encode(Contents(owner: owner, servers: records))
                try AtomicFile.write(data, to: file)
                return nil
            } catch {
                return "could not save the server records \(error)"
            }
        }
        if let failure { onError(failure) }
    }

    /// The records in every other file whose owner is no longer running, and those files.
    private static func loadOrphans(
        in directory: URL, except own: URL, table: ProcessTable, onError: (String) -> Void
    ) -> ([ServerRecord], [URL]) {
        let names: [String]
        do {
            names = try FileManager.default.contentsOfDirectory(atPath: directory.path(percentEncoded: false))
                .filter { $0.hasPrefix("app-") && $0.hasSuffix(".json") }.sorted()
        } catch let error as CocoaError where error.code == .fileReadNoSuchFile {
            return ([], [])
        } catch {
            onError("could not read the server records in \(directory.path(percentEncoded: false)): \(error)")
            return ([], [])
        }
        if names.count > fileLimit {
            onError("\(directory.path(percentEncoded: false)) holds \(names.count) server records files; reading \(fileLimit)")
        }
        var orphans: [ServerRecord] = []
        var files: [URL] = []
        for name in names.prefix(fileLimit) {
            let url = directory.appending(path: name)
            guard url != own, let contents = read(url, onError: onError) else { continue }
            if table.lookup(contents.owner.pid) == contents.owner.identity { continue }  // a live app's
            orphans += contents.servers
            files.append(url)
        }
        return (orphans, files)
    }

    private static func read(_ url: URL, onError: (String) -> Void) -> Contents? {
        let path = url.path(percentEncoded: false)
        var info = stat()
        guard lstat(path, &info) == 0, info.st_mode & S_IFMT == S_IFREG else {
            onError("could not read the server records \(path): not a file")
            return nil
        }
        guard Int(info.st_size) <= byteLimit else {
            onError("could not read the server records \(path): \(info.st_size) bytes is too many")
            return nil
        }
        do {
            return try JSONDecoder().decode(Contents.self, from: Data(contentsOf: url))
        } catch {
            onError("could not read the server records \(path): \(error)")
            return nil
        }
    }
}

extension JSONEncoder {
    /// Stable and readable, for a file a person may open.
    fileprivate nonisolated static var records: JSONEncoder {
        let encoder = JSONEncoder()
        encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
        return encoder
    }
}

/// A recorded child: everything goes to the child, and its record is forgotten once the
/// supervisor has released it and it has exited. A child released while it still runs
/// (one given up on in uninterruptible I/O) stays recorded until it exits, so a later
/// launch can still end it.
nonisolated final class RecordedProcess: ServerProcess, @unchecked Sendable {
    private let child: any ServerProcess
    private let forget: @Sendable () -> Void

    init(_ child: any ServerProcess, forget: @escaping @Sendable () -> Void) {
        self.child = child
        self.forget = forget
    }

    var pid: pid_t { child.pid }
    var lines: AsyncStream<String> { child.lines }
    var hasExited: Bool { child.hasExited }
    func recentOutput() -> [String] { child.recentOutput() }
    func waitForExit() async -> Int32? { await child.waitForExit() }
    func waitForOutputEnd() async -> Void? { await child.waitForOutputEnd() }
    func signalGroup(_ signal: Int32) { child.signalGroup(signal) }

    func release() {
        child.release()
        if child.hasExited { return forget() }
        let child = child
        let forget = forget
        Task.detached {
            guard await child.waitForExit() != nil else { return }
            forget()
        }
    }
}

/// Ends the servers a previous run left, at launch.
///
/// A record's group is signaled only while its leader still has the recorded start time
/// and group, checked before each signal, so a pid the kernel has since given to another
/// process is never signaled. A group whose leader has exited is not signaled either,
/// for the same reason: nothing holds its id for this app any more.
public nonisolated enum OrphanReaper {
    public enum Outcome: Equatable, Sendable {
        /// It exited after SIGTERM.
        case stopped(ServerRecord)
        /// It needed SIGKILL.
        case killed(ServerRecord)
        /// It outlasted SIGKILL (uninterruptible I/O); the next launch tries again.
        case survived(ServerRecord)
        /// No process has its pid, or another process does now.
        case gone(ServerRecord)

        public var record: ServerRecord {
            switch self {
            case .stopped(let record), .killed(let record), .survived(let record), .gone(let record): record
            }
        }

        /// What happened, for the logs.
        public var summary: String {
            let server = "server pid \(record.pid) for \(record.root), which an app that did not quit left running"
            return switch self {
            case .stopped: "ended the \(server), with SIGTERM"
            case .killed: "ended the \(server), with SIGKILL after SIGTERM"
            case .survived: "the \(server) outlasted SIGKILL (uninterruptible I/O?); the next launch tries again"
            case .gone: "server pid \(record.pid) for \(record.root) had already exited"
            }
        }
    }

    /// As long as an orderly stop gives a server (`SupervisorPolicy.shutdownGrace`).
    public static let grace: Duration = .seconds(5)
    /// As long as an orderly stop waits after SIGKILL (`SupervisorPolicy.killWait`).
    public static let killWait: Duration = .seconds(2)
    static let pollInterval: Duration = .milliseconds(50)

    public static func reap(
        _ records: [ServerRecord], table: ProcessTable, grace: Duration = grace, killWait: Duration = killWait
    ) async -> [Outcome] {
        func matches(_ record: ServerRecord) -> Bool { table.lookup(record.pid) == record.identity }
        let owned = records.filter(matches)
        owned.forEach { table.signalGroup($0.identity.group, SIGTERM) }
        let stubborn = await waitForExit(owned, within: grace, matches: matches).filter(matches)
        stubborn.forEach { table.signalGroup($0.identity.group, SIGKILL) }
        let survivors = await waitForExit(stubborn, within: killWait, matches: matches)
        return records.map { record in
            if !owned.contains(record) { return .gone(record) }
            if !stubborn.contains(record) { return .stopped(record) }
            return survivors.contains(record) ? .survived(record) : .killed(record)
        }
    }

    /// Those of `records` still running once all have exited or `limit` has passed.
    private static func waitForExit(
        _ records: [ServerRecord], within limit: Duration, matches: (ServerRecord) -> Bool
    ) async -> [ServerRecord] {
        let clock = ContinuousClock()
        let deadline = clock.now.advanced(by: limit)
        var running = records.filter(matches)
        while !running.isEmpty, clock.now < deadline {
            try? await Task.sleep(for: pollInterval)  // cancelled: the launch is ending
            running = running.filter(matches)
        }
        return running
    }
}
