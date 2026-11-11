import Foundation
import Testing
@testable import ShellCore

/// The real server, end to end, when METABROWSER_SHELL_TEST_METAB names a `metab`:
///
///     METABROWSER_SHELL_TEST_METAB=$HOME/.local/bin/metab swift test --filter LiveMetab
nonisolated private let liveMetab = ProcessInfo.processInfo.environment["METABROWSER_SHELL_TEST_METAB"]

@Suite(.enabled(if: liveMetab != nil, "set METABROWSER_SHELL_TEST_METAB to a metab executable"))
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
        guard case .ready(let endpoint) = subject.state else {
            Issue.record("expected ready, got \(subject.state)")
            return
        }
        let (_, response) = try await URLSession.shared.data(from: endpoint.entryURL)
        #expect((response as? HTTPURLResponse)?.statusCode == 200)
        // The route, or, from a metab older than it, a 404 that leaves the fallback.
        switch await IdentityClient.fetch(origin: endpoint.origin, authorization: launch.authorization(for: endpoint)) {
        case .identity(let identity):
            #expect(identity.shortName == root.lastPathComponent)
            #expect(identity.kind == .folder)
        case .missingRoute:
            break
        case .failed(let reason):
            Issue.record("/api/identity failed: \(reason)")
        }
        let pid = try #require(subject.pid)
        await subject.stop()
        #expect(subject.state == .stopped)
        #expect(!processExists(pid))
        #expect(try String(contentsOf: log, encoding: .utf8).contains("Serving "))
    }
}
