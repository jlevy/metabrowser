import Foundation
import Testing
@testable import ShellCore

/// The real server, end to end, when METABROWSER_SHELL_TEST_METAB names a `metab` that
/// meets `MetabRequirement`, such as a checkout's after `make install`:
///
///     METABROWSER_SHELL_TEST_METAB=$PWD/../../.venv/bin/metab swift test --filter LiveMetab
nonisolated private let liveMetab = ProcessInfo.processInfo.environment["METABROWSER_SHELL_TEST_METAB"]

/// A server's environment as the app builds it, with a configuration directory of the
/// test's own. Every serve records its root as a recent target, and a test's folder must
/// not enter the list of whoever runs the suite, as it would through the default
/// directory the app's servers use. The directory is one `metab` makes inside
/// `configuration`, private to the user, which a temporary directory is not.
nonisolated private func liveEnvironment(configuration: URL, toolDirectories: [String] = []) -> [String: String] {
    let directory = configuration.appending(path: "metabrowser").path(percentEncoded: false)
    return ChildEnvironment.build(inherited: ProcessInfo.processInfo.environment, toolDirectories: toolDirectories)
        .merging(["METABROWSER_CONFIG_DIR": directory, RecentTargets.recordVariable: "1"]) { _, test in test }
}

/// Serialized: `metab` picks its port by probing and binds it later, so two servers
/// started at once can announce the same port, which the app's `LaunchGate` prevents.
@Suite(.serialized, .enabled(if: liveMetab != nil, "set METABROWSER_SHELL_TEST_METAB to a metab executable"))
struct LiveMetabTests {
    @Test func discoveryValidatesIt() async throws {
        let path = try #require(liveMetab)
        let result = await RuntimeDiscovery.validate(path, .live(saved: nil))
        guard case .valid(let version) = result else {
            Issue.record("\(path) did not validate: \(result)")
            return
        }
        #expect(!version.isEmpty)
    }

