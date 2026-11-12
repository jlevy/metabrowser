import Foundation
import Testing
@testable import ShellCore

/// Noticing `uv tool upgrade` and anything else that replaces the runtime's file
/// (mb-895s): fingerprints, the settle rule, and the recheck that follows.
@Suite struct RuntimeRecheckTests {
    private let tools = ToolPaths(git: "/usr/bin/git")

    private func stamp(_ n: UInt64) -> FileFingerprint {
        FileFingerprint(device: 1, inode: n, size: 348, modified: 1_000, mode: 0o100755)
    }

    /// The files a watch sees, changed by the test between looks.
    private final class Disk: @unchecked Sendable {
        var files: [String: FileFingerprint] = [:]
        func fingerprint(_ path: String) -> FileFingerprint? { files[path] }
    }

    @Test func aReplacedOrRewrittenFileHasANewFingerprint() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let file = directory.appending(path: "metab").path
        let link = directory.appending(path: "link").path
        #expect(FileFingerprint.of(file) == nil)
        try "#!/bin/sh\necho metab 0.12.1\n".write(toFile: file, atomically: false, encoding: .utf8)
        try FileManager.default.createSymbolicLink(atPath: link, withDestinationPath: file)
        let first = try #require(FileFingerprint.of(file))
        #expect(FileFingerprint.of(file) == first)
        #expect(FileFingerprint.of(link) == first)  // a link is its target, as uv's are
        // An installer that writes a new file and renames it over the old one.
        try "#!/bin/sh\necho metab 0.13.0\n".write(toFile: file, atomically: true, encoding: .utf8)
        let replaced = try #require(FileFingerprint.of(file))
        #expect(replaced != first)
        // An installer that rewrites the file in place, same length and inode.
        let handle = try #require(FileHandle(forWritingAtPath: file))
        try handle.write(contentsOf: Data("#!/bin/sh\necho metab 0.13.1\n".utf8))
        try handle.close()
        #expect(try #require(FileFingerprint.of(file)) != replaced)
    }

    @Test func aChangeCountsOnceTwoLooksAgree() {
        let disk = Disk()
        disk.files["/bin/metab"] = stamp(1)
        let watch = FileWatch(watching: ["/bin/metab", "/bin/uv"], fingerprint: disk.fingerprint)
        #expect(watch.look() == [])
        // Mid-install: removed, then written, then left alone.
        disk.files["/bin/metab"] = nil
        #expect(watch.look() == [])
        disk.files["/bin/metab"] = stamp(2)
        #expect(watch.look() == [])
        #expect(watch.look() == ["/bin/metab"])
        #expect(watch.look() == [])
        // Gone and back as it was between two looks is no change.
        disk.files["/bin/metab"] = nil
        #expect(watch.look() == [])
        disk.files["/bin/metab"] = stamp(2)
        #expect(watch.look() == [])
        disk.files["/bin/uv"] = stamp(9)
        #expect(watch.look() == [])
        #expect(watch.look() == ["/bin/uv"])
    }

    @Test func aRuntimeWatchComparesWithTheFingerprintItWasValidatedWith() {
        let disk = Disk()
        disk.files["/opt/metab"] = stamp(2)  // already replaced when the watch starts
        let runtime = Runtime(executable: "/opt/metab", version: "0.12.1", source: .localBin, fingerprint: stamp(1))
        let watch = SetupWatch(runtime: runtime, fingerprint: disk.fingerprint)
        #expect(watch.look() == nil)
        #expect(watch.look() == .recheck)
        #expect(watch.look() == nil)
    }

    @Test func aWaitingWatchDiscoversWhenMetabAppearsAndReplansWhenUvDoes() {
        let disk = Disk()
        let watch = SetupWatch(
            waitingFor: ["/Volumes/Home/.local/bin/metab"], uv: ["/Volumes/Home/.local/bin/uv"], fingerprint: disk.fingerprint)
        disk.files["/Volumes/Home/.local/bin/uv"] = stamp(1)
        #expect(watch.look() == nil)
        #expect(watch.look() == .replan)
        disk.files["/Volumes/Home/.local/bin/metab"] = stamp(2)
        disk.files["/Volumes/Home/.local/bin/uv"] = stamp(3)
        #expect(watch.look() == nil)
        #expect(watch.look() == .discover)  // metab wins: discovery replans too
    }

    /// mb-oa5u: `chmod +x` changes nothing else about a file, so a candidate that
    /// discovery saw as missing because it could not run stayed missing.
    @Test func aChangeOfModeAloneIsANewFingerprint() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let file = directory.appending(path: "metab").path
        try "#!/bin/sh\necho metab 0.12.1\n".write(toFile: file, atomically: false, encoding: .utf8)
        #expect(chmod(file, 0o644) == 0)
        let before = try #require(FileFingerprint.of(file))
        #expect(chmod(file, 0o755) == 0)
        let after = try #require(FileFingerprint.of(file))
        #expect(after != before)
        #expect(after.inode == before.inode && after.modified == before.modified)
    }

    @Test func aWaitingWatchDiscoversWhenACandidateBecomesExecutable() {
        let disk = Disk()
        var notExecutable = stamp(4)
        notExecutable.mode = 0o100644
        disk.files["/Volumes/Home/.local/bin/metab"] = notExecutable
        let watch = SetupWatch(
            waitingFor: ["/Volumes/Home/.local/bin/metab"], uv: [], fingerprint: disk.fingerprint)
        #expect(watch.look() == nil)
        disk.files["/Volumes/Home/.local/bin/metab"] = stamp(4)
        #expect(watch.look() == nil)
        #expect(watch.look() == .discover)
    }

    /// mb-d4g5: an old `metab` found only on the login shell's `PATH` was shown in
    /// Settings but not watched, so upgrading it released no waiting folder.
    @Test func aWaitingWatchCoversEveryCandidateTheLastSearchTried() {
        let tried = [
            CandidateOutcome(path: "/Volumes/Home/.local/bin/metab", source: .localBin, result: .missing),
            CandidateOutcome(path: "/Volumes/Tools/bin/metab", source: .loginShell, result: .tooOld(version: "0.12.0")),
        ]
        let paths = SetupWatch.metabPaths(
            cheap: ["/Volumes/Home/.local/bin/metab", "/opt/homebrew/bin/metab"], tried: tried,
            binDirectory: "/Volumes/Home/.local/share/bin")
        #expect(paths == [
            "/Volumes/Home/.local/bin/metab", "/opt/homebrew/bin/metab", "/Volumes/Tools/bin/metab",
            "/Volumes/Home/.local/share/bin/metab",
        ])
        let disk = Disk()
        disk.files["/Volumes/Tools/bin/metab"] = stamp(5)
        let watch = SetupWatch(waitingFor: paths, uv: [], fingerprint: disk.fingerprint)
        disk.files["/Volumes/Tools/bin/metab"] = stamp(6)  // upgraded in place, nothing else changed
        #expect(watch.look() == nil)
        #expect(watch.look() == .discover)
    }

    @Test func aRuntimeIsCurrentOnlyWithItsOwnFileAndAnAcceptedVersion() {
        let runtime = Runtime(executable: "/opt/metab", version: "0.12.1", source: .localBin, fingerprint: stamp(1))
        #expect(runtime.isCurrent(fingerprint: stamp(1)))
        #expect(!runtime.isCurrent(fingerprint: stamp(2)))
        #expect(!runtime.isCurrent(fingerprint: nil))
        var unknown = runtime
        unknown.fingerprint = nil  // as saved by a build that took none
        #expect(!unknown.isCurrent(fingerprint: nil))
        var old = runtime
        old.version = "0.12.0"  // as saved by a build with a lower minimum
        #expect(!old.isCurrent(fingerprint: stamp(1)))
    }

    @Test func discoveryTakesTheFingerprintBeforeRunningVersion() async {
        let order = Recorder<String>()
        let env = DiscoveryEnvironment(
            home: "/Volumes/Home", environment: [:], saved: nil, shell: nil,
            isExecutable: { $0 == "/Volumes/Home/.local/bin/metab" || $0.hasPrefix("/opt/homebrew/bin/g") },
            canonicalPath: { $0 },
            run: { spec, _ in
                order.append("run")
                return CommandResult(status: 0, output: ["metab 0.12.1"])
            },
            fingerprint: { path in
                order.append("fingerprint")
                return path == "/Volumes/Home/.local/bin/metab" ? FileFingerprint(device: 1, inode: 7, size: 1, modified: 1, mode: 0o100755) : nil
            })
        let report = await RuntimeDiscovery.discover(env)
        #expect(report.setup?.runtime.fingerprint?.inode == 7)
        #expect(order.all.prefix(2) == ["fingerprint", "run"])
    }

    private func selection(with setup: RuntimeSetup) -> (RuntimeSelection, RuntimeSettings) {
        let settings = RuntimeSettings(defaults: UserDefaults(suiteName: "shellcore-recheck-\(UUID().uuidString)")!)
        return (RuntimeSelection(settings: settings, setup: setup), settings)
    }

    @Test func aRecheckHoldsFoldersAndAdoptsTheNewVersion() {
        let old = RuntimeSetup(
            runtime: Runtime(executable: "/opt/metab", version: "0.12.1", source: .localBin, fingerprint: stamp(1)),
            tools: tools)
        let (subject, settings) = selection(with: old)
        let folder = URL(filePath: "/tmp/notes", directoryHint: .isDirectory)
        let ticket = subject.startRecheck()
        #expect(subject.setupForOpening(folder) == nil)  // not the file that changed
        #expect(subject.waitingFolders == [folder])
        let outcome = subject.finishRecheck(ticket, fingerprint: stamp(2), result: .valid(version: "0.13.0"))
        let upgraded = RuntimeSetup(
            runtime: Runtime(executable: "/opt/metab", version: "0.13.0", source: .localBin, fingerprint: stamp(2)),
            tools: tools)
        #expect(outcome == .adopted(upgraded))
        #expect(settings.load() == upgraded)
        #expect(subject.setupForOpening(folder) == upgraded)
    }

    @Test func aRecheckThatFindsAnOlderOrMissingMetabLeavesNoRuntime() {
        for result: CandidateResult in [.tooOld(version: "0.12.0"), .missing, .rejected("could not run")] {
            let old = RuntimeSetup(
                runtime: Runtime(executable: "/opt/metab", version: "0.12.1", source: .localBin), tools: tools)
            let (subject, _) = selection(with: old)
            let ticket = subject.startRecheck()
            #expect(subject.finishRecheck(ticket, fingerprint: nil, result: result) == .notFound)
            #expect(subject.setup == nil)
            #expect(!subject.isRechecking)
            #expect(subject.tried == [CandidateOutcome(path: "/opt/metab", source: .localBin, result: result)])
        }
    }

    /// mb-2mpn: Find Again during a recheck kept the changed file's hold only until
    /// the search started, so a folder opened meanwhile started the unchecked file.
    @Test func aSearchStartedDuringARecheckKeepsFoldersWaiting() {
        let old = RuntimeSetup(
            runtime: Runtime(executable: "/opt/metab", version: "0.12.1", source: .localBin, fingerprint: stamp(1)),
            tools: tools)
        let (subject, _) = selection(with: old)
        let folder = URL(filePath: "/tmp/notes", directoryHint: .isDirectory)
        _ = subject.startRecheck()
        let search = subject.startSearch()
        #expect(subject.launchableSetup == nil)
        #expect(subject.setupForOpening(folder) == nil)
        #expect(subject.waitingFolders == [folder])
        let found = RuntimeSetup(
            runtime: Runtime(executable: "/opt/metab", version: "0.13.0", source: .localBin, fingerprint: stamp(2)),
            tools: tools)
        #expect(subject.finishSearch(search, with: DiscoveryReport(setup: found, tried: [])) == .adopted(found))
        #expect(subject.launchableSetup == found)
        #expect(subject.setupForOpening(folder) == found)
    }

    /// A choice that overtook a recheck and was rejected leaves the changed file
    /// unchecked, so folders still wait and the recheck is due again.
    @Test func aRejectedChoiceDuringARecheckLeavesTheRecheckDue() {
        let old = RuntimeSetup(
            runtime: Runtime(executable: "/opt/metab", version: "0.12.1", source: .localBin), tools: tools)
        let (subject, _) = selection(with: old)
        _ = subject.startRecheck()
        let choice = subject.startChoice()
        #expect(!subject.needsRecheck)  // the choice settles it first
        #expect(subject.finishChoice(choice, path: "/opt/b/metab", result: .missing) { tools } == .rejected(.missing))
        #expect(subject.launchableSetup == nil)
        #expect(subject.needsRecheck)
    }

    /// mb-hlkm: a watch that settled while a chosen file was being validated started
    /// a recheck, whose newer ticket dropped the user's choice.
    @Test func aChoiceInProgressCountsAsBusy() {
        let old = RuntimeSetup(
            runtime: Runtime(executable: "/opt/metab", version: "0.12.1", source: .localBin), tools: tools)
        let (subject, _) = selection(with: old)
        let choice = subject.startChoice()
        #expect(subject.isChoosing)
        #expect(subject.isBusy)
        // The old file changed meanwhile: folders wait, and no recheck starts over the choice.
        subject.markUnverified()
        #expect(!subject.needsRecheck)
        #expect(subject.launchableSetup == nil)
        let chosen = subject.finishChoice(choice, path: "/opt/b/metab", result: .valid(version: "0.13.0")) { tools }
        #expect(chosen == .adopted(RuntimeSetup(
            runtime: Runtime(executable: "/opt/b/metab", version: "0.13.0", source: .chosen), tools: tools)))
        #expect(!subject.isBusy)
        #expect(subject.launchableSetup?.runtime.executable == "/opt/b/metab")
    }

    @Test func aChoiceOvertakesARecheck() {
        let old = RuntimeSetup(
            runtime: Runtime(executable: "/opt/metab", version: "0.12.1", source: .localBin), tools: tools)
        let (subject, _) = selection(with: old)
        let recheck = subject.startRecheck()
        let choice = subject.startChoice()
        #expect(!subject.isRechecking)
        _ = subject.finishChoice(choice, path: "/opt/b/metab", result: .valid(version: "0.13.0")) { tools }
        #expect(subject.finishRecheck(recheck, fingerprint: nil, result: .tooOld(version: "0.12.0")) == .superseded)
        #expect(subject.setup?.runtime.executable == "/opt/b/metab")
    }
}

