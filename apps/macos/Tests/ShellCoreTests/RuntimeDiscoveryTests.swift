import Foundation
import Testing
@testable import ShellCore

/// A fake machine: which files are executable, where symlinks point, and what each
/// command prints.
private struct Machine {
    var executables: Set<String> = []
    var links: [String: String] = [:]
    var versions: [String: String] = [:]  // executable → `--version` output
    /// Executables built before `--exit-on-eof`, which reject it as click does.
    var predatingFlag: Set<String> = []
    var loginOutput: [String]? = nil
    var environment: [String: String] = [:]
    var saved: Runtime? = nil
    /// Why the app may not run a path it found (`ExecutableTrust`), by path; the rest pass.
    var refused: [String: String] = [:]

    func discovery(calls: Recorder<String>) -> DiscoveryEnvironment {
        let executables = executables
        let links = links
        let versions = versions
        let predatingFlag = predatingFlag
        let loginOutput = loginOutput
        let refused = refused
        return DiscoveryEnvironment(
            home: "/Volumes/Home", environment: environment, saved: saved, shell: "/bin/zsh",
            isExecutable: { executables.contains($0) || $0 == "/bin/zsh" },
            canonicalPath: { links[$0] ?? $0 },
            run: { spec, _ in
                calls.append(([spec.executable] + spec.arguments).joined(separator: " "))
                if spec.executable == "/bin/zsh" {
                    return CommandResult(status: loginOutput == nil ? 256 : 0, output: loginOutput ?? [])
                }
                if predatingFlag.contains(spec.executable), spec.arguments.contains("--exit-on-eof") {
                    return CommandResult(status: 2 << 8, output: clickUsageError)
                }
                guard let version = versions[spec.executable] else {
                    return CommandResult(status: 1 << 8, output: ["Traceback (most recent call last):"])
                }
                return CommandResult(status: 0, output: [version])
            },
            refusal: { refused[$0] })
    }
}

/// What click prints, to stderr, for an option it does not know, before an eager option
/// such as `--version` runs; it then exits with status 2.
nonisolated private let clickUsageError = [
    "Usage: metab [OPTIONS] [ROOT]", "Try 'metab --help' for help.", "", "Error: No such option: --exit-on-eof",
]

private let homebrewTools: Set<String> = ["/opt/homebrew/bin/git", "/opt/homebrew/bin/gh"]

private func loginShellOutput(path: String) -> [String] {
    ["Last login: today", "", RuntimeDiscovery.beginMarker, "HOME=/Volumes/Home", "PATH=\(path)",
     "SHELL=/bin/zsh", "", RuntimeDiscovery.endMarker]
}

