import Foundation
import Testing
@testable import ShellCore

/// A fake machine: which files are executable, where symlinks point, and what each
/// command prints.
private struct Machine {
    var executables: Set<String> = []
    var links: [String: String] = [:]
    var versions: [String: String] = [:]  // executable → `--version` output
    var loginOutput: [String]? = nil
    var environment: [String: String] = [:]
    var saved: Runtime? = nil

    func discovery(calls: Recorder<String>) -> DiscoveryEnvironment {
        let executables = executables
        let links = links
        let versions = versions
        let loginOutput = loginOutput
        return DiscoveryEnvironment(
            home: "/Volumes/Home", environment: environment, saved: saved, shell: "/bin/zsh",
            isExecutable: { executables.contains($0) || $0 == "/bin/zsh" },
            canonicalPath: { links[$0] ?? $0 },
            run: { spec, _ in
                calls.append(([spec.executable] + spec.arguments).joined(separator: " "))
                if spec.executable == "/bin/zsh" {
                    return CommandResult(status: loginOutput == nil ? 256 : 0, output: loginOutput ?? [])
                }
                guard let version = versions[spec.executable] else {
                    return CommandResult(status: 1 << 8, output: ["Traceback (most recent call last):"])
                }
                return CommandResult(status: 0, output: [version])
            })
    }
}

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
        #expect(calls.all == ["/Volumes/Home/.local/bin/metab --version"])
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
        #expect(calls.all.filter { $0.hasSuffix("--version") }.count == 1)
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
        #expect(settings.usable(isExecutable: { _ in true }) == setup)
        #expect(settings.usable(isExecutable: { _ in false }) == nil)
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
