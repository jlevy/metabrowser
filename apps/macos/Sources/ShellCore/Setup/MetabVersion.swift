import Foundation

/// A `metab` version as `metab --version` prints it, in the normalized PEP 440 forms
/// this project's builds produce: a release (`0.12.0`), then optionally a pre-release
/// (`rc1`), a post-release (`.post2`), a development build (`.dev214`), and a local
/// label (`+8b0603f7`). A checkout prints a description after the version, such as
/// `(+214 commits, 8b0603f78)`, which is not part of it.
public nonisolated struct MetabVersion: Equatable, Sendable, CustomStringConvertible {
    /// The release segments: `[0, 12, 1]` for `0.12.1.dev214`.
    public let release: [Int]
    /// The version alone, without the description after it.
    public let text: String

    public init?(_ printed: String) {
        let text = String(printed.prefix { !$0.isWhitespace })
        guard let match = text.wholeMatch(of: Self.pattern) else { return nil }
        var release: [Int] = []
        for segment in match.output.1.split(separator: ".") {
            guard let number = Int(segment) else { return nil }
            release.append(number)
        }
        self.release = release
        self.text = text
    }

    public var description: String { text }

    /// Whether the release segments are `minimum`'s or later, missing segments counting
    /// as zero. Pre-release, post-release, and development parts are not compared.
    public func hasRelease(atLeast minimum: [Int]) -> Bool {
        for index in 0..<max(release.count, minimum.count) {
            let mine = index < release.count ? release[index] : 0
            let theirs = index < minimum.count ? minimum[index] : 0
            if mine != theirs { return mine > theirs }
        }
        return true
    }

    nonisolated(unsafe) private static let pattern =
        #/([0-9]+(?:\.[0-9]+)*)(?:(?:a|b|rc)[0-9]+)?(?:\.post[0-9]+)?(?:\.dev[0-9]+)?(?:\+[a-z0-9]+(?:\.[a-z0-9]+)*)?/#
}

/// The oldest `metab` this app runs, and what it tells a user whose `metab` is older.
///
/// A CLI install updates independently of the app, so this is the app's side of a
/// versioned boundary: below the minimum the app starts no server and shows
/// `upgradeCommand`. The host-protocol version replaces it once host mode exists.
///
/// The contract is at the minor release: `minimumRelease` is always `X.Y.0`, at most the
/// next minor release after the latest one, and `isReleased` stays false until it is on
/// PyPI. "Choosing a Version" in `docs/publishing.md` has the rule and its reason, and
/// `tests/test_macos_app_pins.py` checks it.
public nonisolated enum MetabRequirement {
    /// The first release with `GET /api/identity`, which names each window, with
    /// `--exit-on-eof`, which ends a server with the app, with `--present`, whose dry run
    /// resolves a GitHub link (`PresentDryRun`), with `--recent`, which File > Open
    /// Recent lists, and with `POST /api/source/link`, which opens every link into a
    /// repository in its one mirror (`SourceLink`). 0.12.0, the latest published release,
    /// lacks all five, so the next release is a minor one. Until it is on PyPI, only builds
    /// from a source checkout meet this, and `RuntimeDiscovery.validate` finds one built
    /// before any of the flags too old, whatever its number: the check runs with them all
    /// (`requiredFlags`). A route cannot be probed that way; a development build from
    /// before the link route opens a link's repository and leaves its window on the
    /// entry page, which the app logs.
    public static let minimumRelease = [0, 13, 0]

    /// The flags a `metab` must take that its number cannot show (`flagShortfall`), oldest
    /// first: `RuntimeDiscovery.validate` passes them all with `--version`. `--exit-on-eof`
    /// ends a server with the app, `--present` resolves a GitHub link, and `--recent` lists
    /// the recent targets.
    public static let requiredFlags = [CLIServeLaunch.exitOnEOF, PresentDryRun.flag, RecentTargets.listFlag]

    public static var minimum: String { minimumRelease.map(String.init).joined(separator: ".") }

    /// Whether `minimum` is on PyPI, so that uv can install a `metab` this app runs. Until
    /// it is, the first-run screen points to the source checkout the app was built from
    /// instead of `uv tool install`. Set it with the release that publishes `minimum`, and
    /// back to false whenever `minimumRelease` is raised to an unpublished release.
    public static let isReleased = false

    /// A pre-release or development build of the minimum counts as the minimum. A source
    /// checkout reports the next release with `.devN`, which PEP 440 orders before that
    /// release, so without this no development build would run. Its number says only
    /// that it was built after 0.12.0, not which changes it has, so
    /// `RuntimeDiscovery.validate` also runs it with `requiredFlags`, and one that rejects
    /// any of them is too old. Each reached the source after the one before it and the
    /// identity route, so a build that has the newest has them all.
    public static func accepts(_ version: MetabVersion) -> Bool {
        version.hasRelease(atLeast: minimumRelease)
    }

    /// What a `metab` that `RuntimeDiscovery.validate` found too old lacks when its number
    /// meets the minimum: "built before --recent". Nil when its number is below the
    /// minimum, which then says why. `validate` finds a build that meets the number too old
    /// only when it rejects one of `requiredFlags` as an unknown option
    /// (`RuntimeDiscovery.rejectsServeFlag`), and a build without any of them was built
    /// before the newest, so the screens that name one say that, rather than compare its
    /// number with a minimum it meets.
    public static func flagShortfall(_ version: String) -> String? {
        guard let parsed = MetabVersion(version), accepts(parsed), let newest = requiredFlags.last else { return nil }
        return "built before \(newest)"
    }

    /// Replaces an older CLI install with one this app runs, by the install's own tool
    /// (`MetabInstall.upgradeCommand`).
    public static func upgradeCommand(for install: MetabInstall) -> String {
        install.upgradeCommand(minimum: minimum)
    }
}

