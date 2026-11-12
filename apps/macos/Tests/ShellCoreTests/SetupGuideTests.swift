import Foundation
import Testing
@testable import ShellCore

/// The first run without a usable `metab` (mb-su30): which steps are missing, which
/// commands they show, and where the app waits for `metab`.
@Suite struct SetupGuideTests {
    private let bin = "/Volumes/Home/.local/bin"

    private func guide(
        tried: [CandidateOutcome] = [], uv: String? = nil, loginPath: [String]? = nil, homebrew: Bool = false,
        released: Bool = true, refused: [UvRefusal] = []
    ) -> SetupGuide {
        SetupGuide(
            tried: tried, uv: uv, binDirectory: bin, home: "/Volumes/Home", loginPath: loginPath, hasHomebrew: homebrew,
            minimumIsReleased: released, refusedUv: refused)
    }

    @Test func withoutUvItShowsBothInstallsInOrder() {
        let steps = guide().steps
        #expect(steps == [.installUv(homebrew: false), .installMetab(inNewTerminal: true)])
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
        let steps = guide(uv: "/opt/homebrew/bin/uv", loginPath: ["/opt/homebrew/bin", "/usr/bin"]).steps
        #expect(steps == [.installMetab(inNewTerminal: false)])
        #expect(steps[0].note == nil)
    }

