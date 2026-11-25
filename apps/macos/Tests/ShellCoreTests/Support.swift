import AppKit
import Darwin
import Foundation
import os
@testable import ShellCore

/// A child that prints what the test tells it to and exits when signaled.
nonisolated final class FakeProcess: ServerProcess, @unchecked Sendable {
    let pid: pid_t
    let lines: AsyncStream<String>
    private let sink: AsyncStream<String>.Continuation
    private let exit = Latch<Int32>()
    private let outputEnd = Latch<Void>()
    private let tail = OutputTail(limit: 200)
    private let ignoresTerm: Bool
    /// Stands in for a process in uninterruptible I/O, which not even SIGKILL ends.
    private let ignoresKill: Bool
    private let record = OSAllocatedUnfairLock(
        initialState: (signals: [Int32](), exitedBy: Int32?.none, released: false, signalsAfterRelease: [Int32]()))

    init(pid: pid_t = 4242, ignoresTerm: Bool = false, ignoresKill: Bool = false) {
        self.pid = pid
        self.ignoresTerm = ignoresTerm
        self.ignoresKill = ignoresKill
        (lines, sink) = AsyncStream.makeStream(bufferingPolicy: .bufferingNewest(200))
    }

    var signals: [Int32] { record.withLock { $0.signals } }
    var exitedBy: Int32? { record.withLock { $0.exitedBy } }
    /// Whether the supervisor gave up the pid, which for a real child is when it is reaped.
    var isReleased: Bool { record.withLock { $0.released } }
    /// Signals sent after `release()`: each could have reached an unrelated process group
    /// that took over the reaped pid.
    var signalsAfterRelease: [Int32] { record.withLock { $0.signalsAfterRelease } }
    var hasExited: Bool { exit.isResolved }

    func say(_ line: String) {
        written.withLock { $0 += line.utf8.count + 1 }
        tail.append(line)
        sink.yield(line)
    }

    /// Writes `text` where a real child's stderr goes, the log, which the app does not read
    /// line by line: it shows as `outputProgress`, as a clone's progress does, and its whole
    /// lines in `recentOutput()`, which a real child reads from the log.
    func writeToLog(_ text: String) {
        written.withLock { $0 += text.utf8.count }
        text.split(separator: "\n").forEach { tail.append(String($0)) }
    }

    private let written = OSAllocatedUnfairLock(initialState: 0)
    var outputProgress: Int { written.withLock { $0 } }

    /// Exits with `code`, as a crash or a startup error would.
    func exitOnItsOwn(code: Int32 = 1) {
        finishOutput()
        exit.resolve(code << 8)
    }

    func recentOutput() -> [String] { tail.snapshot }
    func waitForExit() async -> Int32? { await exit.wait() }
    func waitForOutputEnd() async -> Void? { await outputEnd.wait() }

    func signalGroup(_ signal: Int32) {
        let released = record.withLock { record in
            record.signals.append(signal)
            if record.released { record.signalsAfterRelease.append(signal) }
            return record.released
        }
        guard !released else { return }
        guard !exit.isResolved else { return }
        if (signal == SIGKILL && !ignoresKill) || (signal == SIGTERM && !ignoresTerm) {
            record.withLock { $0.exitedBy = signal }
            finishOutput()
            exit.resolve(signal)  // a wait status whose low bits name the signal
        }
    }

    func release() {
        record.withLock { $0.released = true }
    }

    private func finishOutput() {
        sink.finish()
        outputEnd.resolve(())
    }
}

/// A thread-safe counter and log for fakes called from @Sendable closures.
nonisolated final class Recorder<Value: Sendable>: Sendable {
    private let values = OSAllocatedUnfairLock(initialState: [Value]())
    func append(_ value: Value) { values.withLock { $0.append(value) } }
    var all: [Value] { values.withLock { $0 } }
    var count: Int { values.withLock { $0.count } }
}

/// The startup timeout of a start that a test expects to succeed. Nothing waits it out:
/// the fake child announces itself before the start and the probe answers at once. The
/// tests once used 2 seconds, which a stalled main actor reached before the first probe
/// on a loaded three-core CI runner, so a test went on from a failed start.
nonisolated let startupCeiling: Duration = .seconds(60)

/// Polls `condition` until it holds or `limit` passes.
///
/// The limit only stops a test that would otherwise hang, so it sits far above any
/// scheduling delay: every suite here runs on the main actor, which a loaded three-core
/// CI runner has stalled for over two seconds at a time.
func eventually(within limit: Duration = .seconds(30), _ condition: () -> Bool) async -> Bool {
    let clock = ContinuousClock()
    let deadline = clock.now.advanced(by: limit)
    while clock.now < deadline {
        if condition() { return true }
        try? await Task.sleep(for: .milliseconds(5))
    }
    return condition()
}

