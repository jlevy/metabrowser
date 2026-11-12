import Darwin
import Foundation

/// What discovery may look at. Tests substitute every field.
public nonisolated struct DiscoveryEnvironment: Sendable {
    public var home: String
    /// This app's own environment. A Finder launch has almost nothing here.
    public var environment: [String: String]
    /// The previously saved runtime, tried first.
    public var saved: Runtime?
    /// The user's login shell, an absolute path.
    public var shell: String?
    public var isExecutable: @Sendable (String) -> Bool
    public var canonicalPath: @Sendable (String) -> String
    public var run: CommandRunner.Run
    public var fingerprint: @Sendable (String) -> FileFingerprint?
    /// Why a candidate the app found by itself may not be run, or nil if it may
    /// (`ExecutableTrust`).
    public var refusal: @Sendable (String) -> String?

    public init(
        home: String, environment: [String: String], saved: Runtime?, shell: String?,
        isExecutable: @escaping @Sendable (String) -> Bool,
        canonicalPath: @escaping @Sendable (String) -> String,
        run: @escaping CommandRunner.Run,
        fingerprint: @escaping @Sendable (String) -> FileFingerprint? = { _ in nil },
        refusal: @escaping @Sendable (String) -> String? = { ExecutableTrust.refusal($0) }
    ) {
        self.home = home
        self.environment = environment
        self.saved = saved
        self.shell = shell
        self.isExecutable = isExecutable
        self.canonicalPath = canonicalPath
        self.run = run
        self.fingerprint = fingerprint
        self.refusal = refusal
    }

    /// `home` is `HOME` when the app has one, as uv reads it to place `~/.local/bin`, so
    /// discovery looks where uv installs; a Finder launch's `HOME` is the account's own.
    public static func live(saved: Runtime?) -> DiscoveryEnvironment {
        let environment = ProcessInfo.processInfo.environment
        let home = environment["HOME"].flatMap { $0.hasPrefix("/") ? $0 : nil } ?? NSHomeDirectory()
        return DiscoveryEnvironment(
            home: home, environment: environment, saved: saved,
            shell: environment["SHELL"] ?? passwordDatabaseShell(),
            isExecutable: FileChecks.isExecutableFile, canonicalPath: FileChecks.canonicalPath,
            run: CommandRunner.live, fingerprint: FileFingerprint.of)
    }

    private static func passwordDatabaseShell() -> String? {
        guard let entry = getpwuid(getuid()), let shell = entry.pointee.pw_shell else { return nil }
        return String(cString: shell)
    }
}

public nonisolated enum CandidateResult: Equatable, Sendable {
    case valid(version: String)
    case missing
    /// A working `metab` older than `MetabRequirement.minimum`, or, whatever its number,
    /// one built before `CLIServeLaunch.exitOnEOF`, which it rejects as an unknown option
    /// (`RuntimeDiscovery.rejectsServeFlag`, `MetabRequirement.flagShortfall`).
    case tooOld(version: String)
    case rejected(String)
    /// Not run: the app found it by itself, and another account can change it, or it could
    /// not be examined (`ExecutableTrust`).
    case untrusted(String)
}

public nonisolated struct CandidateOutcome: Equatable, Sendable {
    public var path: String
    public var source: RuntimeSource
    public var result: CandidateResult
}

public nonisolated struct DiscoveryReport: Equatable, Sendable {
    /// The first valid runtime and the tools, or nil when no `metab` was found.
    public var setup: RuntimeSetup?
    /// Every candidate looked at, in order, for the Settings window.
    public var tried: [CandidateOutcome]
    /// The login shell's `PATH`, when the search consulted the shell and it answered.
    public var loginPath: [String]?

    public var consultedLoginShell: Bool { loginPath != nil }
}

