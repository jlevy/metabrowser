import Darwin
import Foundation
import os

/// What the supervisor needs from a running child. Tests substitute a fake.
public nonisolated protocol ServerProcess: AnyObject, Sendable {
    var pid: pid_t { get }
    /// Output lines, stdout and stderr interleaved as written. Finishes at EOF.
    /// Iterate it from one task only.
    var lines: AsyncStream<String> { get }
    /// The newest output lines, for the error view.
    func recentOutput() -> [String]
    /// The wait status once the child has exited, or nil if the waiting task was
    /// cancelled first. The exited child is not reaped yet: it keeps its pid, and so its
    /// process group id, until `release()`.
    func waitForExit() async -> Int32?
    /// Whether `waitForExit()` would return at once.
    var hasExited: Bool { get }
    /// Returns once every holder of the output pipe has closed it, or nil if cancelled.
    func waitForOutputEnd() async -> Void?
    /// Sends `signal` to the child's whole process group, until `release()`.
    func signalGroup(_ signal: Int32)
    /// Gives up the child's pid: reaps it now if `waitForExit()` has returned, or else as
    /// soon as the child's exit is observed.
    /// Once a child is reaped and its group is empty, the kernel can hand the same id to
    /// an unrelated process group, so `signalGroup` does nothing after this.
    func release()
}

