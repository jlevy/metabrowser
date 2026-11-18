import Darwin
import Foundation
import os
import Testing
@testable import ShellCore

private let repository = SessionRoot.repository(URL(string: "https://github.com/jlevy/tbd")!)

@Suite struct StartupDeadlineTests {
    private let spawn = ContinuousClock.now

    private func at(_ seconds: Int) -> ContinuousClock.Instant { spawn.advanced(by: .seconds(seconds)) }

    /// A folder's start: output moves nothing.
    @Test func withoutALimitTheDeadlineRunsFromTheSpawn() {
        var deadline = StartupDeadline(quiet: .seconds(60), limit: nil, spawned: spawn)
        deadline.observe(written: 100, at: at(50))
        #expect(deadline.expiry == at(60))
        #expect(deadline.expired(at: at(59)) == nil)
        #expect(deadline.expired(at: at(60)) == .quiet)
        #expect(deadline.longest == .seconds(60))
    }

    @Test func withALimitNewOutputStartsTheQuietPeriodAgain() {
        var deadline = StartupDeadline(quiet: .seconds(60), limit: .seconds(2040), spawned: spawn, written: 7)
        #expect(deadline.expiry == at(60))
        deadline.observe(written: 7, at: at(30))  // the count it started with: nothing new
        #expect(deadline.expiry == at(60))
        deadline.observe(written: 90, at: at(50))
        #expect(deadline.expiry == at(110))
        #expect(deadline.expired(at: at(109)) == nil)
        #expect(deadline.expired(at: at(110)) == .quiet)
        #expect(deadline.longest == .seconds(2040))
    }

    /// A clone writes a line every `MetabAcquisition.progressLineInterval`, so its start
    /// lasts until the limit, and no longer.
    @Test func aStartThatKeepsWritingEndsAtTheLimit() {
        var deadline = StartupDeadline(quiet: .seconds(60), limit: .seconds(2040), spawned: spawn)
        let interval = Int(MetabAcquisition.progressLineInterval.components.seconds)
        for second in stride(from: interval, through: 2100, by: interval) {
            #expect(deadline.expired(at: at(second)) == (second >= 2040 ? .limit : nil))
            deadline.observe(written: second, at: at(second))
        }
        #expect(deadline.expiry == at(2040))
    }

    @Test func theAnnouncementCountsAsOutput() {
        var deadline = StartupDeadline(quiet: .seconds(60), limit: .seconds(2040), spawned: spawn)
        deadline.noteOutput(at: at(600))
        #expect(deadline.expiry == at(660))
        var folder = StartupDeadline(quiet: .seconds(60), limit: nil, spawned: spawn)
        folder.noteOutput(at: at(30))
        #expect(folder.expiry == at(60))
    }

    @Test func eachSummarySaysWhichBoundEndedTheStart() {
        let folder = StartupDeadline(quiet: .seconds(60), limit: nil, spawned: spawn)
        let clone = StartupDeadline(quiet: .seconds(60), limit: .seconds(2040), spawned: spawn)
        let what = "announce its address"
        #expect(folder.summary(.quiet, waitingFor: what) == "The server did not announce its address within 60.0 seconds.")
        #expect(clone.summary(.quiet, waitingFor: what) == "The server wrote nothing for 60.0 seconds and did not announce its address.")
        #expect(clone.summary(.limit, waitingFor: what) == "The server did not announce its address within 2040.0 seconds, though it was still writing.")
        #expect(clone.summary(.quiet, waitingFor: "answer it", announced: true) == "The server did not answer it within 60.0 seconds of announcing its address.")
        #expect(clone.summary(.limit, waitingFor: "answer it", announced: true) == "The server did not answer it within 2040.0 seconds.")
    }

    @Test func aRepositoryStartsUnderTheLimitAndAFolderUnderNone() {
        #expect(MetabAcquisition.reservationWait == .seconds(1980))
        #expect(SupervisorPolicy.repositoryStartupLimit == .seconds(2040))
        #expect(SupervisorPolicy.serving(repository).startupLimit == .seconds(2040))
        #expect(SupervisorPolicy.serving(.folder(URL(filePath: "/tmp/notes"))).startupLimit == nil)
        // The quiet period lets five lines of a clone's progress go missing.
        #expect(SupervisorPolicy().startupTimeout == MetabAcquisition.progressLineInterval * 6)
    }
}

/// Writes to a fake child's log on a thread of its own, every `interval`, until stopped:
/// a thread, not a task, so a starved task pool, which runs the start's watch, cannot also
/// hold back the progress the watch looks for.
private final class LogWriter: Sendable {
    private let stopped = OSAllocatedUnfairLock(initialState: false)