/// Finds the user's CLI install of `metab` once, at setup.
///
/// It runs only a candidate no other account can change (`ExecutableTrust`), since running
/// `--version` executes it; one it refuses is recorded as `.untrusted`, with the reason,
/// for Settings, the log, and the first-run steps.
///
/// Cheap locations come first, each a file check plus `metab --exit-on-eof --version`
/// (`validate`): the saved path, `METABROWSER_METAB`, `~/.local/bin`, uv's tool bin
/// directory, and the Homebrew prefixes. The login shell is consulted only when they do
/// not answer for `metab`, `git`, or `gh`, because it runs the user's shell startup files
/// in this app's name, which can take seconds and can raise privacy prompts the user
/// never saw in Terminal.
public nonisolated enum RuntimeDiscovery {
    public static let homebrewBins = ["/opt/homebrew/bin", "/usr/local/bin"]
    public static let installCommand = "uv tool install metabrowser"
    /// A first run after `uv tool install` compiles bytecode, so `--version` can take
    /// seconds; one that takes longer than this is broken.
    static let versionTimeout: Duration = .seconds(20)
    /// A login shell whose startup files take longer is given up on, and setup goes on
    /// without its `PATH`.
    static let shellTimeout: Duration = .seconds(8)
    /// Settings > Run Doctor stops `metab --doctor` after this, so a check stuck on a
    /// hung tool or network leaves the window usable.
    public static let doctorTimeout: Duration = .seconds(60)
    static let beginMarker = "__METABROWSER_LOGIN_ENV_BEGIN__"
    static let endMarker = "__METABROWSER_LOGIN_ENV_END__"

    public static func discover(_ env: DiscoveryEnvironment) async -> DiscoveryReport {
        var tried: [CandidateOutcome] = []
        var seen: Set<String> = []

        func firstValid(_ candidates: [(String, RuntimeSource)]) async -> Runtime? {
            for (path, source) in candidates {
                let canonical = env.isExecutable(path) ? env.canonicalPath(path) : path
                guard seen.insert(canonical).inserted else { continue }
                let fingerprint = env.fingerprint(path)
                let result = await validate(path, env, source: source)
                tried.append(CandidateOutcome(path: path, source: source, result: result))
                if case .valid(let version) = result {
                    return Runtime(executable: path, version: version, source: source, fingerprint: fingerprint)
                }
            }
            return nil
        }

        var runtime = await firstValid(cheapCandidates(env))
        var tools = resolveTools(loginPath: nil, isExecutable: env.isExecutable)
        let needsShell = runtime == nil || tools.gh == nil
            || !(tools.git.map { homebrewBins.contains(($0 as NSString).deletingLastPathComponent) } ?? false)
        var consulted: [String]?
        if needsShell, let loginPath = await loginShellPath(env) {
            consulted = loginPath
            if runtime == nil {
                runtime = await firstValid(loginPath.map { ($0 + "/metab", .loginShell) })
            }
            tools = resolveTools(loginPath: loginPath, isExecutable: env.isExecutable)
        }
        return DiscoveryReport(
            setup: runtime.map { RuntimeSetup(runtime: $0, tools: tools) }, tried: tried, loginPath: consulted)
    }

    /// The candidates that cost only a file check, in order.
    public static func cheapCandidates(_ env: DiscoveryEnvironment) -> [(String, RuntimeSource)] {
        var candidates: [(String, RuntimeSource)] = []
        if let saved = env.saved { candidates.append((saved.executable, saved.source)) }
        if let explicit = env.environment["METABROWSER_METAB"], explicit.hasPrefix("/") {
            candidates.append((explicit, .environment))
        }
        candidates.append((env.home + "/.local/bin/metab", .localBin))
        candidates.append((uvToolBinDirectory(env) + "/metab", .uvToolBin))
        candidates += homebrewBins.map { ($0 + "/metab", .homebrew) }
        return candidates
    }

    /// uv's documented rule for where `uv tool install` puts executables:
    /// `UV_TOOL_BIN_DIR`, else `XDG_BIN_HOME`, else `XDG_DATA_HOME/../bin`, else
    /// `~/.local/bin`. A Finder launch usually has none of these variables, which is
    /// one reason the login shell is the last resort.
    public static func uvToolBinDirectory(_ env: DiscoveryEnvironment) -> String {
        let variables = env.environment
        if let directory = variables["UV_TOOL_BIN_DIR"], directory.hasPrefix("/") { return directory }
        if let directory = variables["XDG_BIN_HOME"], directory.hasPrefix("/") { return directory }
        if let data = variables["XDG_DATA_HOME"], data.hasPrefix("/") {
            return ((data as NSString).deletingLastPathComponent as NSString).appendingPathComponent("bin")
        }
        return env.home + "/.local/bin"
    }

    /// Runs `metab --exit-on-eof --version` with the same minimal environment a server
    /// gets, and holds the version to `MetabRequirement`.
    ///
    /// The flag is the one every server gets (`CLIServeLaunch.exitOnEOF`), and a version
    /// number cannot show it: a development build of the minimum from before the flag
    /// counts as the minimum. Click rejects an unknown option before the eager `--version`
    /// runs, so such a build exits 2 and names the flag (`rejectsServeFlag`). Only then
    /// does `--version` run alone, and a version this app reads from it makes the `metab`
    /// too old whatever its number. Any other failed probe shows nothing about when the
    /// build was made, so it is rejected with its own output and nothing more runs; so is
    /// a probe that could not start or did not finish. A current `metab` costs one run.
    ///
    /// Running it executes the file, whatever it prints, so a file the app found by itself
    /// (every `source` but `.chosen`, and no source at all) runs only if no other account
    /// can change it (`env.refusal`, `ExecutableTrust`): discovery's candidates, a saved
    /// runtime discovery found, and a recheck of one. That is checked just before each
    /// run, since a folder on the path can become writable by its group, or a link on it
    /// lead elsewhere, while the probe runs. A file the user chose in Settings is run as
    /// chosen.
    public static func validate(
        _ path: String, _ env: DiscoveryEnvironment, source: RuntimeSource? = nil
    ) async -> CandidateResult {
        func barred() -> CandidateResult? {
            guard env.isExecutable(path) else { return .missing }
            if source != .chosen, let reason = env.refusal(path) { return .untrusted(reason) }
            return nil
        }
        if let barred = barred() { return barred }
        let environment = ChildEnvironment.build(inherited: env.environment, toolDirectories: [])
        func run(_ arguments: [String]) async -> CommandResult {
            await env.run(LaunchSpec(executable: path, arguments: arguments, environment: environment), versionTimeout)
        }
        func unfinished(_ result: CommandResult) -> CandidateResult? {
            if let error = result.launchError { return .rejected("could not run: \(error)") }
            if result.timedOut { return .rejected("--version did not finish within \(versionTimeout)") }
            return nil
        }
        func reading(_ result: CommandResult, _ judge: (String, MetabVersion) -> CandidateResult) -> CandidateResult {
            guard result.succeeded, let version = parseVersion(result.output) else {
                return .rejected("--version printed: \(result.output.last ?? "nothing")")
            }
            guard let parsed = MetabVersion(version) else {
                return .rejected("--version printed a version this app cannot read: \(version)")
            }
            return judge(version, parsed)
        }
        let probe = await run([CLIServeLaunch.exitOnEOF, "--version"])
        if let rejection = unfinished(probe) { return rejection }
        if probe.succeeded {
            return reading(probe) { MetabRequirement.accepts($1) ? .valid(version: $0) : .tooOld(version: $0) }
        }
        guard rejectsServeFlag(probe) else {
            return .rejected("\(CLIServeLaunch.exitOnEOF) --version printed: \(probe.output.last ?? "nothing")")
        }
        if let barred = barred() { return barred }
        let plain = await run(["--version"])
        if let rejection = unfinished(plain) { return rejection }
        return reading(plain) { version, _ in .tooOld(version: version) }
    }

    /// Whether `result` is click's rejection of `CLIServeLaunch.exitOnEOF` as an unknown
    /// option: exit status 2, with the flag named in what it printed. The wording around
    /// the flag is click's and is not matched. A crash, a signal, or another usage error is
    /// not one, and shows nothing about when the build was made.
    static func rejectsServeFlag(_ result: CommandResult) -> Bool {
        guard let status = result.status, ExitStatus(waitStatus: status) == .exited(2) else { return false }
        return result.output.contains { $0.contains(CLIServeLaunch.exitOnEOF) }
    }

    /// `metab 0.12.0` → `0.12.0`. A checkout prints a longer description after it.
    public static func parseVersion(_ output: [String]) -> String? {
        for line in output {
            let text = line.trimmingCharacters(in: .whitespaces)
            guard text.hasPrefix("metab ") else { continue }
            let version = text.dropFirst("metab ".count).trimmingCharacters(in: .whitespaces)
            if !version.isEmpty { return version }
        }
        return nil
    }

    /// `git` and `gh` from the login shell's `PATH` when there is one, then Homebrew;
    /// `git` falls back to `/usr/bin/git`, the Command Line Tools shim.
    public static func resolveTools(loginPath: [String]?, isExecutable: (String) -> Bool) -> ToolPaths {
        func find(_ name: String, after extra: [String]) -> String? {
            var directories: [String] = []
            for directory in (loginPath ?? []) + homebrewBins + extra where !directories.contains(directory) {
                directories.append(directory)
            }
            return directories.lazy.map { $0 + "/" + name }.first(where: isExecutable)
        }
        return ToolPaths(git: find("git", after: ["/usr/bin"]), gh: find("gh", after: []))
    }

    /// The `PATH` an interactive login shell builds, which is where Terminal finds
    /// `metab`, `git`, and `gh`. Runs `env` rather than `command -v`, so it works the
    /// same in bash, zsh, and fish.
    public static func loginShellPath(_ env: DiscoveryEnvironment) async -> [String]? {
        guard let shell = env.shell, shell.hasPrefix("/"), env.isExecutable(shell) else { return nil }
        let script = #"/usr/bin/printf '\n%s\n' "# + beginMarker + #"; /usr/bin/env; /usr/bin/printf '\n%s\n' "#
            + endMarker
        var environment = ChildEnvironment.build(inherited: env.environment, toolDirectories: [])
        environment["SHELL"] = shell
        environment["TERM"] = "dumb"
        let spec = LaunchSpec(
            executable: shell, arguments: ["-l", "-i", "-c", script], environment: environment,
            workingDirectory: env.home)
        return parseLoginPath(await env.run(spec, shellTimeout).output)
    }

    /// The `PATH=` line between the markers, so startup-file chatter is ignored.
    public static func parseLoginPath(_ lines: [String]) -> [String]? {
        guard let begin = lines.firstIndex(of: beginMarker),
              let end = lines[begin...].firstIndex(of: endMarker),
              let line = lines[begin..<end].first(where: { $0.hasPrefix("PATH=") })
        else { return nil }
        let directories = line.dropFirst("PATH=".count).split(separator: ":").map(String.init)
            .filter { $0.hasPrefix("/") }
        return directories.isEmpty ? nil : directories
    }
}