/// One child to start: everything is explicit, nothing is inherited.
public nonisolated struct LaunchSpec: Equatable, Sendable {
    public var executable: String
    public var arguments: [String]
    public var environment: [String: String]
    public var workingDirectory: String?
    /// Written as the first line of the child's stdin.
    public var stdinLine: String?
    /// Close stdin after `stdinLine`, so the child reads EOF (one-shot commands).
    /// A server's stdin stays open as a lifeline: the kernel closes it however this
    /// app exits.
    public var closesStdin: Bool
    /// Output is appended here, created mode 0600 if missing.
    public var logURL: URL?
    /// How many lines `ServerProcess.recentOutput()` keeps.
    public var tailLimit: Int

    public init(
        executable: String, arguments: [String] = [], environment: [String: String] = [:],
        workingDirectory: String? = nil, stdinLine: String? = nil, closesStdin: Bool = false,
        logURL: URL? = nil, tailLimit: Int = 200
    ) {
        self.executable = executable
        self.arguments = arguments
        self.environment = environment
        self.workingDirectory = workingDirectory
        self.stdinLine = stdinLine
        self.closesStdin = closesStdin
        self.logURL = logURL
        self.tailLimit = tailLimit
    }

    /// The command line as one string, for logs.
    public var commandLine: String {
        ([executable] + arguments).map(Self.quoted).joined(separator: " ")
    }

    static func quoted(_ word: String) -> String {
        let plain = word.allSatisfy { $0.isLetter || $0.isNumber || "/._-:=+@,".contains($0) }
        return plain && !word.isEmpty ? word : "'" + word.replacingOccurrences(of: "'", with: #"'\''"#) + "'"
    }
}

public nonisolated enum SpawnError: Error, Equatable, CustomStringConvertible {
    case relativeExecutable(String)
    case pipe(Int32)
    case spawn(Int32)

    public var description: String {
        switch self {
        case .relativeExecutable(let path): "\(path) is not an absolute path"
        case .pipe(let code): "could not create a pipe: \(String(cString: strerror(code)))"
        case .spawn(let code): String(cString: strerror(code))
        }
    }
}

/// A child started with `posix_spawn` in its own process group.
///
/// - `POSIX_SPAWN_SETPGROUP` with pgroup 0 makes the child a group leader, so one
///   `kill(-pid, …)` reaches every descendant that stays in the group.
/// - `POSIX_SPAWN_CLOEXEC_DEFAULT` closes every descriptor the file actions do not
///   name. Without it the child inherits the write end of its own stdin pipe and
///   never sees EOF, and every other child's pipes leak into it.
/// - `POSIX_SPAWN_SETSIGDEF` and `POSIX_SPAWN_SETSIGMASK` give the child default
///   signal handling, since this app ignores `SIGPIPE` and handles `SIGTERM`.
public nonisolated final class SpawnedProcess: ServerProcess, @unchecked Sendable {
    public let pid: pid_t
    public let lines: AsyncStream<String>
    private let lifeline: FileHandle?  // write end of the child's stdin
    private let output: FileHandle  // must outlive init, or its descriptor closes
    private let exit = Latch<Int32>()
    private let outputEnd = Latch<Void>()
    private let tail: OutputTail
    private let exitSource: DispatchSourceProcess
    private let ownership: ChildOwnership

    public init(_ spec: LaunchSpec) throws(SpawnError) {
        // posix_spawn resolves a relative path after the working-directory change, so
        // `metab` could otherwise name a file inside the folder being served.
        guard spec.executable.hasPrefix("/") else { throw .relativeExecutable(spec.executable) }
        var stdinPipe: [Int32] = [-1, -1]
        var outputPipe: [Int32] = [-1, -1]
        guard pipe(&stdinPipe) == 0 else { throw .pipe(errno) }
        guard pipe(&outputPipe) == 0 else {
            close(stdinPipe[0])
            close(stdinPipe[1])
            throw .pipe(errno)
        }
        // This app's ends must not leak into any other child it starts.
        _ = fcntl(stdinPipe[1], F_SETFD, FD_CLOEXEC)
        _ = fcntl(outputPipe[0], F_SETFD, FD_CLOEXEC)

        var attr: posix_spawnattr_t?
        posix_spawnattr_init(&attr)
        defer { posix_spawnattr_destroy(&attr) }
        let flags = POSIX_SPAWN_SETPGROUP | POSIX_SPAWN_CLOEXEC_DEFAULT
            | POSIX_SPAWN_SETSIGDEF | POSIX_SPAWN_SETSIGMASK
        posix_spawnattr_setflags(&attr, Int16(flags))
        posix_spawnattr_setpgroup(&attr, 0)
        var defaults = sigset_t()
        sigemptyset(&defaults)
        for signal in [SIGPIPE, SIGTERM, SIGINT, SIGHUP] { sigaddset(&defaults, signal) }
        posix_spawnattr_setsigdefault(&attr, &defaults)
        var empty = sigset_t()
        sigemptyset(&empty)
        posix_spawnattr_setsigmask(&attr, &empty)

        var actions: posix_spawn_file_actions_t?
        posix_spawn_file_actions_init(&actions)
        defer { posix_spawn_file_actions_destroy(&actions) }
        posix_spawn_file_actions_adddup2(&actions, stdinPipe[0], 0)
        posix_spawn_file_actions_adddup2(&actions, outputPipe[1], 1)
        posix_spawn_file_actions_adddup2(&actions, outputPipe[1], 2)
        if let directory = spec.workingDirectory {
            posix_spawn_file_actions_addchdir_np(&actions, directory)
        }

        let argv = ([spec.executable] + spec.arguments).map { strdup($0) } + [nil]
        let envp = spec.environment.sorted { $0.key < $1.key }
            .map { strdup("\($0.key)=\($0.value)") } + [nil]
        defer { (argv + envp).forEach { free($0) } }

        var spawned: pid_t = 0
        let rc = posix_spawn(&spawned, spec.executable, &actions, &attr, argv, envp)
        close(stdinPipe[0])
        close(outputPipe[1])
        guard rc == 0 else {
            close(stdinPipe[1])
            close(outputPipe[0])
            throw .spawn(rc)
        }
        let child = spawned  // immutable, so @Sendable closures can capture it
        pid = child

        let stdinHandle = FileHandle(fileDescriptor: stdinPipe[1], closeOnDealloc: true)
        if let line = spec.stdinLine {
            try? stdinHandle.write(contentsOf: Data((line + "\n").utf8))
        }
        if spec.closesStdin {
            try? stdinHandle.close()
            lifeline = nil
        } else {
            lifeline = stdinHandle
        }

        let tail = OutputTail(limit: spec.tailLimit)
        self.tail = tail
        let (lineStream, lineSink) = AsyncStream<String>.makeStream(
            bufferingPolicy: .bufferingNewest(spec.tailLimit))
        lines = lineStream
        let log = spec.logURL.flatMap(Self.openLog)
        let splitter = LineSplitter()
        let ended = outputEnd
        let reader = FileHandle(fileDescriptor: outputPipe[0], closeOnDealloc: true)
        output = reader
        reader.readabilityHandler = { handle in
            let chunk = handle.availableData
            let emit: (String) -> Void = { line in
                tail.append(line)
                lineSink.yield(line)
            }
            guard !chunk.isEmpty else {  // EOF: the child and every descendant closed it
                handle.readabilityHandler = nil
                splitter.finish(emit: emit)
                lineSink.finish()
                ended.resolve(())
                return
            }
            try? log?.write(contentsOf: chunk)
            splitter.append(chunk, emit: emit)
        }

        // kqueue EVFILT_PROC with NOTE_EXIT, then read the status with WNOWAIT, which
        // leaves the child a zombie: its pid, and so its group id, stays this child's
        // while the stop sweeps the group, and `release()` reaps it afterwards.
        //
        // NOTE_EXIT can arrive before the exited child is waitable, and it arrives once,
        // so the event handler waits for the child to become waitable. The first look,
        // for a child that exited before the source was armed, must not wait: the child
        // may run for hours.
        let latch = exit
        let ownership = ChildOwnership(pid: child)
        self.ownership = ownership
        let source = DispatchSource.makeProcessSource(
            identifier: child, eventMask: .exit, queue: .global())
        let observe: @Sendable (_ waiting: Bool) -> Void = { waiting in
            guard !latch.isResolved, let status = Self.observedExit(of: child, waiting: waiting) else { return }
            ownership.exited { latch.resolve(status) }
            source.cancel()
        }
        source.setEventHandler { observe(true) }
        source.resume()
        exitSource = source
        DispatchQueue.global().async { observe(false) }  // it may have exited before arming
    }

    /// A child nobody released, such as one a test spawned, is reaped when it exits.
    deinit { ownership.release() }

    public func recentOutput() -> [String] { tail.snapshot }
    public func waitForExit() async -> Int32? { await exit.wait() }
    public func waitForOutputEnd() async -> Void? { await outputEnd.wait() }
    public var hasExited: Bool { exit.isResolved }

    public func signalGroup(_ signal: Int32) {
        ownership.signalGroup(signal)
    }

    public func release() {
        ownership.release()
    }

    /// The wait status of `child` once it has exited, read with `WNOWAIT`, so the child
    /// stays unreaped. Unless `waiting`, nil while the child runs; when `waiting`, the call
    /// returns once the child is waitable, which closely follows NOTE_EXIT. Nil, too, if
    /// `child` is no longer this process's to wait for.
    static func observedExit(of child: pid_t, waiting: Bool) -> Int32? {
        var info = siginfo_t()
        let options = WEXITED | WNOWAIT | (waiting ? 0 : WNOHANG)
        while waitid(P_PID, id_t(child), &info, options) != 0 {
            guard errno == EINTR else { return nil }
        }
        return info.si_pid == child ? waitStatus(info) : nil
    }

    /// `waitid`'s account of an exit as the `waitpid` status `ExitStatus` decodes.
    static func waitStatus(_ info: siginfo_t) -> Int32 {
        switch info.si_code {
        case CLD_EXITED: (info.si_status & 0xff) << 8
        case CLD_DUMPED: (info.si_status & 0x7f) | 0x80
        default: info.si_status & 0x7f  // CLD_KILLED
        }
    }

    /// What the kernel does for a child if this app crashes: the child reads EOF.
    public func closeLifeline() {
        try? lifeline?.close()
    }

    /// Appends, never truncates, and refuses to follow a symlink planted at the path.
    private static func openLog(_ url: URL) -> FileHandle? {
        let fd = open(url.path, O_WRONLY | O_APPEND | O_CREAT | O_NOFOLLOW | O_CLOEXEC, 0o600)
        guard fd >= 0 else { return nil }
        return FileHandle(fileDescriptor: fd, closeOnDealloc: true)
    }
}

/// Whether a `SpawnedProcess` still holds its child's pid, which is also the id of the
/// child's process group.
///
/// The exit handler only observes the exit (`waitid` with `WNOWAIT`), so the exited
/// leader stays a zombie that keeps its pid reserved, and with it the group id: a
/// `kill(-pid, …)` meanwhile reaches the child's own group and nothing else, even after
/// the leader exits while descendants remain. Reaping happens only once the owner has
/// released the child and the child has exited, and signals stop at reaping, under one
/// lock, so no signal can follow the reap.
nonisolated final class ChildOwnership: Sendable {
    private struct State {
        var exited = false
        var released = false
        var reaped = false
    }

    private let pid: pid_t
    private let state = OSAllocatedUnfairLock(initialState: State())
    private let sendToGroup: @Sendable (pid_t, Int32) -> Void
    private let reapZombie: @Sendable (pid_t) -> Void

    /// `sendToGroup` and `reapZombie` are the two system calls whose order ownership
    /// decides; tests record them instead.
    init(
        pid: pid_t,
        sendToGroup: @escaping @Sendable (pid_t, Int32) -> Void = { pid, signal in _ = kill(-pid, signal) },
        reapZombie: @escaping @Sendable (pid_t) -> Void = { pid in
            var status: Int32 = 0
            _ = waitpid(pid, &status, 0)  // a zombie: returns at once
        }
    ) {
        self.pid = pid
        self.sendToGroup = sendToGroup
        self.reapZombie = reapZombie
    }

    var isReaped: Bool { state.withLock { $0.reaped } }

    func signalGroup(_ signal: Int32) {
        state.withLock { state in
            guard !state.reaped else { return }
            sendToGroup(pid, signal)
        }
    }

    /// The exit handler saw the child exit, and `announce` resumes the exit waiters.
    /// The exit is recorded, and the child reaped if it is already released, before
    /// `announce` runs: a waiter that releases the child the moment `waitForExit()`
    /// returns then reaps it at once, and no later signal reaches its group.
    func exited(announce: () -> Void) {
        state.withLock { state in
            state.exited = true
            reapIfDone(&state)
        }
        announce()
    }

    func release() {
        state.withLock { state in
            state.released = true
            reapIfDone(&state)
        }
    }

    private func reapIfDone(_ state: inout State) {
        guard state.exited, state.released, !state.reaped else { return }
        reapZombie(pid)
        state.reaped = true
    }
}
