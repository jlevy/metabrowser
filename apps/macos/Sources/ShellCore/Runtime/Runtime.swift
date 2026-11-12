import Foundation

/// Where a `metab` came from, in discovery order.
public nonisolated enum RuntimeSource: String, Codable, Sendable {
    case chosen
    case environment
    case localBin
    case uvToolBin
    case homebrew
    case loginShell

    public var label: String {
        switch self {
        case .chosen: "chosen in Settings"
        case .environment: "METABROWSER_METAB"
        case .localBin: "~/.local/bin"
        case .uvToolBin: "uv's tool directory"
        case .homebrew: "Homebrew"
        case .loginShell: "your login shell's PATH"
        }
    }
}

/// The `metab` the app runs: a CLI install, validated with `metab --version`.
public nonisolated struct Runtime: Codable, Equatable, Sendable {
    public var executable: String
    public var version: String
    public var source: RuntimeSource
    /// The executable as it was just before `--version` ran, so `version` describes this
    /// file and no later one. Nil when it could not be taken, which no check trusts.
    public var fingerprint: FileFingerprint?

    public init(executable: String, version: String, source: RuntimeSource, fingerprint: FileFingerprint? = nil) {
        self.executable = executable
        self.version = version
        self.source = source
        self.fingerprint = fingerprint
    }

    /// Whether a server can start from this runtime without running `--version` again:
    /// its executable is the file that was validated, and its version is one this app
    /// accepts, which a runtime saved by a build with a lower minimum may not be.
    public func isCurrent(fingerprint now: FileFingerprint?) -> Bool {
        guard let fingerprint, now == fingerprint, let parsed = MetabVersion(version) else { return false }
        return MetabRequirement.accepts(parsed)
    }
}

/// External tools the server runs, as absolute paths resolved once at setup.
public nonisolated struct ToolPaths: Codable, Equatable, Sendable {
    public var git: String?
    public var gh: String?

    public init(git: String? = nil, gh: String? = nil) {
        self.git = git
        self.gh = gh
    }

    /// The directories that go first on the child's `PATH`, in order.
    public var directories: [String] {
        var result: [String] = []
        for tool in [git, gh].compactMap(\.self) {
            let directory = (tool as NSString).deletingLastPathComponent
            if !directory.isEmpty, !result.contains(directory) { result.append(directory) }
        }
        return result
    }
}

/// Everything setup decided, saved so later launches search nothing.
public nonisolated struct RuntimeSetup: Codable, Equatable, Sendable {
    public var runtime: Runtime
    public var tools: ToolPaths

    public init(runtime: Runtime, tools: ToolPaths) {
        self.runtime = runtime
        self.tools = tools
    }
}

/// The saved setup, in the app's user defaults.
public final class RuntimeSettings {
    static let key = "runtimeSetup"
    private let defaults: UserDefaults

    public init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    /// The saved setup. One this build cannot decode counts as none, so the next launch
    /// runs setup again and saves what it finds: the saved setup is only what setup found.
    public func load() -> RuntimeSetup? {
        guard let data = defaults.data(forKey: Self.key) else { return nil }
        return try? JSONDecoder().decode(RuntimeSetup.self, from: data)
    }

    public func save(_ setup: RuntimeSetup) {
        // Strings and string-backed enums, which JSONEncoder always encodes.
        let data = try! JSONEncoder().encode(setup)
        defaults.set(data, forKey: Self.key)
    }

    public func clear() {
        defaults.removeObject(forKey: Self.key)
    }

    /// The saved setup if its `metab` is still an executable file at an absolute path and,
    /// unless the user chose it, one no other account can change (`ExecutableTrust`), as
    /// discovery requires. A launch checks only that, so it costs no subprocess; Settings
    /// re-runs `--version`. Without a usable one, the launch searches, and the search says
    /// why it passes over the saved one.
    public func usable(
        isExecutable: (String) -> Bool = FileChecks.isExecutableFile,
        refusal: (String) -> String? = { ExecutableTrust.refusal($0) }
    ) -> RuntimeSetup? {
        guard let setup = load(), setup.runtime.executable.hasPrefix("/"), isExecutable(setup.runtime.executable),
              setup.runtime.source == .chosen || refusal(setup.runtime.executable) == nil
        else { return nil }
        return setup
    }
}

public nonisolated enum FileChecks {
    /// A regular file (after symlinks) that this user may execute. Unlike
    /// `FileManager.isExecutableFile`, a directory does not count.
    public static func isExecutableFile(_ path: String) -> Bool {
        var info = stat()
        guard stat(path, &info) == 0, info.st_mode & S_IFMT == S_IFREG else { return false }
        return access(path, X_OK) == 0
    }

    public static func isDirectory(_ path: String) -> Bool {
        var info = stat()
        return stat(path, &info) == 0 && info.st_mode & S_IFMT == S_IFDIR
    }

    /// `realpath(3)`: symlinks resolved, `/tmp` becomes `/private/tmp`. Unlike
    /// `URL.resolvingSymlinksInPath()`, it does not strip `/private`. A path that does
    /// not exist is returned unchanged.
    public static func canonicalPath(_ path: String) -> String {
        guard let resolved = realpath(path, nil) else { return path }
        defer { free(resolved) }
        return String(cString: resolved)
    }
}
