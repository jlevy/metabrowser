import Darwin
import Foundation
import os
import Testing
@testable import ShellCore

/// A process table the test controls: which pids exist, when each started, its group,
/// and what each signal does to it.
private final class FakeTable: Sendable {
    struct Entry {
        var identity: ProcessIdentity
        var exitsOnTerm = true
        var exitsOnKill = true
    }
    private let entries: OSAllocatedUnfairLock<[pid_t: Entry]>
    private let sent = OSAllocatedUnfairLock(initialState: [String]())

    init(_ entries: [pid_t: Entry] = [:]) {
        self.entries = OSAllocatedUnfairLock(initialState: entries)
    }

    static func started(_ seconds: Int64, group: pid_t) -> ProcessIdentity {
        ProcessIdentity(start: ProcessStart(seconds: seconds, microseconds: 7), group: group)
    }

    func add(_ pid: pid_t, _ entry: Entry) { entries.withLock { $0[pid] = entry } }
    func remove(_ pid: pid_t) { _ = entries.withLock { $0.removeValue(forKey: pid) } }
    var signals: [String] { sent.withLock { $0 } }

    var table: ProcessTable {
        ProcessTable(
            lookup: { pid in self.entries.withLock { $0[pid]?.identity } },
            signalGroup: { group, signal in
                self.sent.withLock { $0.append("\(signal == SIGKILL ? "KILL" : "TERM") -\(group)") }
                self.entries.withLock { entries in
                    for (pid, entry) in entries where entry.identity.group == group {
                        if signal == SIGTERM ? entry.exitsOnTerm : entry.exitsOnKill { entries[pid] = nil }
                    }
                }
            })
    }
}

/// For records that should report no error.
/// For records that should report no error.
private let unexpected: @Sendable (String) -> Void = { Issue.record(Comment(rawValue: $0)) }

private func recordsFolder() throws -> URL {
    try temporaryDirectory().appending(path: "Application Support/io.github.jlevy.metabrowser.dev/servers")
}

/// A records file as the app writes it.
private struct Contents: Codable {
    var owner: AppOwner
    var servers: [ServerRecord]
}

private func onDisk(_ file: URL) throws -> Contents {
    try JSONDecoder().decode(Contents.self, from: Data(contentsOf: file))
}

/// The app process that owns the records, and whether it still runs.
private let thisApp = AppOwner(pid: 900, identity: FakeTable.started(9_000, group: 900))
private let crashedApp = AppOwner(pid: 800, identity: FakeTable.started(8_000, group: 800))

private let servingLine = "Serving /tmp/root at http://127.0.0.1:8412/view/"

private func policy() -> SupervisorPolicy {
    var policy = SupervisorPolicy()
    policy.shutdownGrace = .milliseconds(50)
    policy.killWait = .milliseconds(50)
    policy.probeInterval = .milliseconds(5)
    policy.outputSettle = .milliseconds(20)
    return policy
}

/// Each server is recorded while it runs, in a file of its app process's own, so a
/// crashed app's servers can be found at the next launch, and forgotten once it exits.
@Suite struct ServerRecordsTests {
    private let identity = FakeTable.started(1_000, group: 4242)

    private func records(in folder: URL, table: FakeTable, owner: AppOwner = thisApp) -> ServerRecords {
        ServerRecords(directory: folder, owner: owner, table: table.table, onError: unexpected)
    }

    private func supervisor(
        _ records: ServerRecords, table: ProcessTable, children: @escaping () -> FakeProcess
    ) -> ServerSupervisor {
        ServerSupervisor(
            spec: LaunchSpec(executable: "/usr/bin/false", workingDirectory: "/tmp/notes"), launch: CLIServeLaunch(),
            policy: policy(), makeProcess: records.recording(table: table) { _ in children() }, probe: { _ in true })
    }

    private func announcing(ignoresTerm: Bool = false, ignoresKill: Bool = false) -> FakeProcess {
        let child = FakeProcess(ignoresTerm: ignoresTerm, ignoresKill: ignoresKill)
        child.say(servingLine)
        return child
    }

