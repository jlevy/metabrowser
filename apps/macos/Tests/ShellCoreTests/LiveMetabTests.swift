import Foundation
import Testing
@testable import ShellCore

/// The real server, end to end, when METABROWSER_SHELL_TEST_METAB names a `metab` that
/// meets `MetabRequirement`, such as a checkout's after `make install`:
///
///     METABROWSER_SHELL_TEST_METAB=$PWD/../../.venv/bin/metab swift test --filter LiveMetab
nonisolated private let liveMetab = ProcessInfo.processInfo.environment["METABROWSER_SHELL_TEST_METAB"]

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
        let log = root.appending(path: "server.log")
        let launch = CLIServeLaunch()
        let tools = RuntimeDiscovery.resolveTools(loginPath: nil, isExecutable: FileChecks.isExecutableFile)
        let subject = ServerSupervisor(
            spec: LaunchSpec(
                executable: path, arguments: launch.arguments(serving: root),
                environment: ChildEnvironment.build(
                    inherited: ProcessInfo.processInfo.environment, toolDirectories: tools.directories),
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
        let launch = CLIServeLaunch()
        let subject = ServerSupervisor(
            spec: LaunchSpec(
                executable: path, arguments: launch.arguments(serving: root) + ["--path", relative],
                environment: ChildEnvironment.build(inherited: ProcessInfo.processInfo.environment, toolDirectories: []),
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
        let launch = CLIServeLaunch()
        let child = try SpawnedProcess(LaunchSpec(
            executable: path, arguments: launch.arguments(serving: root),
            environment: ChildEnvironment.build(inherited: ProcessInfo.processInfo.environment, toolDirectories: []),
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