/// Which open servers an upgrade leaves behind, and how the app offers to restart them.
@Suite struct RuntimeUpgradeTests {
    private let current = Runtime(executable: "/Volumes/Home/.local/bin/metab", version: "0.13.0", source: .localBin)

    @Test func onlyServersFromTheSameMetabAtAnotherVersionAreOutdated() {
        let running = [
            Runtime(executable: "/Volumes/Home/.local/bin/metab", version: "0.12.1", source: .localBin),
            Runtime(executable: "/Volumes/Home/.local/bin/metab", version: "0.13.0", source: .localBin),
            // Chosen in Settings: a different metab, which Restart Server switches to.
            Runtime(executable: "/src/.venv/bin/metab", version: "0.12.1.dev3", source: .chosen),
        ]
        #expect(RuntimeUpgrade.outdated(running, current: current) == [0])
        // A checkout's description changes with its working tree, not its version.
        let checkout = Runtime(
            executable: "/src/.venv/bin/metab", version: "0.12.1.dev3+abc (+3 commits, abc)", source: .chosen)
        var committed = checkout
        committed.version = "0.12.1.dev3+abc (+4 commits, def, dirty)"
        #expect(RuntimeUpgrade.outdated([checkout], current: committed) == [])
    }

    @Test func thePromptNamesTheVersionsWithoutACheckoutsDescription() {
        let checkout = Runtime(
            executable: "/Volumes/Home/.local/bin/metab", version: "0.13.0.dev2+abc (+2 commits, abc)", source: .localBin)
        let one = RuntimeUpgrade.prompt(outdated: [current.with(version: "0.12.1")], current: checkout)
        #expect(one.title == "metab was updated to 0.13.0.dev2+abc")
        #expect(one.message.hasPrefix("1 open folder runs a server started from metab 0.12.1."))
        let two = RuntimeUpgrade.prompt(
            outdated: [current.with(version: "0.12.1"), current.with(version: "0.12.2")], current: current)
        #expect(two.message.hasPrefix("2 open folders run servers started from metab 0.12.1 and 0.12.2."))
    }
}

extension Runtime {
    fileprivate func with(version: String) -> Runtime {
        var copy = self
        copy.version = version
        return copy
    }
}