/// A fresh directory under the system temporary directory, canonicalized.
func temporaryDirectory(_ name: String = #function) throws -> URL {
    let base = URL(filePath: FileChecks.canonicalPath(FileManager.default.temporaryDirectory.path), directoryHint: .isDirectory)
    let safe = name.filter { $0.isLetter || $0.isNumber }
    let url = base.appending(path: "shellcore-\(safe)-\(UUID().uuidString.prefix(8))", directoryHint: .isDirectory)
    try FileManager.default.createDirectory(at: url, withIntermediateDirectories: true)
    return url
}

/// Gives this test process the SIGPIPE disposition that the app sets on its first line
/// (main.swift). The suites that drive WebKit call it as they start: at the default
/// disposition, loaded runs of the download tests died of SIGPIPE before the test's
/// server had written a byte, from a write elsewhere in this process.
///
/// Those suites also run in a process of their own (the `test` target in the app's
/// Makefile): WebKit's first web view blocks the main actor, which every suite here
/// shares, for seconds on a loaded runner.
func ignoreSIGPIPELikeTheApp() {
    signal(SIGPIPE, SIG_IGN)
}

/// Runs AppKit's event loop on the main thread from the first call on, as the app runs
/// it. A suite that puts one of the app's windows on screen calls it before the first
/// window exists.
///
/// AppKit's event thread takes each window-server event for this process and wakes the
/// main thread by stopping whatever run loop the main thread is in (HIToolbox's
/// `SignalMainThread` queues a `CFRunLoopStop` of the main run loop). In the app that is
/// the event wait inside `NSApplication.run`. In a test process with no event loop it is
/// the test runner's own (`CFMainExecutor.run`), whose return ends the run with status 0
/// and the remaining tests unrun: `exit` from `swift_task_asyncMainDrainQueue`. On
/// 2026-11-24 lldb caught that stop, queued from `_NSEventThread`'s
/// `PushToCGEventQueue`, ending runs of SettingsWindowTests after two to four of its
/// tests. Inside `NSApplication.run` the stop ends one wait for an event, as in the app,
/// and the main queue, where the suites' main-actor work runs, is served as before.
///
/// It starts from a run-loop block rather than from a test's own main-queue job, since a
/// run loop nested in a main-queue job does not serve the main queue, and it returns once
/// the block has run, from the runner's loop: a block left queued would run in the next
/// loop the main thread enters, such as the one a button's click runs, and never return
/// to it. A stop queued before the block runs would still end the runner's loop, so it
/// starts before any window does.
///
/// A suite that calls it runs in a test process of its own (`window_suites` in the app's
/// Makefile): its windows hold the main actor, which every suite shares, long enough on
/// a loaded machine that other suites' wall-clock bounds fail.
func runAppKitEventLoop() async {
    if let start = AppKitEventLoop.start { return await start.value }
    let start = Task {
        await withCheckedContinuation { (running: CheckedContinuation<Void, Never>) in
            let main = CFRunLoopGetMain()
            CFRunLoopPerformBlock(main, CFRunLoopMode.commonModes.rawValue) {
                // Resumed on the main queue, which the event loop serves.
                running.resume()
                NSApplication.shared.run()
            }
            CFRunLoopWakeUp(main)
        }
    }
    AppKitEventLoop.start = start
    await start.value
}

private enum AppKitEventLoop {
    static var start: Task<Void, Never>?
}

/// How long, in seconds, the background job of a group-signal test sleeps. It must
/// outlive `eventually`'s limit by a wide margin: a job that expired on its own during
/// the poll would pass a check that the signal under test killed it. A test that owns the
/// job's leader also kills the group on the way out, so a signal that misses the job
/// leaves nothing running.
nonisolated let survivorSeconds = 600

func processExists(_ pid: pid_t) -> Bool {
    kill(pid, 0) == 0 || errno == EPERM
}

/// Runs `body` against a started server and stops the server however `body` ends: on
/// return, on a thrown error, and on cancellation, which URLSession reports as an
/// error. Neither the supervisor nor `SpawnedProcess` ends a child on deallocation, so a
/// test that skipped the stop would leave its server running.
func stoppingAfterward<T>(_ server: ServerSupervisor, _ body: () async throws -> T) async throws -> T {
    let result: T
    do {
        result = try await body()
    } catch {
        await server.stop()
        throw error
    }
    await server.stop()
    return result
}