@Suite struct RuntimeDiscoveryTests {
    @Test func candidatesFollowTheDocumentedOrder() {
        var machine = Machine()
        machine.saved = Runtime(executable: "/opt/tools/metab", version: "0.11", source: .chosen)
        machine.environment = ["METABROWSER_METAB": "/srv/metab", "XDG_BIN_HOME": "/Volumes/Home/bin"]
        let candidates = RuntimeDiscovery.cheapCandidates(machine.discovery(calls: Recorder()))
        #expect(candidates.map(\.0) == [
            "/opt/tools/metab", "/srv/metab", "/Volumes/Home/.local/bin/metab", "/Volumes/Home/bin/metab",
            "/opt/homebrew/bin/metab", "/usr/local/bin/metab",
        ])
        #expect(candidates.map(\.1) == [.chosen, .environment, .localBin, .uvToolBin, .homebrew, .homebrew])
    }

    @Test func uvToolBinDirectoryFollowsUvsRule() {
        func directory(_ environment: [String: String]) -> String {
            var machine = Machine()
            machine.environment = environment
            return RuntimeDiscovery.uvToolBinDirectory(machine.discovery(calls: Recorder()))
        }
        #expect(directory([:]) == "/Volumes/Home/.local/bin")
        #expect(directory(["XDG_DATA_HOME": "/data/share"]) == "/data/bin")
        #expect(directory(["XDG_DATA_HOME": "/data/share", "XDG_BIN_HOME": "/xdg/bin"]) == "/xdg/bin")
        #expect(directory(["UV_TOOL_BIN_DIR": "/uv/bin", "XDG_BIN_HOME": "/xdg/bin"]) == "/uv/bin")
        #expect(directory(["UV_TOOL_BIN_DIR": "relative/bin"]) == "/Volumes/Home/.local/bin")
    }

    @Test func firstValidCandidateWinsAndTheShellIsNotConsulted() async {
        var machine = Machine()
        machine.executables = ["/Volumes/Home/.local/bin/metab", "/opt/homebrew/bin/metab"].reduce(into: homebrewTools) {
            $0.insert($1)
        }
        machine.versions = ["/Volumes/Home/.local/bin/metab": "metab 0.12.1"]
        let calls = Recorder<String>()
        let report = await RuntimeDiscovery.discover(machine.discovery(calls: calls))
        #expect(report.setup?.runtime == Runtime(
            executable: "/Volumes/Home/.local/bin/metab", version: "0.12.1", source: .localBin))
        #expect(report.setup?.tools == ToolPaths(git: "/opt/homebrew/bin/git", gh: "/opt/homebrew/bin/gh"))
        #expect(!report.consultedLoginShell)
        #expect(calls.all == ["/Volumes/Home/.local/bin/metab --exit-on-eof --version"])
    }

    @Test func brokenAndOlderCandidatesAreRecordedAndSkipped() async {
        var machine = Machine()
        machine.environment = ["METABROWSER_METAB": "/srv/metab"]
        machine.executables = homebrewTools.union(["/srv/metab", "/Volumes/Home/.local/bin/metab", "/opt/homebrew/bin/metab"])
        machine.versions = ["/Volumes/Home/.local/bin/metab": "metab 0.12.0", "/opt/homebrew/bin/metab": "metab 0.13.0"]
        let report = await RuntimeDiscovery.discover(machine.discovery(calls: Recorder()))
        #expect(report.setup?.runtime.executable == "/opt/homebrew/bin/metab")
        // ~/.local/bin is also uv's default tool directory, so it is tried once.
        #expect(report.tried.map(\.result) == [
            .rejected("--version printed: Traceback (most recent call last):"), .tooOld(version: "0.12.0"),
            .valid(version: "0.13.0"),
        ])
    }

    @Test func oneInstallReachedTwoWaysIsTriedOnce() async {
        var machine = Machine()
        machine.environment = ["METABROWSER_METAB": "/Volumes/Home/.local/bin/metab"]
        machine.executables = homebrewTools.union(["/Volumes/Home/.local/bin/metab"])
        machine.links = ["/Volumes/Home/.local/bin/metab": "/Volumes/Home/.local/share/uv/tools/metabrowser/bin/metab"]
        let calls = Recorder<String>()
        let report = await RuntimeDiscovery.discover(machine.discovery(calls: calls))
        #expect(report.setup == nil)
        // One validation of a broken install: the probe, then `--version` alone.
        #expect(calls.all.filter { $0.hasSuffix("--version") } == [
            "/Volumes/Home/.local/bin/metab --exit-on-eof --version", "/Volumes/Home/.local/bin/metab --version",
        ])
    }

    @Test func loginShellFindsWhatTheCheapLocationsMiss() async {
        var machine = Machine()
        machine.executables = ["/Volumes/Home/bin/metab", "/Volumes/Home/bin/gh", "/usr/bin/git"]
        machine.versions = ["/Volumes/Home/bin/metab": "metab 0.12.1"]
        machine.loginOutput = loginShellOutput(path: "/Volumes/Home/bin:/usr/bin:/bin")
        let calls = Recorder<String>()
        let report = await RuntimeDiscovery.discover(machine.discovery(calls: calls))
        #expect(report.consultedLoginShell)
        #expect(report.setup?.runtime == Runtime(
            executable: "/Volumes/Home/bin/metab", version: "0.12.1", source: .loginShell))
        #expect(report.setup?.tools == ToolPaths(git: "/usr/bin/git", gh: "/Volumes/Home/bin/gh"))
        #expect(calls.all.contains { $0.hasPrefix("/bin/zsh -l -i -c ") })
    }

    @Test func missingGhAloneConsultsTheShellButKeepsTheRuntime() async {
        var machine = Machine()
        machine.executables = ["/Volumes/Home/.local/bin/metab", "/opt/homebrew/bin/git"]
        machine.versions = ["/Volumes/Home/.local/bin/metab": "metab 0.12.1"]
        machine.loginOutput = loginShellOutput(path: "/usr/bin:/bin")
        let report = await RuntimeDiscovery.discover(machine.discovery(calls: Recorder()))
        #expect(report.consultedLoginShell)
        #expect(report.setup?.runtime.source == .localBin)
        #expect(report.setup?.tools == ToolPaths(git: "/opt/homebrew/bin/git", gh: nil))
    }

    @Test func nothingFoundReportsEveryPlaceLooked() async {
        let report = await RuntimeDiscovery.discover(Machine().discovery(calls: Recorder()))
        #expect(report.setup == nil)
        #expect(report.tried.map(\.path) == [
            "/Volumes/Home/.local/bin/metab", "/opt/homebrew/bin/metab", "/usr/local/bin/metab",
        ])
        #expect(report.tried.allSatisfy { $0.result == .missing })
    }

    @Test func loginPathIsReadOnlyBetweenTheMarkers() {
        #expect(RuntimeDiscovery.parseLoginPath(["PATH=/evil"]) == nil)
        #expect(RuntimeDiscovery.parseLoginPath(
            ["PATH=/before", RuntimeDiscovery.beginMarker, "PATH=/a:relative:/b", RuntimeDiscovery.endMarker])
            == ["/a", "/b"])
        #expect(RuntimeDiscovery.parseLoginPath([RuntimeDiscovery.beginMarker, "PATH=/a"]) == nil)
    }

    @Test func versionIsReadFromTheMetabLine() {
        #expect(RuntimeDiscovery.parseVersion(["metab 0.12.0"]) == "0.12.0")
        #expect(RuntimeDiscovery.parseVersion(["warning: x", "metab 0.11.1.dev12+abc (+3 commits)"])
            == "0.11.1.dev12+abc (+3 commits)")
        #expect(RuntimeDiscovery.parseVersion(["metab"]) == nil)
        #expect(RuntimeDiscovery.parseVersion(["Python 3.14.9"]) == nil)
    }

    @Test func toolsPreferTheLoginPathThenHomebrewThenTheSystemGit() {
        let executables: Set<String> = ["/a/git", "/opt/homebrew/bin/git", "/usr/bin/git", "/opt/homebrew/bin/gh"]
        let found = { (path: [String]?) in
            RuntimeDiscovery.resolveTools(loginPath: path, isExecutable: executables.contains)
        }
        #expect(found(["/a"]) == ToolPaths(git: "/a/git", gh: "/opt/homebrew/bin/gh"))
        #expect(found(nil) == ToolPaths(git: "/opt/homebrew/bin/git", gh: "/opt/homebrew/bin/gh"))
        let systemOnly = RuntimeDiscovery.resolveTools(loginPath: nil, isExecutable: { $0 == "/usr/bin/git" })
        #expect(systemOnly == ToolPaths(git: "/usr/bin/git", gh: nil))
    }
}