    init(_ child: FakeProcess, every interval: Duration) {
        let stopped = self.stopped
        let micros = useconds_t(interval / .microseconds(1))
        Thread.detachNewThread {
            while !stopped.withLock({ $0 }) {
                child.writeToLog("cloning https://github.com/jlevy/tbd: receiving objects: 45%\n")
                usleep(micros)
            }
        }
    }

    func stop() { stopped.withLock { $0 = true } }
}

/// The supervisor with a `StartupDeadline`: a start that keeps writing is not abandoned at
/// `startupTimeout`, one that goes quiet is, and so is one that writes past its limit.
@Suite struct RepositoryStartupTests {
    private let servingLine = "Serving https://github.com/jlevy/tbd at http://127.0.0.1:8443/pull/12"

    private func policy(quiet: Duration, limit: Duration?) -> SupervisorPolicy {
        var policy = SupervisorPolicy()
        policy.startupTimeout = quiet
        policy.startupLimit = limit
        policy.progressInterval = .milliseconds(20)
        policy.shutdownGrace = .milliseconds(100)
        policy.probeInterval = .milliseconds(5)
        policy.outputSettle = .milliseconds(50)
        return policy
    }

    private func supervisor(
        _ child: FakeProcess, _ policy: SupervisorPolicy, probe: @escaping ServerSupervisor.ReadinessProbe = { _ in true }
    ) -> ServerSupervisor {
        ServerSupervisor(
            spec: LaunchSpec(executable: "/usr/bin/false"), launch: CLIServeLaunch(), policy: policy,
            makeProcess: { _ in child }, probe: probe)
    }

    private func failure(_ subject: ServerSupervisor) -> ServerFailure? {
        if case .failed(let failure) = subject.state { return failure }
        Issue.record("expected a failure, got \(subject.state)")
        return nil
    }

    /// The defect this guards against: every start was abandoned 60 s after its spawn, so a
    /// first clone that took longer was killed while it was still receiving objects.
    @Test func aStartThatKeepsWritingOutlastsItsQuietPeriod() async throws {
        let child = FakeProcess()
        let subject = supervisor(child, policy(quiet: .seconds(1), limit: .seconds(60)))
        let writer = LogWriter(child, every: .milliseconds(50))
        defer { writer.stop() }
        let started = Task { await subject.start() }
        try await Task.sleep(for: .milliseconds(2500))  // more than twice the quiet period
        #expect(subject.state == .starting)
        #expect(child.signals.isEmpty)
        child.say(servingLine)
        await started.value
        guard case .ready(let endpoint) = subject.state else {
            Issue.record("expected ready, got \(subject.state)")
            return
        }
        #expect(endpoint.entryURL.absoluteString == "http://127.0.0.1:8443/pull/12")
        await subject.stop()
    }

    @Test func aStartThatGoesQuietIsGivenUpOnLongBeforeItsLimit() async {
        let child = FakeProcess()
        let subject = supervisor(child, policy(quiet: .milliseconds(300), limit: .seconds(600)))
        child.writeToLog("cloning https://github.com/jlevy/tbd into ~/.cache/metabrowser\n")
        let clock = ContinuousClock()
        let began = clock.now
        await subject.start()
        #expect(began.duration(to: clock.now) < .seconds(300))
        #expect(failure(subject)?.summary == "The server wrote nothing for 0.3 seconds and did not announce its address.")
        #expect(child.signals.first == SIGTERM)
    }

    @Test func aStartThatWritesPastItsLimitIsGivenUpOn() async {
        let child = FakeProcess()
        let subject = supervisor(child, policy(quiet: .seconds(30), limit: .milliseconds(500)))
        let writer = LogWriter(child, every: .milliseconds(20))
        defer { writer.stop() }
        await subject.start()
        #expect(failure(subject)?.summary == "The server did not announce its address within 0.5 seconds, though it was still writing.")
    }

    /// A folder's start is bounded from its spawn, whatever it writes.
    @Test func aFoldersStartIsNotExtendedByOutput() async {
        let child = FakeProcess()
        let subject = supervisor(child, policy(quiet: .milliseconds(300), limit: nil))
        let writer = LogWriter(child, every: .milliseconds(20))
        defer { writer.stop() }
        await subject.start()
        #expect(failure(subject)?.summary == "The server did not announce its address within 0.3 seconds.")
    }