    @Test func aRunningServerIsRecordedOwnerOnlyAndTheFileGoesWithTheLastOne() async throws {
        let folder = try recordsFolder()
        let fake = FakeTable([4242: .init(identity: identity)])
        let records = records(in: folder, table: fake)
        let subject = supervisor(records, table: fake.table) { announcing() }
        await subject.start()
        let expected = ServerRecord(pid: 4242, identity: identity, root: "/tmp/notes")
        #expect(records.all == [expected])
        #expect(records.file.lastPathComponent == "app-900.json")
        let saved = try onDisk(records.file)
        #expect(saved.owner == thisApp)
        #expect(saved.servers == [expected])
        let mode = try FileManager.default.attributesOfItem(atPath: records.file.path)[.posixPermissions] as? Int
        #expect(mode == 0o600)
        let folderMode = try FileManager.default.attributesOfItem(atPath: folder.path)[.posixPermissions] as? Int
        #expect(folderMode == 0o700)
        await subject.stop()
        #expect(await eventually { records.all.isEmpty })
        #expect(!FileManager.default.fileExists(atPath: records.file.path))
    }

    @Test func aCrashedServerIsForgottenOnceSweptAndARestartRecordsTheNewOne() async throws {
        let fake = FakeTable([4242: .init(identity: identity)])
        let records = records(in: try recordsFolder(), table: fake)
        var spawned: [FakeProcess] = []
        let subject = supervisor(records, table: fake.table) {
            let child = self.announcing()
            spawned.append(child)
            return child
        }
        await subject.start()
        spawned[0].exitOnItsOwn(code: 1)
        #expect(await eventually { if case .failed = subject.state { true } else { false } })
        #expect(records.all.isEmpty)
        await subject.start()  // Retry
        #expect(records.all.count == 1)
        await subject.stop()
        #expect(await eventually { records.all.isEmpty })
    }

    /// A child given up on in uninterruptible I/O stays recorded while it runs, so a
    /// later launch can still end it; it is forgotten once it exits.
    @Test func aChildGivenUpOnStaysRecordedUntilItExits() async throws {
        let fake = FakeTable([4242: .init(identity: identity)])
        let records = records(in: try recordsFolder(), table: fake)
        let child = announcing(ignoresTerm: true, ignoresKill: true)
        let subject = supervisor(records, table: fake.table) { child }
        await subject.start()
        await subject.stop()
        #expect(records.all.count == 1)
        child.exitOnItsOwn()
        #expect(await eventually { records.all.isEmpty })
    }

    @Test func aChildThatIsGoneBeforeItCanBeRecordedIsNotRecorded() async throws {
        let records = records(in: try recordsFolder(), table: FakeTable())
        let subject = supervisor(records, table: FakeTable().table) { self.announcing() }
        await subject.start()
        #expect(records.all.isEmpty)
        await subject.stop()
    }

    @Test func theNextLaunchFindsACrashedAppsServersAndSettlesThem() throws {
        let folder = try recordsFolder()
        let left = ServerRecord(pid: 77, identity: FakeTable.started(500, group: 77), root: "/tmp/old")
        let stuck = ServerRecord(pid: 78, identity: FakeTable.started(501, group: 78), root: "/tmp/stuck")
        let earlier = records(in: folder, table: FakeTable(), owner: crashedApp)
        earlier.add(left)
        earlier.add(stuck)
        // crashedApp is not in the next launch's process table: it is not running.
        let next = records(in: folder, table: FakeTable())
        #expect(next.orphans == [left, stuck])
        next.settleOrphans([.stopped(left), .survived(stuck)])
        #expect(!FileManager.default.fileExists(atPath: earlier.file.path))
        #expect(next.all == [stuck])  // the next launch tries again
        #expect(try onDisk(next.file).servers == [stuck])
    }