@Suite struct ChildEnvironmentTests {
    private let inherited = [
        "HOME": "/Volumes/Home", "USER": "someone", "LANG": "en_US.UTF-8", "TMPDIR": "/var/tmp/",
        "PATH": "/Volumes/Home/.venv/bin:/usr/bin", "VIRTUAL_ENV": "/Volumes/Home/.venv",
        "PYTHONPATH": "/src", "PYTHONHOME": "/py", "UV_INDEX_URL": "https://mirror.invalid",
        "UV_PYTHON": "3.9", "NODE_OPTIONS": "--inspect", "SSH_AUTH_SOCK": "/tmp/agent",
    ]

    @Test func keepsIdentityLocaleAgentAndProxiesAndDropsEverythingElse() {
        var parent = inherited
        parent["HTTPS_PROXY"] = "http://proxy.invalid:3128"
        parent["no_proxy"] = "localhost,127.0.0.1"
        let built = ChildEnvironment.build(inherited: parent, toolDirectories: [])
        #expect(built == [
            "HOME": "/Volumes/Home", "USER": "someone", "LANG": "en_US.UTF-8", "TMPDIR": "/var/tmp/",
            "SSH_AUTH_SOCK": "/tmp/agent", "HTTPS_PROXY": "http://proxy.invalid:3128",
            "no_proxy": "localhost,127.0.0.1",
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin", "PYTHONNOUSERSITE": "1", "PYTHONUNBUFFERED": "1",
        ])
    }

    @Test func everyProxySpellingPassesThrough() {
        let names = ["HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY"]
        for name in names + names.map({ $0.lowercased() }) {
            #expect(ChildEnvironment.build(inherited: [name: "x"], toolDirectories: [])[name] == "x")
        }
    }

    @Test func toolDirectoriesComeFirstOnAFixedPath() {
        let tools = ToolPaths(git: "/opt/homebrew/bin/git", gh: "/opt/homebrew/bin/gh")
        let built = ChildEnvironment.build(inherited: [:], toolDirectories: tools.directories + ["relative", "/a:b"])
        #expect(built["PATH"] == "/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin")
    }

    @Test func toolDirectoriesAreDistinctAndOrdered() {
        #expect(ToolPaths(git: "/usr/bin/git", gh: "/opt/homebrew/bin/gh").directories
            == ["/usr/bin", "/opt/homebrew/bin"])
        #expect(ToolPaths().directories.isEmpty)
    }
}