    @Test func anOlderMetabIsUpgradedToTheFloor() {
        let old = CandidateOutcome(path: bin + "/metab", source: .localBin, result: .tooOld(version: "0.12.0"))
        let steps = guide(tried: [old], uv: bin + "/uv", loginPath: [bin]).steps
        #expect(steps == [.upgradeMetab(path: bin + "/metab", version: "0.12.0", inNewTerminal: false)])
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
            .reinstallMetab(path: bin + "/metab", reason: "could not run: x", inNewTerminal: true),
        ])
        #expect(guide(tried: [elsewhere, broken], uv: bin + "/uv").steps[0].command
            == "uv tool install --reinstall metabrowser")
        #expect(guide(tried: [elsewhere], uv: bin + "/uv", loginPath: [bin]).steps == [.installMetab(inNewTerminal: false)])
    }

    /// PR #361 A5: once the watch saw the uv just installed, the note went away, though
    /// the Terminal that ran the installer still cannot find it.
    @Test func theNewTerminalNoteStaysUntilTheLoginShellFindsUv() {
        let before = guide(loginPath: ["/usr/bin", "/bin"]).steps
        #expect(before.last?.note == "In a new Terminal window, so that it finds uv:")
        let detected = guide(uv: bin + "/uv", loginPath: ["/usr/bin", "/bin"]).steps
        #expect(detected == [.installMetab(inNewTerminal: true)])
        #expect(detected[0].note == "In a new Terminal window, so that it finds uv:")
        #expect(guide(uv: bin + "/uv").steps[0].note != nil)  // the login PATH is unknown
        #expect(guide(uv: bin + "/uv", loginPath: [bin]).steps[0].note == nil)
    }

    /// PR #361 A4: until the minimum is on PyPI, uv installs only older releases, so the
    /// steps end in this checkout's own metab and Choose metab….
    @Test func beforeTheMinimumIsReleasedTheStepsEndInTheSourceCheckout() {
        let fresh = guide(released: false)
        #expect(fresh.steps == [
            .installUv(homebrew: false), .buildFromCheckout(oldPath: nil, oldVersion: nil, inNewTerminal: true),
        ])
        #expect(fresh.steps[1].command == "make install")
        #expect(fresh.steps[1].title(home: "/Volumes/Home")
            == "Build metab in the source checkout this app was built from, then choose its .venv/bin/metab"
            + " with Choose metab… below: Metabrowser needs metab 0.12.1 or later, which is not on PyPI yet.")
        #expect(fresh.steps[1].note
            == "In a new Terminal window, so that it finds uv, at the root of the checkout:")
        #expect(fresh.endsWithChoice)
        #expect(!guide().endsWithChoice)
        #expect(fresh.heading == "Metabrowser needs metab 0.12.1 or later")
        let old = CandidateOutcome(path: bin + "/metab", source: .localBin, result: .tooOld(version: "0.12.0"))
        let upgrade = guide(tried: [old], uv: bin + "/uv", loginPath: [bin], released: false).steps
        #expect(upgrade == [.buildFromCheckout(oldPath: bin + "/metab", oldVersion: "0.12.0", inNewTerminal: false)])
        #expect(upgrade[0].note == "At the root of the checkout:")
        #expect(upgrade[0].title(home: "/Volumes/Home")
            == "Build metab in the source checkout this app was built from, then choose its .venv/bin/metab"
            + " with Choose metab… below: ~/.local/bin/metab is metab 0.12.0, and Metabrowser needs metab"
            + " 0.12.1 or later, which is not on PyPI yet.")
        let broken = CandidateOutcome(path: bin + "/metab", source: .localBin, result: .rejected("could not run: x"))
        #expect(guide(tried: [broken], uv: bin + "/uv", loginPath: [bin], released: false).steps
            == [.buildFromCheckout(oldPath: nil, oldVersion: nil, inNewTerminal: false)])
        #expect(MetabRequirement.isReleased == false)
    }

    /// PR #361 B1: a uv another account can change is not run, and the screen says why.
    @Test func aUvTheAppMayNotRunIsNamedWithItsReason() {
        let refused = [UvRefusal(path: "/opt/homebrew/bin/uv", reason: "/opt/homebrew belongs to another account (uid 502)")]
        let shown = guide(uv: "/opt/homebrew/bin/uv", loginPath: ["/opt/homebrew/bin"], refused: refused)
        // Present for the user's Terminal, which is theirs to run; not run by the app.
        #expect(shown.steps == [.installMetab(inNewTerminal: false)])
        #expect(shown.notices == [
            "Metabrowser does not run /opt/homebrew/bin/uv itself: /opt/homebrew belongs to another account (uid 502).",
        ])
    }

    @Test func onlyAUvThatPassesTheTrustCheckIsRun() async {
        let ran = Recorder<String>()
        let env = DiscoveryEnvironment(
            home: "/Volumes/Home", environment: [:], saved: nil, shell: nil,
            isExecutable: { $0 == "/opt/homebrew/bin/uv" || $0 == "/Volumes/Home/.cargo/bin/uv" },
            canonicalPath: { $0 },
            run: { spec, _ in
                ran.append(spec.executable)
                return CommandResult(status: 0, output: ["/Volumes/Home/uv-bin"])
            })
        let candidates = ["/Volumes/Home/.local/bin/uv", "/opt/homebrew/bin/uv", "/Volumes/Home/.cargo/bin/uv"]
        let refuseHomebrew: @Sendable (String) -> String? = { $0.hasPrefix("/opt/homebrew") ? "/opt/homebrew/bin is writable by its group" : nil }
        let both = await UvToolDirectory.survey(candidates, env: env, refusal: refuseHomebrew)
        #expect(both.found == "/opt/homebrew/bin/uv")
        #expect(both.run == "/Volumes/Home/.cargo/bin/uv")
        #expect(both.refused == [UvRefusal(path: "/opt/homebrew/bin/uv", reason: "/opt/homebrew/bin is writable by its group")])
        #expect(both.binDirectory == "/Volumes/Home/uv-bin")
        #expect(ran.all == ["/Volumes/Home/.cargo/bin/uv"])
        let none = await UvToolDirectory.survey(Array(candidates.prefix(2)), env: env, refusal: refuseHomebrew)
        #expect(none.run == nil)
        #expect(none.found == "/opt/homebrew/bin/uv")
        #expect(none.binDirectory == "/Volumes/Home/.local/bin")  // uv's documented default
        #expect(none.failure == nil)
        #expect(ran.all == ["/Volumes/Home/.cargo/bin/uv"])  // the refused one never ran
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