    @Test func anAnnouncedServerThatNeverAnswersIsGivenUpOnAfterTheQuietPeriod() async {
        let child = FakeProcess()
        let subject = supervisor(child, policy(quiet: .milliseconds(300), limit: .seconds(600)), probe: { _ in false })
        child.say(servingLine)
        await subject.start()
        #expect(failure(subject)?.summary == "The server did not answer http://127.0.0.1:8443/pull/12 with a 2xx within 0.3 seconds of announcing its address.")
    }
}

@Suite struct OutputProgressTests {
    /// A clone's progress goes to stderr, which is the log itself, so the app never reads it
    /// as a line: only the log's growth shows it.
    @Test func stderrThatGoesStraightToTheLogCounts() async throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let log = directory.appending(path: "server.log")
        try Data("an earlier run\n".utf8).write(to: log)
        let child = try SpawnedProcess(LaunchSpec(
            executable: "/bin/sh", arguments: ["-c", "printf 'cloning: 45%%' >&2"], logURL: log))
        #expect(await child.waitForExit() == 0)
        _ = await child.waitForOutputEnd()
        #expect(child.outputProgress == "cloning: 45%".utf8.count)
        var seen: [String] = []
        for await line in child.lines { seen.append(line) }
        #expect(seen.isEmpty)
        child.release()
    }

    @Test func withoutALogThePipeCounts() async throws {
        let child = try SpawnedProcess(LaunchSpec(executable: "/bin/sh", arguments: ["-c", "echo out; echo err >&2"]))
        #expect(await child.waitForExit() == 0)
        _ = await child.waitForOutputEnd()
        #expect(child.outputProgress == "out\nerr\n".utf8.count)
        child.release()
    }
}

/// The copies of `metab`'s constants the app's bounds are built from, each pinned to its
/// definition, so a change there fails here and names the copy to change.
@Suite struct MetabAcquisitionTests {
    private static let repositoryRoot = URL(filePath: #filePath).deletingLastPathComponent()
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        .deletingLastPathComponent()

    /// What `name` is assigned at the start of a line of `file`: the text after `=`.
    private func definition(_ name: String, in file: String) throws -> String {
        let source = try String(contentsOf: Self.repositoryRoot.appending(path: file), encoding: .utf8)
        let line = try #require(
            source.split(separator: "\n").first { $0.hasPrefix(name + " ") || $0.hasPrefix(name + ":") },
            "\(name) is not defined at the start of a line of \(file)")
        let value = try #require(line.split(separator: "=", maxSplits: 1).last)
        return value.trimmingCharacters(in: .whitespaces)
    }

    private func seconds(_ name: String, in file: String) throws -> Duration {
        .seconds(try #require(Double(try definition(name, in: file)), "\(name) is not a number"))
    }

    @Test func theAcquisitionBoundsAreMetabs() throws {
        #expect(try seconds("REMOTE_PROBE_TIMEOUT_S", in: "src/metabrowser/cache/origin.py") == MetabAcquisition.remoteProbe)
        #expect(try seconds("GIT_ACQUISITION_TIMEOUT_S", in: "src/metabrowser/git/process.py") == MetabAcquisition.fetch)
        #expect(try seconds("LOG_INTERVAL_S", in: "src/metabrowser/cli/clone_report.py") == MetabAcquisition.progressLineInterval)
        // MetabAcquisition.reservationWait is this expression: its attempts and its minute.
        #expect(try definition("RESERVATION_WAIT_S", in: "src/metabrowser/cache/acquire.py")
            == "\(MetabAcquisition.attempts) * (REMOTE_PROBE_TIMEOUT_S + GIT_ACQUISITION_TIMEOUT_S + \(MetabAcquisition.validation.components.seconds).0)")
    }

    @Test func thePortWalkIsMetabs() throws {
        #expect(try definition("DEFAULT_BROWSER_PORT", in: "src/metabrowser/settings.py") == String(CLIServeLaunch.defaultBasePort))
        #expect(try definition("DEFAULT_PORT_SEARCH_COUNT", in: "src/metabrowser/server_utils.py") == String(CLIServeLaunch.portSearchCount))
    }

    @Test func theLinkHostsAreTheGitHubReducers() throws {
        let file = "src/metabrowser/builtin_plugins/github/urls.py"
        #expect(try definition("_WEB_HOSTS", in: file) == #"frozenset({"github.com", "www.github.com"})"#)
        #expect(try definition("_RAW_HOST", in: file) == #""raw.githubusercontent.com""#)
        #expect(GitHubLink.hosts == ["github.com", "www.github.com", "raw.githubusercontent.com"])
    }
}