@Suite struct RuntimeSettingsTests {
    private func defaults() -> UserDefaults {
        let name = "shellcore-tests-\(UUID().uuidString)"
        let defaults = UserDefaults(suiteName: name)!
        defaults.removePersistentDomain(forName: name)
        return defaults
    }

    @Test func savedSetupRoundTripsAndIsUsableOnlyWhileExecutable() {
        let settings = RuntimeSettings(defaults: defaults())
        #expect(settings.load() == nil)
        let setup = RuntimeSetup(
            runtime: Runtime(executable: "/opt/homebrew/bin/metab", version: "0.12.0", source: .homebrew),
            tools: ToolPaths(git: "/usr/bin/git"))
        settings.save(setup)
        #expect(settings.load() == setup)
        #expect(settings.usable(isExecutable: { _ in true }, refusal: { _ in nil }) == setup)
        #expect(settings.usable(isExecutable: { _ in false }, refusal: { _ in nil }) == nil)
        settings.clear()
        #expect(settings.load() == nil)
    }

    @Test func aRelativeSavedPathIsNeverUsable() {
        let settings = RuntimeSettings(defaults: defaults())
        settings.save(RuntimeSetup(
            runtime: Runtime(executable: "bin/metab", version: "0.12.0", source: .chosen), tools: ToolPaths()))
        #expect(settings.usable(isExecutable: { _ in true }) == nil)
    }
}

/// Discovery ran `metab --version` on every executable candidate it found, Homebrew's and
/// the login shell's `PATH` entries among them, with no check of who can change it (review
/// D1 on #363, mb-3o3h): another account that controls one of those places could put a
/// `metab` there that runs as this user at launch, whatever it prints. Only a file the
/// user chose in Settings is run without `ExecutableTrust`.
@Suite struct DiscoveryTrustTests {
    private let shared = "/opt/homebrew/bin is writable by its group"