    /// Two copies with one bundle identifier share the folder; neither takes the other's
    /// live servers for orphans.
    @Test func anotherRunningCopysServersAreNotOrphans() throws {
        let folder = try recordsFolder()
        let other = AppOwner(pid: 700, identity: FakeTable.started(7_000, group: 700))
        let table = FakeTable([700: .init(identity: other.identity)])
        records(in: folder, table: table, owner: other).add(
            ServerRecord(pid: 71, identity: FakeTable.started(7_100, group: 71), root: "/tmp/theirs"))
        #expect(records(in: folder, table: table).orphans.isEmpty)
        // A process that later got the other copy's pid is not that copy.
        let reused = FakeTable([700: .init(identity: FakeTable.started(9_999, group: 700))])
        #expect(records(in: folder, table: reused).orphans.map(\.pid) == [71])
    }

    @Test func anUnreadableFileIsReportedAndSkipped() throws {
        let folder = try recordsFolder()
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        try Data("not json".utf8).write(to: folder.appending(path: "app-12.json"))
        let errors = Recorder<String>()
        let records = ServerRecords(directory: folder, owner: thisApp, table: FakeTable().table, onError: { errors.append($0) })
        #expect(records.orphans.isEmpty)
        #expect(errors.all.count == 1)
        #expect(errors.all.first?.contains("could not read the server records") == true)
    }

    @Test func aFileThatCannotBeWrittenIsReportedAndTheOldOneKept() throws {
        let folder = try recordsFolder()
        let first = ServerRecord(pid: 1, identity: FakeTable.started(1, group: 1), root: "/tmp/a")
        let records = records(in: folder, table: FakeTable())
        records.add(first)
        chmod(folder.path, 0o500)  // no new file can be made beside it
        defer { chmod(folder.path, 0o700) }
        let errors = Recorder<String>()
        let blocked = ServerRecords(directory: folder, owner: thisApp, table: FakeTable().table, onError: { errors.append($0) })
        blocked.add(first)
        blocked.add(ServerRecord(pid: 2, identity: FakeTable.started(2, group: 2), root: "/tmp/b"))
        #expect(errors.all.count == 2)
        #expect(errors.all.allSatisfy { $0.contains("could not save the server records") })
        #expect(blocked.all.count == 2)  // still known to this run
        #expect(try onDisk(records.file).servers == [first])  // the published file is whole, and as it was
    }
}

/// At launch, only a group whose leader still has its recorded start time is signaled:
/// a pid the kernel has since handed to another process is left alone.
@Suite struct OrphanReaperTests {
    private func record(_ pid: pid_t, started: Int64) -> ServerRecord {
        ServerRecord(pid: pid, identity: FakeTable.started(started, group: pid), root: "/tmp/\(pid)")
    }

    private func reap(_ records: [ServerRecord], _ fake: FakeTable) async -> [OrphanReaper.Outcome] {
        await OrphanReaper.reap(records, table: fake.table, grace: .milliseconds(100), killWait: .milliseconds(100))
    }

    @Test func aMatchingServerIsStoppedWithTerm() async {
        let orphan = record(10, started: 1_000)
        let fake = FakeTable([10: .init(identity: orphan.identity)])
        #expect(await reap([orphan], fake) == [.stopped(orphan)])
        #expect(fake.signals == ["TERM -10"])
    }

    @Test func oneThatIgnoresTermIsKilled() async {
        let orphan = record(10, started: 1_000)
        let fake = FakeTable([10: .init(identity: orphan.identity, exitsOnTerm: false)])
        #expect(await reap([orphan], fake) == [.killed(orphan)])
        #expect(fake.signals == ["TERM -10", "KILL -10"])
    }

    @Test func oneThatSurvivesKillIsKeptForTheNextLaunch() async {
        let orphan = record(10, started: 1_000)
        let fake = FakeTable([10: .init(identity: orphan.identity, exitsOnTerm: false, exitsOnKill: false)])
        let outcomes = await reap([orphan], fake)
        #expect(outcomes == [.survived(orphan)])
    }

