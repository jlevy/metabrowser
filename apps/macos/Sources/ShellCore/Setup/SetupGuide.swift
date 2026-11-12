import Foundation

/// What a Mac without a usable `metab` still needs, as the first-run screen shows it:
/// only the missing steps, each a command to copy, in the order to run them.
///
/// Every path ends in Flow 1's CLI install (`uv tool install metabrowser`), which the
/// app then finds with a file check; the setup flows brief's option (i).
public nonisolated struct SetupGuide: Equatable, Sendable {
    public enum Step: Equatable, Sendable {
        case installUv(homebrew: Bool)
        /// `afterUv`: the step before it installs uv.
        case installMetab(afterUv: Bool)
        /// A `metab` in uv's tool directory that does not run.
        case reinstallMetab(path: String, reason: String)
        /// A working `metab` older than `MetabRequirement.minimum`.
        case upgradeMetab(path: String, version: String, afterUv: Bool)

        /// What the step does, with paths under `home` written with `~`.
        public func title(home: String) -> String {
            switch self {
            case .installUv:
                return "Install uv, which installs and updates metab."
            case .installMetab:
                return "Install metab."
            case .reinstallMetab(let path, let reason):
                return "Reinstall metab: \(FolderIdentity.abbreviatingHome(path, home: home)) does not run (\(reason))."
            case .upgradeMetab(let path, let version, _):
                let shown = MetabVersion(version)?.text ?? version
                return "Upgrade metab: \(FolderIdentity.abbreviatingHome(path, home: home)) is metab \(shown),"
                    + " and Metabrowser needs \(MetabRequirement.minimum) or later."
            }
        }

        /// uv's official installer, or uv's documented tool commands.
        public var command: String {
            switch self {
            case .installUv: "curl -LsSf https://astral.sh/uv/install.sh | sh"
            case .installMetab: RuntimeDiscovery.installCommand
            case .reinstallMetab: "uv tool install --reinstall metabrowser"
            case .upgradeMetab: MetabRequirement.upgradeCommand
            }
        }

        /// Another command that does the same, when this Mac has what it needs.
        public var alternative: String? {
            if case .installUv(homebrew: true) = self { return "brew install uv" }
            return nil
        }

        /// What to know before running the command. uv's installer adds its directory to
        /// `PATH` in the shell's startup files, which the Terminal window that ran it has
        /// already read.
        public var note: String? {
            switch self {
            case .installMetab(afterUv: true), .upgradeMetab(_, _, afterUv: true):
                "In a new Terminal window, so that it finds uv:"
            default: nil
            }
        }
    }

    public static let updateShellCommand = "uv tool update-shell"

    public var steps: [Step]

    public var heading: String {
        let upgrading = steps.contains { if case .upgradeMetab = $0 { true } else { false } }
        return upgrading
            ? "Metabrowser needs metab \(MetabRequirement.minimum) or later"
            : "Metabrowser needs the metab command-line tool"
    }

    /// Where uv installs `metab`, which the app watches.
    public var binDirectory: String
    /// The home folder discovery used, for writing paths with `~`.
    public var home: String
    /// Whether to suggest `uv tool update-shell`, so `metab` also runs in Terminal: the
    /// login shell's `PATH` lacks `binDirectory`, or is unknown. The app needs neither.
    public var suggestsUpdateShell: Bool

    /// `tried` is the last search's candidates, `uv` the uv found, if any, and
    /// `loginPath` the login shell's `PATH`, when the search read it.
    public init(
        tried: [CandidateOutcome], uv: String?, binDirectory: String, home: String, loginPath: [String]?,
        hasHomebrew: Bool
    ) {
        let needsUv = uv == nil
        var steps: [Step] = needsUv ? [.installUv(homebrew: hasHomebrew)] : []
        let toolMetab = binDirectory + "/metab"
        if let old = tried.lazy.compactMap({ outcome -> (String, String)? in
            if case .tooOld(let version) = outcome.result { return (outcome.path, version) }
            return nil
        }).first {
            steps.append(.upgradeMetab(path: old.0, version: old.1, afterUv: needsUv))
        } else if let broken = tried.lazy.compactMap({ outcome -> String? in
            if case .rejected(let reason) = outcome.result, outcome.path == toolMetab { return reason }
            return nil
        }).first {
            steps.append(.reinstallMetab(path: toolMetab, reason: broken))
        } else {
            steps.append(.installMetab(afterUv: needsUv))
        }
        self.steps = steps
        self.binDirectory = binDirectory
        self.home = home
        suggestsUpdateShell = !(loginPath?.contains(binDirectory) ?? false)
    }

    /// Where uv may be, in order: where its installer puts it (`XDG_BIN_HOME`, then
    /// `XDG_DATA_HOME/../bin`, then `~/.local/bin`), the Homebrew prefixes, and then the
    /// login shell's `PATH`, which reaches any other install the user's Terminal finds.
    public static func uvCandidates(home: String, environment: [String: String], loginPath: [String]?) -> [String] {
        var directories: [String] = []
        if let directory = environment["XDG_BIN_HOME"], directory.hasPrefix("/") { directories.append(directory) }
        if let data = environment["XDG_DATA_HOME"], data.hasPrefix("/") {
            directories.append((data as NSString).deletingLastPathComponent + "/bin")
        }
        directories.append(home + "/.local/bin")
        directories += RuntimeDiscovery.homebrewBins + (loginPath ?? [])
        var candidates: [String] = []
        for directory in directories where !candidates.contains(directory + "/uv") {
            candidates.append(directory + "/uv")
        }
        return candidates
    }
}

/// Asks uv where `uv tool install` puts executables, which is where the app waits for
/// `metab`.
public nonisolated enum UvToolDirectory {
    public enum Answer: Equatable, Sendable {
        case directory(String)
        case failed(String)
    }

    static let timeout: Duration = .seconds(15)
    /// The variables uv's rule for the directory reads. The rest of the app's
    /// environment is left out, as it is for every child.
    static let locationVariables = ["UV_TOOL_BIN_DIR", "XDG_BIN_HOME", "XDG_DATA_HOME"]

    public static func spec(uv: String, home: String, inherited: [String: String]) -> LaunchSpec {
        var environment = ChildEnvironment.build(inherited: inherited, toolDirectories: [])
        for name in locationVariables {
            if let value = inherited[name] { environment[name] = value }
        }
        return LaunchSpec(
            executable: uv, arguments: ["tool", "dir", "--bin"], environment: environment, workingDirectory: home)
    }

    /// The last line uv printed, which must be an absolute path.
    public static func parse(_ result: CommandResult) -> Answer {
        if let error = result.launchError { return .failed("could not run uv: \(error)") }
        if result.timedOut { return .failed("uv tool dir --bin did not finish within \(timeout)") }
        let last = result.output.last(where: { !$0.trimmingCharacters(in: .whitespaces).isEmpty }) ?? "nothing"
        guard result.succeeded, last.hasPrefix("/") else { return .failed("uv tool dir --bin printed: \(last)") }
        return .directory(last)
    }

    public static func ask(uv: String, env: DiscoveryEnvironment) async -> Answer {
        parse(await env.run(spec(uv: uv, home: env.home, inherited: env.environment), timeout))
    }
}