    @Test func servesAFolderAndStopsWithoutLeavingAProcess() async throws {
        let path = try #require(liveMetab)
        let root = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: root) }
        try "# Hello\n".write(to: root.appending(path: "README.md"), atomically: true, encoding: .utf8)
        let configuration = try temporaryDirectory("configuration")
        defer { try? FileManager.default.removeItem(at: configuration) }
        let log = root.appending(path: "server.log")
        let launch = CLIServeLaunch()
        let tools = RuntimeDiscovery.resolveTools(loginPath: nil, isExecutable: FileChecks.isExecutableFile)
        let subject = ServerSupervisor(
            spec: LaunchSpec(
                executable: path, arguments: launch.arguments(serving: root),
                environment: liveEnvironment(configuration: configuration, toolDirectories: tools.directories),
                workingDirectory: root.path, logURL: log),
            launch: launch)
        await subject.start()
        // Everything after the start runs under stoppingAfterward, so a failed request or a
        // cancelled run still stops the server before the folder is deleted.
        let pid = try await stoppingAfterward(subject) {
            guard case .ready(let endpoint) = subject.state else {
                Issue.record("expected ready, got \(subject.state)")
                return subject.pid
            }
            let (_, response) = try await URLSession.shared.data(from: endpoint.entryURL)
            #expect((response as? HTTPURLResponse)?.statusCode == 200)
            #expect(await subject.checkHealth() == .healthy(endpoint))
            switch await IdentityClient.fetch(origin: endpoint.origin, authorization: launch.authorization(for: endpoint)) {
            case .identity(let identity):
                #expect(identity.shortName == root.lastPathComponent)
                #expect(identity.kind == .folder)
            case .failed(let reason):
                Issue.record("/api/identity failed: \(reason)")
            }
            return subject.pid
        }
        #expect(subject.state == .stopped)
        #expect(!processExists(try #require(pid)))
        #expect(try String(contentsOf: log, encoding: .utf8).contains("Serving "))
    }

    /// File > Open Recent end to end: the server the app starts for a folder records it,
    /// `metab --recent --json` answers what `RecentTargets` reads, the folder is the row,
    /// under the path the app keys its session by, and forgetting and clearing empty it.
    @Test func theServerTheAppStartsIsWhatOpenRecentLists() async throws {
        let path = try #require(liveMetab)
        let root = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: root) }
        let other = try temporaryDirectory("other")
        defer { try? FileManager.default.removeItem(at: other) }
        let configuration = try temporaryDirectory("configuration")
        defer { try? FileManager.default.removeItem(at: configuration) }
        let environment = liveEnvironment(configuration: configuration)
        func metab(_ arguments: [String]) async -> CommandResult {
            await CommandRunner.run(
                LaunchSpec(executable: path, arguments: arguments, environment: environment),
                timeout: RecentTargets.timeout)
        }
        func listed() async -> [RecentTarget] {
            guard case .listing(let listing) = RecentTargets.answer(await metab(RecentTargets.listArguments)) else {
                Issue.record("metab --recent --json was not read")
                return []
            }
            #expect(listing.problem == nil)
            return listing.targets
        }

        #expect(await listed().isEmpty)
        // Served by a spelling that differs only in case, where the volume takes one, as
        // this job's does: the list must hold the folder as the volume spells it, which is
        // how the app names its session (`FileChecks.canonicalPath`). The Python test of
        // this is in the macOS tier, which CI does not run.
        let shouted = root.deletingLastPathComponent().appending(
            path: root.lastPathComponent.uppercased(), directoryHint: .isDirectory)
        let served = FileManager.default.fileExists(atPath: shouted.path(percentEncoded: false)) ? shouted : root
        let launch = CLIServeLaunch()
        let subject = ServerSupervisor(
            spec: LaunchSpec(
                executable: path, arguments: launch.arguments(serving: served), environment: environment,
                workingDirectory: root.path),
            launch: launch)
        await subject.start()
        try await stoppingAfterward(subject) {
            guard case .ready = subject.state else {
                Issue.record("expected ready, got \(subject.state)")
                return
            }
            // Recorded before the Serving line, so a ready server is already listed.
            let targets = await listed()
            #expect(targets.map(\.mode) == [.folder])
            #expect(targets.map(\.root) == [FileChecks.canonicalPath(root.path(percentEncoded: false))])
        }

        // A server that is not an open, as a restored folder's is, records nothing: started
        // with the opt-out, it serves and leaves the list as it was.
        var restored = environment
        restored[RecentTargets.recordVariable] = "0"
        let quiet = ServerSupervisor(
            spec: LaunchSpec(
                executable: path, arguments: launch.arguments(serving: other), environment: restored,
                workingDirectory: other.path),
            launch: launch)
        await quiet.start()
        try await stoppingAfterward(quiet) {
            guard case .ready = quiet.state else {
                Issue.record("expected ready, got \(quiet.state)")
                return
            }
            #expect(await listed().map(\.root) == [FileChecks.canonicalPath(root.path(percentEncoded: false))])
        }
        let unrecorded = await CommandRunner.run(
            LaunchSpec(
                executable: path, arguments: RecentTargets.addArguments(other.path(percentEncoded: false)),
                environment: restored),
            timeout: RecentTargets.timeout)
        #expect(unrecorded.succeeded)
        #expect(await listed().count == 1)

        // An open that starts no server is recorded by the app's own call, and goes first.
        #expect(await metab(RecentTargets.addArguments(other.path(percentEncoded: false))).succeeded)
        let both = await listed()
        try #require(both.count == 2)
        #expect(both.map(\.root) == [other, root].map { FileChecks.canonicalPath($0.path(percentEncoded: false)) })
        let rows = RecentTargets.items(both, opensURLs: false)
        #expect(rows.map(\.title) == [other.lastPathComponent, root.lastPathComponent])
        #expect(rows.map(\.url) == [other, root].map { URL(filePath: FileChecks.canonicalPath($0.path(percentEncoded: false)), directoryHint: .isDirectory) })

        // A folder that is gone is forgotten by the path it was listed under.
        try FileManager.default.removeItem(at: other)
        #expect(await metab(RecentTargets.forgetArguments(both[0].root)).succeeded)
        #expect(await listed().map(\.root) == [both[1].root])
        #expect(await metab(RecentTargets.clearArguments).succeeded)
        #expect(await listed().isEmpty)
    }

    /// The page the app opens for a file is the view route `metab ROOT --path FILE`
    /// announces for it, spelled the same, and the server serves it.
    @Test func aFilesPageIsTheRouteMetabAnnounces() async throws {
        let path = try #require(liveMetab)
        let root = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: root) }
        let relative = "sub dir/Café notes #1~ (draft)?.md"
        let file = root.appending(path: relative)
        try FileManager.default.createDirectory(at: file.deletingLastPathComponent(), withIntermediateDirectories: true)
        try "# Hello\n".write(to: file, atomically: true, encoding: .utf8)
        let configuration = try temporaryDirectory("configuration")
        defer { try? FileManager.default.removeItem(at: configuration) }
        let launch = CLIServeLaunch()
        let subject = ServerSupervisor(
            spec: LaunchSpec(
                executable: path, arguments: launch.arguments(serving: root) + ["--path", relative],
                environment: liveEnvironment(configuration: configuration),
                workingDirectory: root.path),
            launch: launch)
        await subject.start()
        try await stoppingAfterward(subject) {
            guard case .ready(let endpoint) = subject.state else {
                Issue.record("expected ready, got \(subject.state)")
                return
            }
            let page = PageAddress.view(of: relative)
            #expect(PageAddress(endpoint.entryURL) == page)
            let (_, response) = try await URLSession.shared.data(from: try #require(page.url(on: endpoint.origin)))
            #expect((response as? HTTPURLResponse)?.statusCode == 200)
        }
    }

    /// What a crashed or force-quit app leaves: the kernel closes the stdin pipe the app
    /// held, and the server, started as the app starts it and serving, stops by itself
    /// and frees its port. Nothing signals it.
    ///
    /// Review C4 on #363: the test closed stdin as soon as the server announced itself,
    /// which it does before its socket listens, so the failed request at the end did not
    /// show that a listening server let its port go. It now closes stdin only once the
    /// server answers and holds its port. A stdin closed during startup is the CLI's case,
    /// `test_a_stdin_that_closes_while_startup_is_held_stops_the_server`.
    @Test func aServerWhoseAppIsGoneStopsByItself() async throws {
        let path = try #require(liveMetab)
        let root = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: root) }
        let configuration = try temporaryDirectory("configuration")
        defer { try? FileManager.default.removeItem(at: configuration) }
        let launch = CLIServeLaunch()
        let child = try SpawnedProcess(LaunchSpec(
            executable: path, arguments: launch.arguments(serving: root),
            environment: liveEnvironment(configuration: configuration),
            workingDirectory: root.path))
        defer {
            child.signalGroup(SIGKILL)  // only if the test failed with it running
            child.release()
        }
        let announced = await firstResult(within: .seconds(20), of: [{ @Sendable in
            for await line in child.lines {
                if let endpoint = launch.endpoint(announcedBy: line) { return endpoint }
            }
            return nil
        }])
        let endpoint = try #require(announced, "no announcement within 20 seconds")
        let readiness = launch.readinessURL(for: endpoint)
        let port = try #require(endpoint.origin.port)
        try #require(await answers(readiness, within: .seconds(20)), "the server never answered \(readiness)")
        try #require(!child.hasExited)
        #expect(!canBindLoopback(port: port), "nothing listens on \(port), so the check below would prove nothing")

        child.closeLifeline()  // what the kernel does when the app dies
        let clock = ContinuousClock()
        let closed = clock.now
        let status = try #require(await firstResult(within: .seconds(15), of: [{ @Sendable in await child.waitForExit() }]))
        #expect(ExitStatus(waitStatus: status) == .exited(0))
        #expect(closed.duration(to: clock.now) < .seconds(5))
        #expect(await HTTPReadiness.probe(readiness) == false)
        #expect(canBindLoopback(port: port))
        #expect(child.recentOutput().contains("Stopping Metabrowser: stdin closed."))
    }

    /// The app reads `metab`'s own `--present --dry-run --format json` for each kind of
    /// link and a refusal, as `PresentDryRun.answer` does (review A7 on #539), so the
    /// fixtures in `PresentPlanTests` cannot drift from what `metab` prints. The dry run
    /// reads no network, so this runs in CI.
    @Test(arguments: [
        ("https://github.com/jlevy/metabrowser", PresentPlan.Kind.repository, "https://github.com/jlevy/metabrowser"),
        ("https://github.com/JLevy/Metabrowser.git", .repository, "https://github.com/jlevy/metabrowser"),
        ("https://github.com/jlevy/metabrowser/pull/540/files", .pullRequest, "https://github.com/jlevy/metabrowser/pull/540/files"),
        ("https://github.com/jlevy/metabrowser/tree/main/docs", .tree, "https://github.com/jlevy/metabrowser/tree/main/docs"),
        // A ref with a `/`: the page is null, which the app does not need.
        ("https://github.com/jlevy/metabrowser/blob/claude/app-open-urls/docs/macos-app.md", .file,
         "https://github.com/jlevy/metabrowser/blob/claude/app-open-urls/docs/macos-app.md"),
        ("https://github.com/jlevy/metabrowser/commit/dcf2bcfa8", .commit, "https://github.com/jlevy/metabrowser/commit/dcf2bcfa8"),
        // The token is dropped: the server is started with the handoff.
        ("https://raw.githubusercontent.com/jlevy/metabrowser/main/README.md?token=SECRET", .file,
         "https://github.com/jlevy/metabrowser/blob/main/README.md"),
    ])
    func metabResolvesEveryKindOfLinkAsTheAppReadsIt(_ link: String, _ kind: PresentPlan.Kind, _ handoff: String) async throws {
        let answer = try await dryRun(link)
        #expect(answer == .plan(PresentPlan(
            kind: kind, repository: URL(string: "https://github.com/jlevy/metabrowser")!, link: URL(string: handoff)!)))
    }

    @Test(arguments: [
        ("https://github.com/jlevy/metabrowser/issues/1", "unsupported_github_url"),
        ("https://github.com/jlevy/metabrowser/pulls", "unsupported_github_url"),
    ])
    func metabsRefusalIsReadWhole(_ link: String, _ code: String) async throws {
        guard case .refused(let refusal) = try await dryRun(link) else {
            Issue.record("expected a refusal for \(link)")
            return
        }
        #expect(refusal.code == code)
        #expect(!refusal.message.isEmpty)
    }

    /// What `metab` answers for a repository its cache has never held, through the route
    /// the app asks before a link clones (`RepositoryCache`).
    @Test func theCacheIsAskedThroughMetab() async throws {
        let path = try #require(liveMetab)
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let setup = RuntimeSetup(
            runtime: Runtime(executable: path, version: "live", source: .chosen, fingerprint: nil),
            tools: RuntimeDiscovery.resolveTools(loginPath: nil, isExecutable: FileChecks.isExecutableFile))
        let absent = URL(string: "https://github.com/metabrowser-live-test/no-such-repository")!
        let answer = await RepositoryCache.lookUp(
            absent, folder: folder.path(percentEncoded: false), with: setup, inherited: ProcessInfo.processInfo.environment)
        #expect(answer == .notCached)
    }

    /// Help > Check Setup… end to end: the report `metab --doctor --json` prints in a
    /// server's environment is one the app reads, with every setup check.
    @Test func checkSetupReadsTheDoctorsReport() async throws {
        let path = try #require(liveMetab)
        let configuration = try temporaryDirectory("configuration")
        defer { try? FileManager.default.removeItem(at: configuration) }
        let tools = RuntimeDiscovery.resolveTools(loginPath: nil, isExecutable: FileChecks.isExecutableFile)
        let setup = RuntimeSetup(
            runtime: Runtime(executable: path, version: "live", source: .chosen, fingerprint: nil), tools: tools)
        var spec = DoctorRun.spec(
            setup: setup, inherited: ProcessInfo.processInfo.environment, appBundle: "/Applications/Metabrowser.app")
        spec.environment = liveEnvironment(configuration: configuration, toolDirectories: tools.directories)
        let answer = DoctorRun.answer(await CommandRunner.run(spec, timeout: DoctorRun.timeout))
        guard case .report(let report) = answer else {
            Issue.record("Check Setup… could not read the doctor's report: \(answer)")
            return
        }
        #expect(report.hasChecks)
        #expect(
            report.rows.map(\.id)
                == ["plugins", "open_in", "metab", "git", "config", "cache", "event_log", "github"])
        #expect(!report.rows.contains { $0.state == .other("unreadable") })
    }

    /// File > Open URL… accepts the plan from the same dry run as a sent link. It waits
    /// for window placement on success and shows `metab`'s reason on refusal.
    @Test(arguments: [
        ("https://github.com/jlevy/metabrowser/pull/540", true),
        ("https://github.com/jlevy/metabrowser/blob/main/docs/macos-app.md", true),
        ("https://github.com/jlevy/metabrowser/issues/1", false),
        ("https://github.com/jlevy/metabrowser/pull/0", false),
    ])
    func theOpenURLPanelSaysWhatMetabAnswers(_ text: String, _ opens: Bool) async throws {
        var panel = OpenURLPanel()
        panel.edit(text)
        let request = try #require(panel.open())
        let answer = try await dryRun(request.link.absoluteString)
        let plan = panel.answered(answer, for: request, metab: "metab")
        if opens {
            #expect(plan?.link.absoluteString == text)
            #expect(panel.phase == .opening(request))
            let presented = panel.presented(for: request)
            #expect(presented)
            #expect(panel.phase == .closed)
        } else {
            guard case .refused(let refusal) = answer else {
                Issue.record("expected a refusal for \(text), got \(answer)")
                return
            }
            #expect(plan == nil)
            #expect(panel.message == refusal.message)
            #expect(panel.phase == .editing)
        }
    }

    @Test(arguments: [
        "https://github.com/jlevy/metabrowser",
        "github.com/jlevy/metabrowser",
        "jlevy/metabrowser",
    ])
    func theOpenURLExamplesResolveToTheSameRepository(_ text: String) async throws {
        let expected = try #require(URL(string: "https://github.com/jlevy/metabrowser"))
        var panel = OpenURLPanel()
        panel.edit(text)
        let request = try #require(panel.open())
        #expect(request.link == expected)
        #expect(panel.text == expected.absoluteString)
        let answer = try await dryRun(request.link.absoluteString)
        let plan = panel.answered(answer, for: request, metab: "metab")
        #expect(plan == PresentPlan(kind: .repository, repository: expected, link: expected))
        #expect(panel.phase == .opening(request))
    }

    /// The panel opens what `metab URL` opens as typed: the link the panel sends, its path
    /// encoded as a browser sends it, gets the plan `metab` gives the raw text, and text
    /// the panel refuses for a character `metab` refuses too (`OpenURLEntry.encoded`).
    /// A GitHub URL typed without `https://` is written in full by both
    /// (`OpenURLEntry.corrected`, and `_root_in_full` in `src/metabrowser/cli/main.py`).
    @Test(arguments: [
        "https://github.com/octo/demo/blob/main/a b.md",
        "github.com/octo/demo/blob/main/a b.md",
        "www.github.com/octo/demo/pull/7",
        "https://github.com/octo/demo/blob/main/café.md",
        "https://github.com/octo/demo/blob/main/❤️.md",
        #"https://github.com/octo/demo/blob/main/a"b{c}|d^e`f<g>[1].md"#,
        "https://github.com/octo/demo/tree/main/docs dir",
        "https://github.com/octo/demo/blob/main/a b.md#L1",
        "https://github.com/octo/demo/blob/main/README\u{3164}.md",
        "https://github.com/octo/demo/blob/main/a\u{200B}b.md",
        "https://github.com/octo/demo/blob/main/README\u{FE0F}.md",
        "https://github.com/octo/demo/blob/main/a\\b.md",
        "https://github.com/octo/demo/blob/main/100%.md",
    ])
    func thePanelSendsWhatMetabOpensAsTyped(_ text: String) async throws {
        let typed = try await dryRun(rawText: text)
        switch OpenURLEntry.link(text) {
        case .success(let link):
            guard case .plan = typed else {
                Issue.record("the panel sends \(link) for \(text), which metab answers with \(typed)")
                return
            }
            #expect(try await dryRun(link.absoluteString) == typed)
        case .failure(let problem):
            guard case .refused = typed else {
                Issue.record("the panel refuses \(text) (\(problem)), which metab answers with \(typed)")
                return
            }
        }
    }

    private func dryRun(_ link: String) async throws -> PresentAnswer {
        let url = try #require(URL(string: link))
        #expect(GitHubLink.accepts(url))
        return try await dryRun(PresentDryRun.spec(
            for: url, with: liveSetup(), inherited: ProcessInfo.processInfo.environment, home: NSHomeDirectory()))
    }

    /// `metab TEXT --present --dry-run --format json`, with `TEXT` as typed, which no
    /// `URL` holds.
    private func dryRun(rawText text: String) async throws -> PresentAnswer {
        let placeholder = try #require(URL(string: "https://github.com/octo/demo"))
        var spec = PresentDryRun.spec(
            for: placeholder, with: try liveSetup(), inherited: ProcessInfo.processInfo.environment,
            home: NSHomeDirectory())
        spec.arguments[0] = text
        return try await dryRun(spec)
    }

    private func dryRun(_ spec: LaunchSpec) async throws -> PresentAnswer {
        PresentDryRun.answer(await CommandRunner.run(spec, timeout: PresentDryRun.timeout))
    }

    private func liveSetup() throws -> RuntimeSetup {
        let path = try #require(liveMetab)
        return RuntimeSetup(
            runtime: Runtime(executable: path, version: "live", source: .chosen, fingerprint: nil),
            tools: RuntimeDiscovery.resolveTools(loginPath: nil, isExecutable: FileChecks.isExecutableFile))
    }
}