    @Test func aReusedPidAMissingOneAndAChangedGroupAreNotSignaled() async {
        let reused = record(10, started: 1_000)
        let missing = record(11, started: 1_000)
        let regrouped = record(12, started: 1_000)
        let fake = FakeTable([
            10: .init(identity: FakeTable.started(2_000, group: 10)),  // another process, started later
            12: .init(identity: FakeTable.started(1_000, group: 99)),
        ])
        let outcomes = await reap([reused, missing, regrouped], fake)
        #expect(outcomes == [.gone(reused), .gone(missing), .gone(regrouped)])
        #expect(fake.signals.isEmpty)
    }

    @Test func eachOutcomeSaysWhatHappened() {
        let orphan = record(10, started: 1_000)
        #expect(OrphanReaper.Outcome.stopped(orphan).summary
            == "ended the server pid 10 for /tmp/10, which an app that did not quit left running, with SIGTERM")
        #expect(OrphanReaper.Outcome.survived(orphan).summary.hasSuffix("the next launch tries again"))
        #expect(OrphanReaper.Outcome.gone(orphan).summary == "server pid 10 for /tmp/10 had already exited")
    }

    @Test func severalOrphansShareOneWait() async {
        let first = record(10, started: 1_000)
        let second = record(20, started: 1_000)
        let fake = FakeTable([
            10: .init(identity: first.identity), 20: .init(identity: second.identity, exitsOnTerm: false),
        ])
        let clock = ContinuousClock()
        let began = clock.now
        #expect(await reap([first, second], fake) == [.stopped(first), .killed(second)])
        #expect(began.duration(to: clock.now) < .seconds(1))
    }
}

/// The whole path on a real child: recorded at spawn, left behind as a crashed app
/// would leave it, then found and ended by the next launch's reaper.
@Suite struct OrphanReaperLiveTests {
    @Test func aServerLeftByACrashedRunIsEndedAtTheNextLaunch() async throws {
        let folder = try recordsFolder()
        let child = try SpawnedProcess(LaunchSpec(executable: "/bin/sh", arguments: ["-c", "echo up; exec sleep 30"]))
        defer { child.release() }
        for await _ in child.lines { break }
        let identity = try #require(ProcessTable.live.lookup(child.pid))
        #expect(identity.group == child.pid)
        #expect(ProcessTable.live.lookup(child.pid) == identity)  // the same process reads the same
        // An app process that has exited: no process has its pid and start time.
        let crashed = AppOwner(pid: child.pid, identity: ProcessIdentity(start: ProcessStart(seconds: 1, microseconds: 0), group: 1))
        ServerRecords(directory: folder, owner: crashed, onError: unexpected)
            .add(ServerRecord(pid: child.pid, identity: identity, root: "/tmp"))

        let next = ServerRecords(directory: folder, onError: unexpected)
        let outcomes = await OrphanReaper.reap(next.orphans, table: .live)
        #expect(outcomes == [.stopped(next.orphans[0])])
        let status = try #require(await child.waitForExit())
        #expect(ExitStatus(waitStatus: status) == .signaled(SIGTERM))
        #expect(ProcessTable.live.lookup(child.pid) == nil)  // a zombie counts as gone
    }

    /// The record names a process that started a minute before this one: as if the
    /// recorded server exited and the kernel gave its pid to this process.
    @Test func aRecordWhosePidNowNamesAnotherProcessLeavesItAlone() async throws {
        let other = try SpawnedProcess(LaunchSpec(executable: "/bin/sh", arguments: ["-c", "echo up; exec sleep 30"]))
        defer {
            other.signalGroup(SIGKILL)
            other.release()
        }
        for await _ in other.lines { break }
        let now = try #require(ProcessTable.live.lookup(other.pid))
        let earlier = ProcessStart(seconds: now.start.seconds - 60, microseconds: now.start.microseconds)
        let stale = ServerRecord(pid: other.pid, identity: ProcessIdentity(start: earlier, group: now.group), root: "/tmp")
        #expect(await OrphanReaper.reap([stale], table: .live) == [.gone(stale)])
        #expect(!other.hasExited)
    }
}