    @Test func aCandidateAnotherAccountCanChangeNeverReachesTheCommandRunner() async {
        var machine = Machine()
        machine.executables = homebrewTools.union(["/opt/homebrew/bin/metab", "/srv/shared/metab"])
        machine.versions = ["/opt/homebrew/bin/metab": "metab 0.13.0", "/srv/shared/metab": "metab 0.13.0"]
        machine.loginOutput = loginShellOutput(path: "/srv/shared:/usr/bin")
        machine.refused = [
            "/opt/homebrew/bin/metab": shared,
            "/srv/shared/metab": "/srv/shared/metab belongs to another account (uid 502)",
        ]
        let calls = Recorder<String>()
        let report = await RuntimeDiscovery.discover(machine.discovery(calls: calls))
        #expect(report.setup == nil)
        #expect(calls.all.allSatisfy { $0.hasPrefix("/bin/zsh ") }, "\(calls.all)")
        #expect(report.tried.filter { $0.result != .missing }.map(\.result) == [
            .untrusted(shared), .untrusted("/srv/shared/metab belongs to another account (uid 502)"),
        ])
    }

    /// A component whose security information or access control list could not be read is
    /// refused, not run.
    @Test func anUninspectableCandidateIsNotRun() async {
        var machine = Machine()
        machine.executables = homebrewTools.union(["/Volumes/Home/.local/bin/metab", "/opt/homebrew/bin/metab"])
        machine.versions = ["/Volumes/Home/.local/bin/metab": "metab 0.12.1", "/opt/homebrew/bin/metab": "metab 0.12.1"]
        machine.refused = [
            "/Volumes/Home/.local/bin/metab":
                "/Volumes/Home/.local/bin has an access control list that could not be read (Permission denied)",
        ]
        let calls = Recorder<String>()
        let report = await RuntimeDiscovery.discover(machine.discovery(calls: calls))
        #expect(report.setup?.runtime.executable == "/opt/homebrew/bin/metab")
        #expect(calls.all.filter { $0.hasSuffix("--version") } == ["/opt/homebrew/bin/metab --exit-on-eof --version"])
        #expect(report.tried.first?.result == .untrusted(
            "/Volumes/Home/.local/bin has an access control list that could not be read (Permission denied)"))
    }

    /// The live check reads the file system: a candidate in a folder its group can change
    /// is refused, and the command runner never sees it.
    @Test func theLiveCheckRefusesACandidateInAGroupWritableFolder() async throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let bin = directory.appending(path: "bin").path(percentEncoded: false)
        try FileManager.default.createDirectory(atPath: bin, withIntermediateDirectories: true)
        let metab = bin + "/metab"
        try Data("#!/bin/sh\necho metab 0.13.0\n".utf8).write(to: URL(filePath: metab))
        chmod(metab, 0o755)
        chmod(bin, 0o775)
        let ran = Recorder<String>()
        let env = DiscoveryEnvironment(
            home: directory.path(percentEncoded: false), environment: [:], saved: nil, shell: nil,
            isExecutable: FileChecks.isExecutableFile, canonicalPath: FileChecks.canonicalPath,
            run: { spec, _ in
                ran.append(spec.executable)
                return CommandResult(status: 0, output: ["metab 0.13.0"])
            })
        let result = await RuntimeDiscovery.validate(metab, env, source: .loginShell)
        guard case .untrusted(let reason) = result else {
            Issue.record("expected a refusal, got \(result)")
            return
        }
        #expect(reason.contains("can be changed by its group"))
        #expect(ran.all.isEmpty)
        chmod(bin, 0o755)
        #expect(await RuntimeDiscovery.validate(metab, env, source: .loginShell) == .valid(version: "0.13.0"))
        #expect(ran.all == [metab])
    }

    /// A runtime saved by an earlier search is found by the app too; one the user chose is
    /// run as chosen, whatever its folder, as Choose metab… runs it.
    @Test func aSavedRuntimeIsCheckedUnlessTheUserChoseIt() async {
        var machine = Machine()
        machine.executables = homebrewTools.union(["/opt/homebrew/bin/metab"])
        machine.versions = ["/opt/homebrew/bin/metab": "metab 0.13.0"]
        machine.refused = ["/opt/homebrew/bin/metab": shared]
        machine.saved = Runtime(executable: "/opt/homebrew/bin/metab", version: "0.13.0", source: .homebrew)
        let calls = Recorder<String>()
        let found = await RuntimeDiscovery.discover(machine.discovery(calls: calls))
        #expect(found.setup == nil)
        #expect(!calls.all.contains { $0.hasPrefix("/opt/homebrew/bin/metab ") })
        machine.saved?.source = .chosen
        let chosen = await RuntimeDiscovery.discover(machine.discovery(calls: calls))
        #expect(chosen.setup?.runtime.source == .chosen)
        #expect(calls.all.filter { $0.hasPrefix("/opt/homebrew/bin/metab ") }
            == ["/opt/homebrew/bin/metab --exit-on-eof --version"])
    }

    @Test func aFileTheUserChoseIsValidatedAsChosen() async {
        var machine = Machine()
        machine.executables = ["/srv/shared/metab"]
        machine.versions = ["/srv/shared/metab": "metab 0.13.0"]
        machine.refused = ["/srv/shared/metab": "/srv/shared/metab belongs to another account (uid 502)"]
        let env = machine.discovery(calls: Recorder())
        #expect(await RuntimeDiscovery.validate("/srv/shared/metab", env, source: .chosen) == .valid(version: "0.13.0"))
        #expect(await RuntimeDiscovery.validate("/srv/shared/metab", env) == .untrusted(
            "/srv/shared/metab belongs to another account (uid 502)"), "no source is one the app found")
    }

    /// A launch with a saved runtime runs no `--version`; a saved runtime the app found by
    /// itself that no longer passes the check is not used, so discovery runs and says why.
    @Test func aLaunchDoesNotUseASavedRuntimeThatFailsTheCheck() {
        let settings = RuntimeSettings(defaults: UserDefaults(suiteName: "shellcore-trust-\(UUID().uuidString)")!)
        let homebrew = RuntimeSetup(
            runtime: Runtime(executable: "/opt/homebrew/bin/metab", version: "0.13.0", source: .homebrew), tools: ToolPaths())
        settings.save(homebrew)
        let refuse: (String) -> String? = { _ in "/opt/homebrew/bin is writable by its group" }
        #expect(settings.usable(isExecutable: { _ in true }, refusal: refuse) == nil)
        #expect(settings.usable(isExecutable: { _ in true }, refusal: { _ in nil }) == homebrew)
        var chosen = homebrew
        chosen.runtime.source = .chosen
        settings.save(chosen)
        #expect(settings.usable(isExecutable: { _ in true }, refusal: refuse) == chosen)
    }
}

