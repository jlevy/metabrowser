import Foundation
import Testing
@testable import ShellCore

@Suite struct ServerLaunchTests {
    private func parse(_ line: String) -> ServerEndpoint? { CLIServeLaunch.parseServingLine(line) }

    @Test func parsesTheServingLine() {
        let found = parse("Serving /Volumes/Archive/notes at http://127.0.0.1:8411/view/")
        #expect(found?.origin.absoluteString == "http://127.0.0.1:8411")
        #expect(found?.entryURL.absoluteString == "http://127.0.0.1:8411/view/")
    }

    @Test func ignoresTheDevBuildSuffix() {
        let found = parse("Serving /tmp/x at http://127.0.0.1:8413/view/docs/  [dev build: +12 commits, abc1234]")
        #expect(found?.entryURL.absoluteString == "http://127.0.0.1:8413/view/docs/")
    }

    @Test func aRootContainingAtIsNotConfusedForTheURL() {
        let found = parse("Serving /tmp/a at http://example.com b at http://127.0.0.1:8420/view/")
        #expect(found?.origin.absoluteString == "http://127.0.0.1:8420")
    }

    @Test func acceptsIPv6Loopback() {
        let found = parse("Serving /tmp at http://[::1]:8411/view/")
        #expect(found?.origin.absoluteString == "http://[::1]:8411")
    }

    @Test(arguments: [
        "Plugins: markdown, code",
        "Serving /tmp at https://127.0.0.1:8411/view/",
        "Serving /tmp at http://192.168.1.5:8411/view/",
        "Serving /tmp at http://localhost:8411/view/",
        "Serving /tmp at http://127.0.0.1/view/",
        "Serving /tmp at http://user@127.0.0.1:8411/view/",
        "  Serving /tmp at http://127.0.0.1:8411/view/",
        "Serving /tmp at http://127.0.0.1:8411/view/ and more",
        "Serving /tmp/x at http://127.0.0.1:9999/view/\nfoo at http://127.0.0.1:8411/view/",
        "Serving /tmp at http://127.0.0.1:8411/view/  [dev build: x",
        "",
    ])
    func rejectsAnythingElse(_ line: String) {
        #expect(parse(line) == nil)
    }

    @Test func aFolderWhosePathHasALineBreakIsRefused() {
        // Its name could forge a whole announcement line, so it is never served.
        #expect(CLIServeLaunch.unservableReason(URL(filePath: "/tmp/x at http://127.0.0.1:9/view/\nfoo")) != nil)
        #expect(CLIServeLaunch.unservableReason(URL(filePath: "/tmp/a\rb")) != nil)
        #expect(CLIServeLaunch.unservableReason(URL(filePath: "/tmp/My Notes at home")) == nil)
    }

    /// `--exit-on-eof` ties the server to the stdin pipe this app holds, so a crashed or
    /// force-quit app leaves no server running.
    @Test func argumentsServeTheRootWithoutOpeningABrowserAndEndWithTheApp() {
        let root = URL(filePath: "/tmp/My Notes", directoryHint: .isDirectory)
        #expect(CLIServeLaunch().arguments(serving: root)
            == ["/tmp/My Notes/", "--no-open", "--exit-on-eof", "--host", "127.0.0.1", "--port", "8411"])
        #expect(CLIServeLaunch().stdinLine == nil)
    }

    @Test func todaysServerNeedsNoAuthorizationAndIsProbedAtItsEntryURL() throws {
        let endpoint = try #require(parse("Serving /tmp at http://127.0.0.1:8411/view/"))
        #expect(CLIServeLaunch().authorization(for: endpoint) == .none)
        #expect(CLIServeLaunch().readinessURL(for: endpoint) == endpoint.entryURL)
    }

    @Test func commandLineQuotesWhatNeedsIt() {
        let spec = LaunchSpec(executable: "/usr/local/bin/metab", arguments: ["/tmp/it's here", "--no-open"])
        #expect(spec.commandLine == #"/usr/local/bin/metab '/tmp/it'\''s here' --no-open"#)
    }

    @Test func exitStatusDecodesWaitStatuses() {
        #expect(ExitStatus(waitStatus: 0) == .exited(0))
        #expect(ExitStatus(waitStatus: 2 << 8) == .exited(2))
        #expect(ExitStatus(waitStatus: SIGTERM) == .signaled(SIGTERM))
        #expect(ExitStatus(waitStatus: SIGKILL).description == "signal 9 (SIGKILL)")
    }
}