/// Whether `url` answers with a 2xx within `limit`, polled as the supervisor polls it.
private func answers(_ url: URL, within limit: Duration) async -> Bool {
    let clock = ContinuousClock()
    let deadline = clock.now.advanced(by: limit)
    while clock.now < deadline {
        if await HTTPReadiness.probe(url) { return true }
        try? await Task.sleep(for: .milliseconds(50))
    }
    return false
}

/// Whether a socket can bind 127.0.0.1:`port`. With `SO_REUSEADDR`, connections the
/// server left in TIME_WAIT do not block it, and a socket still listening there does.
private func canBindLoopback(port: Int) -> Bool {
    let fd = socket(AF_INET, SOCK_STREAM, 0)
    guard fd >= 0 else { return false }
    defer { close(fd) }
    var on: Int32 = 1
    setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &on, socklen_t(MemoryLayout<Int32>.size))
    var address = sockaddr_in()
    address.sin_len = UInt8(MemoryLayout<sockaddr_in>.size)
    address.sin_family = sa_family_t(AF_INET)
    address.sin_addr.s_addr = inet_addr("127.0.0.1")
    address.sin_port = in_port_t(UInt16(port)).bigEndian
    return withUnsafePointer(to: &address) { pointer in
        pointer.withMemoryRebound(to: sockaddr.self, capacity: 1) {
            bind(fd, $0, socklen_t(MemoryLayout<sockaddr_in>.size)) == 0
        }
    }
}