/// Validation ran `metab --version` alone, and `MetabRequirement` counts any 0.12.1
/// development build as the minimum, so a 0.12.1.dev38 built before `--exit-on-eof`
/// passed; every window then failed on click's "No such option: --exit-on-eof" with no
/// remedy (mb-sugi). Validation now runs `metab --exit-on-eof --version`, and a `metab`
/// that rejects the flag but answers `--version` alone is too old.
@Suite struct ServeFlagValidationTests {
    private let current = "metab 0.12.1.dev218+8b0603f7 (+218 commits, 8b0603f78)"
    private let beforeTheFlag = "metab 0.12.1.dev38+5f0c2a1 (+38 commits, 5f0c2a1)"
    /// The app's own environment: validation passes on only the minimal one.
    private let inherited = ["HOME": "/Volumes/Home", "PYTHONPATH": "/src", "VIRTUAL_ENV": "/Volumes/Home/.venv"]

    /// Validates `/opt/metab`, whose runs `answer` decides from their arguments, and
    /// records every run.
    private func validate(
        ran: Recorder<LaunchSpec>, _ answer: @escaping @Sendable ([String]) -> CommandResult
    ) async -> CandidateResult {
        let env = DiscoveryEnvironment(
            home: "/Volumes/Home", environment: inherited, saved: nil, shell: nil,
            isExecutable: { _ in true }, canonicalPath: { $0 },
            run: { spec, _ in
                ran.append(spec)
                return answer(spec.arguments)
            },
            refusal: { _ in nil })
        return await RuntimeDiscovery.validate("/opt/metab", env, source: .localBin)
    }

    /// A `metab` that rejects the flag as click does, and answers `--version` alone with
    /// `printed`.
    private static func predatingTheFlag(_ printed: [String]) -> @Sendable ([String]) -> CommandResult {
        { arguments in
            arguments.contains("--exit-on-eof")
                ? CommandResult(status: 2 << 8, output: clickUsageError) : CommandResult(status: 0, output: printed)
        }
    }

    @Test func aCurrentBuildAnswersTheProbeInOneRun() async {
        let ran = Recorder<LaunchSpec>()
        let printed = current
        let result = await validate(ran: ran) { _ in CommandResult(status: 0, output: [printed]) }
        #expect(result == .valid(version: "0.12.1.dev218+8b0603f7 (+218 commits, 8b0603f78)"))
        #expect(ran.all.map(\.arguments) == [["--exit-on-eof", "--version"]])
        #expect(ran.all.map(\.environment) == [ChildEnvironment.build(inherited: inherited, toolDirectories: [])])
    }

