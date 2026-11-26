import Foundation

/// Reports why automatic discovery found no usable metab and where the app watches for it.
public nonisolated struct SetupGuide: Equatable, Sendable {
    public var binDirectory: String
    public var home: String
    public var notices: [String]

    public init(
        tried: [CandidateOutcome], binDirectory: String, home: String,
        minimumIsReleased: Bool = MetabRequirement.isReleased, refusedUv: [UvRefusal] = []
    ) {
        self.binDirectory = binDirectory
        self.home = home
        notices = tried.compactMap { outcome in
            let path = FolderIdentity.abbreviatingHome(outcome.path, home: home)
            switch outcome.result {
            case .tooOld(let version):
                let found = MetabVersion(version)?.text ?? version
                let reason = MetabRequirement.flagShortfall(version) ?? "the app needs \(MetabRequirement.minimum) or later"
                return "\(path) is metab \(found). It is incompatible: \(reason)."
            case .rejected(let reason):
                return "\(path) could not be used: \(reason)."
            case .untrusted(let reason):
                return "Automatic discovery skipped \(path): \(reason). Choose metab… if you trust this file."
            case .valid, .missing:
                return nil
            }
        }
        if !minimumIsReleased {
            notices.append("This preview needs metab \(MetabRequirement.minimum) or later. That version is pending on PyPI.")
        }
        notices += refusedUv.map { "Automatic discovery skipped \($0.path): \($0.reason)." }
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

    /// Where to watch for metab, and any problems locating its directory with uv.
    public struct Survey: Equatable, Sendable {
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
            run: nil, refused: [], binDirectory: RuntimeDiscovery.uvToolBinDirectory(env), failure: nil)
        for candidate in candidates where env.isExecutable(candidate) {
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
