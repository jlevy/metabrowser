import Foundation
import Testing
@testable import ShellCore

/// The first run without a usable `metab` (mb-su30): which steps are missing, which
/// commands they show, and where the app waits for `metab`.
@Suite struct SetupGuideTests {
    private let bin = "/Volumes/Home/.local/bin"

    private func guide(
        tried: [CandidateOutcome] = [], uv: String? = nil, loginPath: [String]? = nil, homebrew: Bool = false
    ) -> SetupGuide {
        SetupGuide(
            tried: tried, uv: uv, binDirectory: bin, home: "/Volumes/Home", loginPath: loginPath, hasHomebrew: homebrew)
    }

    @Test func withoutUvItShowsBothInstallsInOrder() {
        let steps = guide().steps
        #expect(steps == [.installUv(homebrew: false), .installMetab(afterUv: true)])
        #expect(steps.map(\.command) == [
            "curl -LsSf https://astral.sh/uv/install.sh | sh", "uv tool install metabrowser",
        ])
        #expect(steps[0].alternative == nil)
        // The Terminal that ran uv's installer has not read the PATH it added.
        #expect(steps[1].note == "In a new Terminal window, so that it finds uv:")
    }

    @Test func withHomebrewTheUvStepOffersItToo() {
        #expect(guide(homebrew: true).steps.first?.alternative == "brew install uv")
    }

    @Test func withUvOnlyMetabIsMissing() {
        let steps = guide(uv: "/opt/homebrew/bin/uv").steps
        #expect(steps == [.installMetab(afterUv: false)])
        #expect(steps[0].note == nil)
    }

    @Test func anOlderMetabIsUpgradedToTheFloor() {
        let old = CandidateOutcome(path: bin + "/metab", source: .localBin, result: .tooOld(version: "0.12.0"))
        let steps = guide(tried: [old], uv: bin + "/uv").steps
        #expect(steps == [.upgradeMetab(path: bin + "/metab", version: "0.12.0", afterUv: false)])
        #expect(steps[0].command == "uv tool install --upgrade 'metabrowser>=0.12.1'")
        #expect(steps[0].title(home: "/Volumes/Home")
            == "Upgrade metab: ~/.local/bin/metab is metab 0.12.0, and Metabrowser needs 0.12.1 or later.")
        #expect(guide(tried: [old], uv: bin + "/uv").heading == "Metabrowser needs metab 0.12.1 or later")
        #expect(guide(uv: bin + "/uv").heading == "Metabrowser needs the metab command-line tool")
    }

    /// `uv tool install` says a broken tool is already installed and changes nothing.
    @Test func aBrokenToolInstallIsReinstalled() {
        let broken = CandidateOutcome(path: bin + "/metab", source: .localBin, result: .rejected("could not run: x"))
        let elsewhere = CandidateOutcome(path: "/srv/metab", source: .environment, result: .rejected("could not run: y"))
        #expect(guide(tried: [elsewhere, broken], uv: bin + "/uv").steps == [
            .reinstallMetab(path: bin + "/metab", reason: "could not run: x"),
        ])
        #expect(guide(tried: [elsewhere, broken], uv: bin + "/uv").steps[0].command
            == "uv tool install --reinstall metabrowser")
        #expect(guide(tried: [elsewhere], uv: bin + "/uv").steps == [.installMetab(afterUv: false)])
    }

    /// The app needs nothing on PATH; Terminal does, and only `uv tool update-shell` adds it.
    @Test func updateShellIsSuggestedUnlessTheLoginShellAlreadyHasTheDirectory() {
        #expect(guide().suggestsUpdateShell)
        #expect(guide(loginPath: ["/usr/bin", "/bin"]).suggestsUpdateShell)
        #expect(!guide(loginPath: [bin, "/usr/bin"]).suggestsUpdateShell)
        #expect(SetupGuide.updateShellCommand == "uv tool update-shell")
    }

    @Test func uvIsLookedForWhereItsInstallerAndHomebrewPutItThenOnTheLoginPath() {
        let candidates = SetupGuide.uvCandidates(
            home: "/Volumes/Home", environment: ["XDG_BIN_HOME": "/xdg/bin"],
            loginPath: ["/Volumes/Home/.cargo/bin", "/opt/homebrew/bin", "/usr/bin"])
        #expect(candidates == [
            "/xdg/bin/uv", "/Volumes/Home/.local/bin/uv", "/opt/homebrew/bin/uv", "/usr/local/bin/uv",
            "/Volumes/Home/.cargo/bin/uv", "/usr/bin/uv",
        ])
    }

    @Test func uvToolDirAsksUvWithTheLocationVariablesItReads() {
        let spec = UvToolDirectory.spec(
            uv: "/opt/homebrew/bin/uv", home: "/Volumes/Home",
            inherited: ["HOME": "/Volumes/Home", "UV_TOOL_BIN_DIR": "/uv/bin", "UV_INDEX_URL": "https://example.invalid"])
        #expect(spec.executable == "/opt/homebrew/bin/uv")
        #expect(spec.arguments == ["tool", "dir", "--bin"])
        #expect(spec.environment["UV_TOOL_BIN_DIR"] == "/uv/bin")
        #expect(spec.environment["UV_INDEX_URL"] == nil)
        #expect(spec.workingDirectory == "/Volumes/Home")
    }

    @Test func uvToolDirOutputIsOneAbsolutePath() {
        #expect(UvToolDirectory.parse(CommandResult(status: 0, output: ["/Volumes/Home/.local/bin"]))
            == .directory("/Volumes/Home/.local/bin"))
        #expect(UvToolDirectory.parse(CommandResult(status: 0, output: ["warning: x", "/uv/bin", ""]))
            == .directory("/uv/bin"))
        #expect(UvToolDirectory.parse(CommandResult(status: 0, output: ["relative/bin"]))
            == .failed("uv tool dir --bin printed: relative/bin"))
        #expect(UvToolDirectory.parse(CommandResult(status: 2 << 8, output: ["error: unrecognized"]))
            == .failed("uv tool dir --bin printed: error: unrecognized"))
        #expect(UvToolDirectory.parse(CommandResult(status: nil, output: [], launchError: "denied"))
            == .failed("could not run uv: denied"))
    }

    @Test func discoveryKeepsTheLoginPathItRead() async {
        let env = DiscoveryEnvironment(
            home: "/Volumes/Home", environment: [:], saved: nil, shell: "/bin/zsh",
            isExecutable: { $0 == "/bin/zsh" }, canonicalPath: { $0 },
            run: { spec, _ in
                CommandResult(status: 0, output: [
                    RuntimeDiscovery.beginMarker, "PATH=/Volumes/Home/bin:/usr/bin", RuntimeDiscovery.endMarker,
                ])
            })
        let report = await RuntimeDiscovery.discover(env)
        #expect(report.setup == nil)
        #expect(report.loginPath == ["/Volumes/Home/bin", "/usr/bin"])
        #expect(report.consultedLoginShell)
    }
}