    /// The flag is the one every server gets, spelled the same.
    @Test func theProbeAsksForTheFlagTheServersGet() {
        #expect(CLIServeLaunch().arguments(serving: URL(filePath: "/tmp/notes/")).contains("--exit-on-eof"))
        #expect(CLIServeLaunch.exitOnEOF == "--exit-on-eof")
    }

    @Test func aDevelopmentBuildFromBeforeTheFlagIsTooOld() async {
        let ran = Recorder<LaunchSpec>()
        let result = await validate(ran: ran, Self.predatingTheFlag([beforeTheFlag]))
        #expect(result == .tooOld(version: "0.12.1.dev38+5f0c2a1 (+38 commits, 5f0c2a1)"))
        #expect(ran.all.map(\.arguments) == [["--exit-on-eof", "--version"], ["--version"]])
        // Both runs get the minimal environment a server gets.
        let minimal = ChildEnvironment.build(inherited: inherited, toolDirectories: [])
        #expect(ran.all.map(\.environment) == [minimal, minimal])
        // Its number meets the minimum, so the screens name the flag instead.
        #expect(MetabRequirement.flagShortfall("0.12.1.dev38+5f0c2a1 (+38 commits, 5f0c2a1)")
            == "built before --exit-on-eof")
    }

    /// 0.12.0, the published release, has no flag either; one that answered the probe
    /// would still be too old for its number.
    @Test func zeroTwelveZeroIsStillTooOld() async {
        let rejecting = Recorder<LaunchSpec>()
        #expect(await validate(ran: rejecting, Self.predatingTheFlag(["metab 0.12.0"])) == .tooOld(version: "0.12.0"))
        #expect(rejecting.count == 2)
        let answering = Recorder<LaunchSpec>()
        #expect(await validate(ran: answering) { _ in CommandResult(status: 0, output: ["metab 0.12.0"]) }
            == .tooOld(version: "0.12.0"))
        #expect(answering.count == 1)
        #expect(MetabRequirement.flagShortfall("0.12.0") == nil)
    }

    /// A probe that fails for another reason leads to `--version` alone, whose output the
    /// rejection names, as before the probe.
    @Test func whenBothRunsFailTheRejectionNamesTheSecond() async {
        let broken = await validate(ran: Recorder()) { arguments in
            arguments.contains("--exit-on-eof")
                ? CommandResult(status: 1 << 8, output: ["Traceback (most recent call last):", "ImportError: probe"])
                : CommandResult(status: 1 << 8, output: ["Traceback (most recent call last):", "ImportError: plain"])
        }
        #expect(broken == .rejected("--version printed: ImportError: plain"))
        let unreadable = await validate(ran: Recorder(), Self.predatingTheFlag(["metab soon"]))
        #expect(unreadable == .rejected("--version printed a version this app cannot read: soon"))
        let silent = await validate(ran: Recorder(), Self.predatingTheFlag([]))
        #expect(silent == .rejected("--version printed: nothing"))
        let plainTimesOut = Recorder<LaunchSpec>()
        let stalled = await validate(ran: plainTimesOut) { arguments in
            arguments.contains("--exit-on-eof")
                ? CommandResult(status: 2 << 8, output: clickUsageError)
                : CommandResult(status: nil, output: [], timedOut: true)
        }
        #expect(stalled == .rejected("--version did not finish within \(RuntimeDiscovery.versionTimeout)"))
        #expect(plainTimesOut.count == 2)
    }

    /// A probe that did not finish is rejected as before, and nothing more runs.
    @Test func aProbeThatTimesOutOrCannotStartRunsNothingMore() async {
        let timedOut = Recorder<LaunchSpec>()
        #expect(await validate(ran: timedOut) { _ in CommandResult(status: nil, output: [], timedOut: true) }
            == .rejected("--version did not finish within \(RuntimeDiscovery.versionTimeout)"))
        #expect(timedOut.all.map(\.arguments) == [["--exit-on-eof", "--version"]])
        let unstarted = Recorder<LaunchSpec>()
        #expect(await validate(ran: unstarted) { _ in CommandResult(status: nil, output: [], launchError: "EACCES") }
            == .rejected("could not run: EACCES"))
        #expect(unstarted.count == 1)
    }

    /// The machine the defect was found on: uv's tool directory holds the old build, and
    /// discovery goes on to a `metab` that has the flag.
    @Test func discoveryPassesOverABuildFromBeforeTheFlag() async {
        var machine = Machine()
        let local = "/Volumes/Home/.local/bin/metab"
        machine.executables = homebrewTools.union([local, "/opt/homebrew/bin/metab"])
        machine.versions = [local: beforeTheFlag, "/opt/homebrew/bin/metab": current]
        machine.predatingFlag = [local]
        let calls = Recorder<String>()
        let report = await RuntimeDiscovery.discover(machine.discovery(calls: calls))
        #expect(report.setup?.runtime == Runtime(
            executable: "/opt/homebrew/bin/metab", version: "0.12.1.dev218+8b0603f7 (+218 commits, 8b0603f78)",
            source: .homebrew))
        #expect(report.tried.map(\.result) == [
            .tooOld(version: "0.12.1.dev38+5f0c2a1 (+38 commits, 5f0c2a1)"),
            .valid(version: "0.12.1.dev218+8b0603f7 (+218 commits, 8b0603f78)"),
        ])
        #expect(calls.all == [
            local + " --exit-on-eof --version", local + " --version", "/opt/homebrew/bin/metab --exit-on-eof --version",
        ])
        // With nothing newer, the first-run screen names the flag rather than the number.
        machine.executables.remove("/opt/homebrew/bin/metab")
        let alone = await RuntimeDiscovery.discover(machine.discovery(calls: Recorder()))
        #expect(alone.setup == nil)
        let guide = SetupGuide(
            tried: alone.tried, uv: "/Volumes/Home/.local/bin/uv", binDirectory: "/Volumes/Home/.local/bin",
            home: "/Volumes/Home", loginPath: ["/Volumes/Home/.local/bin"], hasHomebrew: false,
            minimumIsReleased: false)
        #expect(guide.steps == [.buildFromCheckout(
            oldPath: local, oldVersion: "0.12.1.dev38+5f0c2a1 (+38 commits, 5f0c2a1)", inNewTerminal: false)])
        #expect(guide.steps.first?.title(home: "/Volumes/Home").contains(
            "~/.local/bin/metab is metab 0.12.1.dev38+5f0c2a1, built before --exit-on-eof, and") == true)
    }

    /// The same check against a real process: a script that answers as click does, from
    /// its own stderr and exit status, through the app's command runner.
    @Test func aRealProcessThatRejectsTheFlagIsTooOld() async throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let metab = directory.appending(path: "metab").path(percentEncoded: false)
        let script = """
            #!/bin/sh
            for argument in "$@"; do
              if [ "$argument" = --exit-on-eof ]; then
                printf '%s\\n' "Usage: metab [OPTIONS] [ROOT]" "Try 'metab --help' for help." "" \\
                  "Error: No such option: --exit-on-eof" >&2
                exit 2
              fi
            done
            echo "\(beforeTheFlag)"

            """
        try Data(script.utf8).write(to: URL(filePath: metab))
        chmod(metab, 0o755)
        let results = Recorder<CommandResult>()
        let env = DiscoveryEnvironment(
            home: directory.path(percentEncoded: false), environment: ProcessInfo.processInfo.environment,
            saved: nil, shell: nil, isExecutable: FileChecks.isExecutableFile, canonicalPath: FileChecks.canonicalPath,
            run: { spec, limit in
                let result = await CommandRunner.live(spec, limit)
                results.append(result)
                return result
            },
            refusal: { _ in nil })
        #expect(await RuntimeDiscovery.validate(metab, env) == .tooOld(
            version: "0.12.1.dev38+5f0c2a1 (+38 commits, 5f0c2a1)"))
        let probe = try #require(results.all.first)
        #expect(probe.status.map(ExitStatus.init(waitStatus:)) == .exited(2))
        #expect(probe.output.last == "Error: No such option: --exit-on-eof")
        #expect(results.count == 2)
    }
}
