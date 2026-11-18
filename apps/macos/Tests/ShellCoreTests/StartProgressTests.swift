import Darwin
import Foundation
import Testing
@testable import ShellCore

/// Lines `metab` writes to stderr while it acquires a repository, without a terminal, as
/// the app's server log is. `tests/test_macos_app_pins.py` writes each with
/// `CloneReport` and expects it here, word for word, so a change to what `metab` says
/// fails there and not in the app.
enum CloneReportSamples {
    static let started = "cloning https://github.com/octo/demo into ~/.cache/metabrowser"
    static let phase = "cloning https://github.com/octo/demo: fetching every object (12 s)"
    static let receiving = "cloning https://github.com/octo/demo: receiving objects: 45%, 334.0 MiB at 9.5 MiB/s (40 s)"
    static let cloned = "cloned https://github.com/octo/demo in 104 s (742.0 MiB); starting the server"
    static let cached = "using the clone of https://github.com/octo/demo cached in ~/.cache/metabrowser, fetched less than a minute ago"
    static let readingPullRequest = "reading pull request 12 (5.5 s)"
}

@Suite struct StartProgressTests {
    @Test func eachLineOfTheCloneReportSaysWhereTheCloneHasGot() {
        #expect(StartProgress.parse(CloneReportSamples.started) == .cloning(into: "~/.cache/metabrowser"))
        #expect(StartProgress.parse(CloneReportSamples.phase) == .status("fetching every object (12 s)"))
        #expect(
            StartProgress.parse(CloneReportSamples.receiving)
                == .status("receiving objects: 45%, 334.0 MiB at 9.5 MiB/s (40 s)"))
        #expect(
            StartProgress.parse(CloneReportSamples.cloned) == .cloned("in 104 s (742.0 MiB); starting the server"))
        #expect(
            StartProgress.parse(CloneReportSamples.cached)
                == .cached("cached in ~/.cache/metabrowser, fetched less than a minute ago"))
        #expect(StartProgress.parse(CloneReportSamples.readingPullRequest) == .waiting("reading pull request 12 (5.5 s)"))
    }

    /// The window names the repository already, so the view leaves out its URL.
    @Test func theViewSaysEachWithoutTheRepositorysURL() {
        let texts = [
            CloneReportSamples.started, CloneReportSamples.receiving, CloneReportSamples.cloned,
            CloneReportSamples.cached, CloneReportSamples.readingPullRequest,
        ].compactMap(StartProgress.parse).map(\.text)
        #expect(texts == [
            "Cloning into ~/.cache/metabrowser",
            "Receiving objects: 45%, 334.0 MiB at 9.5 MiB/s (40 s)",
            "Cloned in 104 s (742.0 MiB); starting the server",
            "Using the clone cached in ~/.cache/metabrowser, fetched less than a minute ago",
            "Reading pull request 12 (5.5 s)",
        ])
    }

    @Test func otherLinesReportNothing() {
        for line in [
            "",
            "Serving https://github.com/octo/demo at http://127.0.0.1:8475/view/",
            "Revision: 0123456 (main)",
            "Error: https://github.com/octo/demo could not be reached; check the network connection (network_unreachable); nothing was published",
            "INFO:     Started server process [4242]",
            "cloning",
            "cloning with no URL here",
            "cloning https://github.com/octo/demo:",
            "cloning https://github.com/octo/demo somewhere else",
            "cloned https://github.com/octo/demo",
            "using the clone of https://github.com/octo/demo",
            "reading pull request 12",
            "[metabrowser-app 2026-11-18T12:00:00Z] started pid 4242",
        ] {
            #expect(StartProgress.parse(line) == nil, "\(line)")
        }
    }

    @Test func theNewestProgressLineWinsWhateverFollowsIt() {
        let output = [
            CloneReportSamples.started, CloneReportSamples.phase, CloneReportSamples.receiving,
            "INFO: an unrelated line",
        ]
        #expect(StartProgress.latest(in: output) == .status("receiving objects: 45%, 334.0 MiB at 9.5 MiB/s (40 s)"))
        #expect(StartProgress.latest(in: ["INFO: nothing yet"]) == nil)
        #expect(StartProgress.latest(in: []) == nil)
        #expect(CLIServeLaunch().startProgress(in: output) == StartProgress.latest(in: output))
    }
}

/// The supervisor reports a repository's progress while it starts, and stops at its end.
@Suite struct StartProgressReportTests {
    private let servingLine = "Serving https://github.com/octo/demo at http://127.0.0.1:8475/view/"

    private func policy(limit: Duration?) -> SupervisorPolicy {
        var policy = SupervisorPolicy()
        policy.startupTimeout = startupCeiling
        policy.startupLimit = limit
        policy.progressInterval = .milliseconds(10)
        policy.shutdownGrace = .milliseconds(100)
        policy.probeInterval = .milliseconds(5)
        policy.outputSettle = .milliseconds(50)
        return policy
    }

    private func supervisor(_ child: FakeProcess, limit: Duration?) -> ServerSupervisor {
        ServerSupervisor(
            spec: LaunchSpec(executable: "/usr/bin/false"), launch: CLIServeLaunch(), policy: policy(limit: limit),
            makeProcess: { _ in child }, probe: { _ in true })
    }

    @Test func aRepositorysStartReportsItsCloneUntilItIsReady() async {
        let child = FakeProcess()
        let subject = supervisor(child, limit: .seconds(600))
        var reported: [StartProgress?] = []
        subject.onStartProgress = { reported.append($0) }
        let started = Task { await subject.start() }
        child.writeToLog(CloneReportSamples.started + "\n")
        #expect(await eventually { subject.startProgress == .cloning(into: "~/.cache/metabrowser") })
        child.writeToLog(CloneReportSamples.receiving + "\n")
        #expect(await eventually { subject.startProgress?.text.hasPrefix("Receiving objects") == true })
        // A line that is no progress leaves the last progress shown.
        child.writeToLog("a line about something else\n")
        child.writeToLog(CloneReportSamples.cloned + "\n")
        #expect(await eventually { subject.startProgress == .cloned("in 104 s (742.0 MiB); starting the server") })
        child.say(servingLine)
        await started.value
        #expect(subject.state != .starting)
        #expect(subject.startProgress == nil)
        #expect(reported.first == .cloning(into: "~/.cache/metabrowser"))
        #expect(reported.last == .some(nil))
        await subject.stop()
    }

    @Test func aFailedStartClearsItsProgress() async {
        let child = FakeProcess()
        let subject = supervisor(child, limit: .seconds(600))
        let started = Task { await subject.start() }
        child.writeToLog(CloneReportSamples.started + "\n")
        #expect(await eventually { subject.startProgress != nil })
        child.writeToLog(GitHubFailureSamples.notFound + "\n")
        child.exitOnItsOwn()
        await started.value
        guard case .failed(let failure) = subject.state else {
            Issue.record("expected a failure, got \(subject.state)")
            return
        }
        #expect(subject.startProgress == nil)
        #expect(failure.recentOutput.last == GitHubFailureSamples.notFound)
    }

    /// A folder's server clones nothing, so nothing reads its log while it starts.
    @Test func aFoldersStartReportsNothing() async {
        let child = FakeProcess()
        let subject = supervisor(child, limit: nil)
        var reported = 0
        subject.onStartProgress = { _ in reported += 1 }
        child.writeToLog(CloneReportSamples.started + "\n")
        let started = Task { await subject.start() }
        try? await Task.sleep(for: .milliseconds(100))
        child.say(servingLine)
        await started.value
        #expect(reported == 0)
        #expect(subject.startProgress == nil)
        await subject.stop()
    }
}
