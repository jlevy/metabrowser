import Foundation
import Testing
@testable import ShellCore

@Suite struct SetupGuideTests {
    private let bin = "/Volumes/Home/.local/bin"

    private func guide(
        tried: [CandidateOutcome] = [], released: Bool = true, refused: [UvRefusal] = []
    ) -> SetupGuide {
        SetupGuide(
            tried: tried, binDirectory: bin, home: "/Volumes/Home",
            minimumIsReleased: released, refusedUv: refused)
    }

    @Test func anAbsentRuntimeLeavesTheWatchDirectoryAndPrereleaseStatus() {
        #expect(guide().binDirectory == bin)
        #expect(guide().notices.isEmpty)
        #expect(guide(released: false).notices == [
            "This preview needs metab \(MetabRequirement.minimum) or later. That version is pending on PyPI.",
        ])
    }

    @Test func theGuideReportsDiscoveryFailures() {
        let reason = "/opt/homebrew/bin is writable by its group"
        let tried = [
            CandidateOutcome(path: bin + "/metab", source: .localBin, result: .tooOld(version: "0.12.0")),
            CandidateOutcome(path: "/tmp/metab", source: .localBin, result: .rejected("could not run")),
            CandidateOutcome(path: "/opt/homebrew/bin/metab", source: .homebrew, result: .untrusted(reason)),
            CandidateOutcome(path: "/other/bin/metab", source: .localBin, result: .missing),
        ]
        #expect(guide(tried: tried, refused: [UvRefusal(path: "/opt/homebrew/bin/uv", reason: reason)]).notices == [
            "~/.local/bin/metab is metab 0.12.0. It is incompatible: the app needs \(MetabRequirement.minimum) or later.",
            "/tmp/metab could not be used: could not run.",
            "Automatic discovery skipped /opt/homebrew/bin/metab: \(reason). Choose metab… if you trust this file.",
            "Automatic discovery skipped /opt/homebrew/bin/uv: \(reason).",
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
        #expect(both.run == "/Volumes/Home/.cargo/bin/uv")
        #expect(both.refused == [UvRefusal(path: "/opt/homebrew/bin/uv", reason: "/opt/homebrew/bin is writable by its group")])
        #expect(both.binDirectory == "/Volumes/Home/uv-bin")
        #expect(ran.all == ["/Volumes/Home/.cargo/bin/uv"])
        let none = await UvToolDirectory.survey(Array(candidates.prefix(2)), env: env, refusal: refuseHomebrew)
        #expect(none.run == nil)
        #expect(none.binDirectory == "/Volumes/Home/.local/bin")  // uv's documented default
        #expect(none.failure == nil)
        #expect(ran.all == ["/Volumes/Home/.cargo/bin/uv"])  // the refused one never ran
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