/// How a `metab` was installed, read from its executable's canonical path, so the step
/// that upgrades it uses the tool that installed it rather than adding a second copy.
///
/// `metab --doctor` reads the same of itself, from the same files the same way
/// (`metab_install` and `METAB_UPGRADE_COMMANDS` in `src/metabrowser/cli/doctor.py`), and
/// `tests/test_macos_app_pins.py` holds each case's command and each file's name here to
/// those. The app's own copies are what it shows when no `metab` runs.
public nonisolated enum MetabInstall: Equatable, Sendable {
    /// `uv tool install`: the tool environment holds `uv-receipt.toml`.
    case uvTool
    /// `pipx install`: the environment holds `pipx_metadata.json`.
    case pipx
    /// A source checkout's `.venv/bin/metab`, beside a `pyproject.toml` that names this
    /// project.
    case checkout(root: String)
    /// Anything else, an editable install into another environment among them, which uv
    /// replaces with an install the app finds.
    case other

    public static let uvReceipt = "uv-receipt.toml"
    public static let pipxMetadata = "pipx_metadata.json"
    public static let checkoutVenv = ".venv"
    /// The project a checkout's `pyproject.toml` names, on a line `name = "metabrowser"`.
    public static let checkoutProject = "metabrowser"
    /// How much of a `pyproject.toml` is read for that line; this repository's is about 9 KB.
    static let pyprojectMaxBytes = 256 * 1024

    /// Reads the files beside the canonical executable: `<prefix>/bin/metab`, where a tool
    /// environment's prefix holds its receipt and a checkout's `.venv` sits in the
    /// checkout. A uv receipt wins over a checkout, as `uv tool install --editable` makes
    /// both. `readHead` returns at most `pyprojectMaxBytes` of a regular file.
    public static func of(
        executable: String,
        canonicalPath: (String) -> String = FileChecks.canonicalPath,
        fileExists: (String) -> Bool = { FileManager.default.fileExists(atPath: $0) },
        readHead: (String) -> String? = MetabInstall.readHead
    ) -> MetabInstall {
        let bin = (canonicalPath(executable) as NSString).deletingLastPathComponent
        let prefix = (bin as NSString).deletingLastPathComponent
        guard prefix.hasPrefix("/"), prefix != "/" else { return .other }
        if fileExists(prefix + "/" + uvReceipt) { return .uvTool }
        if fileExists(prefix + "/" + pipxMetadata) { return .pipx }
        let root = (prefix as NSString).deletingLastPathComponent
        if (prefix as NSString).lastPathComponent == checkoutVenv,
            let pyproject = readHead(root + "/pyproject.toml"), declaresThisProject(pyproject)
        {
            return .checkout(root: root)
        }
        return .other
    }

    /// Whether a `pyproject.toml` has the line `name = "metabrowser"`, spaces around `=`
    /// and after it allowed, as `CHECKOUT_PROJECT` in `src/metabrowser/cli/doctor.py`
    /// matches it.
    static func declaresThisProject(_ pyproject: String) -> Bool {
        pyproject.split(whereSeparator: \.isNewline).contains { line in
            guard line.hasPrefix("name") else { return false }
            let rest = line.dropFirst(4).drop { $0 == " " || $0 == "\t" }
            guard rest.first == "=" else { return false }
            return rest.dropFirst().trimmingCharacters(in: .whitespaces) == "\"\(checkoutProject)\""
        }
    }

    /// At most `pyprojectMaxBytes` of the regular file at `path`, or nil; never a FIFO,
    /// which would block.
    public static func readHead(_ path: String) -> String? {
        let type = (try? FileManager.default.attributesOfItem(atPath: path))?[.type] as? FileAttributeType
        guard type == .typeRegular, let handle = FileHandle(forReadingAtPath: path) else { return nil }
        defer { try? handle.close() }
        guard let data = try? handle.read(upToCount: pyprojectMaxBytes) else { return nil }
        return String(decoding: data, as: UTF8.self)
    }

    /// The command that brings this install to `minimum` or later. uv's and pipx's ask
    /// for a floor, not an exact version: uv records the requirement in the tool's receipt
    /// and every later `uv tool upgrade` keeps to it, so an exact pin would hold the
    /// install there. A checkout builds its own source, run at its root (`note`).
    public func upgradeCommand(minimum: String) -> String {
        switch self {
        case .uvTool, .other: "uv tool install --upgrade 'metabrowser>=\(minimum)'"
        case .pipx: "pipx install --force 'metabrowser>=\(minimum)'"
        case .checkout: "git pull && make install"
        }
    }

    /// Where to run `upgradeCommand`, when it matters: a checkout's root.
    public var note: String? {
        guard case .checkout(let root) = self else { return nil }
        return "At the root of the checkout \(root):"
    }

    /// Whether `upgradeCommand` runs uv, so a Terminal must find it: a checkout's
    /// `make install` does too.
    public var needsUv: Bool {
        switch self {
        case .uvTool, .other, .checkout: true
        case .pipx: false
        }
    }
}
