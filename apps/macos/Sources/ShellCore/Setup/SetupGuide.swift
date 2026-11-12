import Foundation

/// What a Mac without a usable `metab` still needs, as the first-run screen shows it:
/// only the missing steps, each a command to copy, in the order to run them.
///
/// Once `MetabRequirement.minimum` is on PyPI, every path ends in Flow 1's CLI install
/// (`uv tool install metabrowser`), which the app then finds with a file check; the
/// setup flows brief's option (i). Until then uv installs only older releases, so the
/// steps end in the source checkout the app was built from, and Choose metab….
public nonisolated struct SetupGuide: Equatable, Sendable {
    public enum Step: Equatable, Sendable {
        case installUv(homebrew: Bool)
        /// `inNewTerminal`: run it in a new Terminal window, which finds uv.
        case installMetab(inNewTerminal: Bool)
        /// A `metab` in uv's tool directory that does not run.
        case reinstallMetab(path: String, reason: String, inNewTerminal: Bool)
        /// A working `metab` older than `MetabRequirement.minimum`.
        case upgradeMetab(path: String, version: String, inNewTerminal: Bool)
        /// The minimum is not on PyPI yet: `make install` in the checkout, then Choose
        /// metab…. `oldPath` and `oldVersion` name an older `metab` found, if any.
        case buildFromCheckout(oldPath: String?, oldVersion: String?, inNewTerminal: Bool)

        /// What the step does, with paths under `home` written with `~`.
        public func title(home: String) -> String {
            func shown(_ path: String) -> String { FolderIdentity.abbreviatingHome(path, home: home) }
            switch self {
            case .installUv:
                return "Install uv, which installs and updates metab."
            case .installMetab:
                return "Install metab."
            case .reinstallMetab(let path, let reason, _):
                return "Reinstall metab: \(shown(path)) does not run (\(reason))."
            case .upgradeMetab(let path, let version, _):
                return "Upgrade metab: \(shown(path)) is metab \(MetabVersion(version)?.text ?? version),"
                    + " and Metabrowser needs \(MetabRequirement.minimum) or later."
            case .buildFromCheckout(let oldPath, let oldVersion, _):
                var found = ""
                if let oldPath, let oldVersion {
                    found = "\(shown(oldPath)) is metab \(MetabVersion(oldVersion)?.text ?? oldVersion), and "
                }
                return "Build metab in the source checkout this app was built from, then choose its .venv/bin/metab"
                    + " with Choose metab… below: \(found)Metabrowser needs metab \(MetabRequirement.minimum) or"
                    + " later, which is not on PyPI yet."
            }
        }

        /// uv's official installer, uv's documented tool commands, or the checkout's
        /// install target.
        public var command: String {
            switch self {
            case .installUv: "curl -LsSf https://astral.sh/uv/install.sh | sh"
            case .installMetab: RuntimeDiscovery.installCommand
            case .reinstallMetab: "uv tool install --reinstall metabrowser"
            case .upgradeMetab: MetabRequirement.upgradeCommand
            case .buildFromCheckout: "make install"
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
            case .installUv: nil
            case .installMetab(let inNewTerminal), .reinstallMetab(_, _, let inNewTerminal),
                 .upgradeMetab(_, _, let inNewTerminal):
                inNewTerminal ? "In a new Terminal window, so that it finds uv:" : nil
            case .buildFromCheckout(_, _, let inNewTerminal):
                inNewTerminal
                    ? "In a new Terminal window, so that it finds uv, at the root of the checkout:"
                    : "At the root of the checkout:"
            }
        }
    }

    public static let updateShellCommand = "uv tool update-shell"

    public var steps: [Step]

    public var heading: String {
        let needsVersion = steps.contains {
            switch $0 {
            case .upgradeMetab, .buildFromCheckout: true
            default: false
            }
        }
        return needsVersion
            ? "Metabrowser needs metab \(MetabRequirement.minimum) or later"
            : "Metabrowser needs the metab command-line tool"
    }

    /// Whether the last step is Choose metab…, rather than an install the app notices.
    public var endsWithChoice: Bool {
        steps.contains { if case .buildFromCheckout = $0 { true } else { false } }
    }

    /// Where uv installs `metab`, which the app watches.
    public var binDirectory: String
    /// The home folder discovery used, for writing paths with `~`.
    public var home: String
    /// Whether to suggest `uv tool update-shell`, so `metab` also runs in Terminal: the
    /// login shell's `PATH` lacks `binDirectory`, or is unknown. The app needs neither.
    public var suggestsUpdateShell: Bool
    /// What the screen says besides the steps: each uv and each `metab` the app found and
    /// would not run (`ExecutableTrust`).
    public var notices: [String]

    /// `tried` is the last search's candidates, `uv` the uv found, if any, whether or
    /// not the app may run it, and `loginPath` the login shell's `PATH`, when the search
    /// read it. `refusedUv` lists the uvs the app would not run, and why.
    public init(
        tried: [CandidateOutcome], uv: String?, binDirectory: String, home: String, loginPath: [String]?,
        hasHomebrew: Bool, minimumIsReleased: Bool = MetabRequirement.isReleased, refusedUv: [UvRefusal] = []
    ) {
        // A Terminal finds the uv only if its directory is on the login shell's PATH, and
        // the window that ran the installer has not read the PATH the installer added.
        let inNewTerminal = uv.map { !(loginPath?.contains(($0 as NSString).deletingLastPathComponent) ?? false) } ?? true
        var steps: [Step] = uv == nil ? [.installUv(homebrew: hasHomebrew)] : []
        let toolMetab = binDirectory + "/metab"
        let old = tried.lazy.compactMap { outcome -> (String, String)? in
            if case .tooOld(let version) = outcome.result { return (outcome.path, version) }
            return nil
        }.first
        let broken = tried.lazy.compactMap { outcome -> String? in
            if case .rejected(let reason) = outcome.result, outcome.path == toolMetab { return reason }
            return nil
        }.first
        if !minimumIsReleased {
            steps.append(.buildFromCheckout(oldPath: old?.0, oldVersion: old?.1, inNewTerminal: inNewTerminal))
        } else if let old {
            steps.append(.upgradeMetab(path: old.0, version: old.1, inNewTerminal: inNewTerminal))
        } else if let broken {
            steps.append(.reinstallMetab(path: toolMetab, reason: broken, inNewTerminal: inNewTerminal))
        } else {
            steps.append(.installMetab(inNewTerminal: inNewTerminal))
        }
        self.steps = steps
        self.binDirectory = binDirectory
        self.home = home
        suggestsUpdateShell = !(loginPath?.contains(binDirectory) ?? false)
        let untrusted = tried.compactMap { outcome -> String? in
            guard case .untrusted(let reason) = outcome.result else { return nil }
            return "Metabrowser does not run \(outcome.path) itself: \(reason). Choose metab… runs it if you trust it."
        }
        notices = refusedUv.map { "Metabrowser does not run \($0.path) itself: \($0.reason)." } + untrusted
    }

    /// Where uv may be, in order: where its installer puts it (`XDG_BIN_HOME`, then
    /// `XDG_DATA_HOME/../bin`, then `~/.local/bin`), the Homebrew prefixes, and then the
    /// login shell's `PATH`, which reaches any other install the user's Terminal finds.
    /// The app runs only one that passes `ExecutableTrust`.
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

/// A uv the app found and would not run, and why (`ExecutableTrust`).
public nonisolated struct UvRefusal: Equatable, Sendable {
    public var path: String
    public var reason: String

    public init(path: String, reason: String) {
        self.path = path
        self.reason = reason
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

    /// What the first-run screen knows about uv.
    public struct Survey: Equatable, Sendable {
        /// The first uv found, which decides whether the steps install uv. The user's own
        /// Terminal runs it, so it counts whether or not the app may run it.
        public var found: String?
        /// The uv the app ran: the first found that the trust check passed.
        public var run: String?
        /// The uvs found before that one, which the app did not run, and why.
        public var refused: [UvRefusal]
        /// Where uv puts `metab`: its own answer, else uv's documented rule.
        public var binDirectory: String
        /// Why the uv that ran gave no answer, when it gave none.
        public var failure: String?
    }

    /// Finds uv among `candidates` and asks the first one `refusal` passes where it puts
    /// `metab`. A candidate refused is never run.
    public static func survey(
        _ candidates: [String], env: DiscoveryEnvironment, refusal: @Sendable (String) -> String?
    ) async -> Survey {
        var survey = Survey(
            found: nil, run: nil, refused: [], binDirectory: RuntimeDiscovery.uvToolBinDirectory(env), failure: nil)
        for candidate in candidates where env.isExecutable(candidate) {
            if survey.found == nil { survey.found = candidate }
            if let reason = refusal(candidate) {
                survey.refused.append(UvRefusal(path: candidate, reason: reason))
                continue
            }
            survey.run = candidate
            break
        }
        if let uv = survey.run {
            switch await ask(uv: uv, env: env) {
            case .directory(let directory): survey.binDirectory = directory
            case .failed(let reason): survey.failure = reason
            }
        }
        return survey
    }
}
