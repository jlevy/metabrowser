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
public nonisolated enum MetabRequirement {
    /// The first release with `GET /api/identity`, which names each window, and with
    /// `--exit-on-eof`, which ends a server with the app. 0.12.0, the latest published
    /// release, lacks both; until a release that has them is on PyPI, only builds from a
    /// source checkout meet this, and `RuntimeDiscovery.validate` finds one built before
    /// the flag too old, whatever its number.
    public static let minimumRelease = [0, 12, 1]

    public static var minimum: String { minimumRelease.map(String.init).joined(separator: ".") }

    /// Whether `minimum` is on PyPI, so that uv can install a `metab` this app runs. Until
    /// it is, the first-run screen points to the source checkout the app was built from
    /// instead of `uv tool install`. Set it with the release that publishes `minimum`.
    public static let isReleased = false

    /// A pre-release or development build of the minimum counts as the minimum. A source
    /// checkout reports the next release with `.devN`, which PEP 440 orders before that
    /// release, so without this no development build would run. Its number says only
    /// that it was built after 0.12.0, not which changes it has, so
    /// `RuntimeDiscovery.validate` also runs it with `--exit-on-eof`, and one that rejects
    /// the flag is too old. The flag reached the source after the identity route, so a
    /// build that has the flag has the route too.
    public static func accepts(_ version: MetabVersion) -> Bool {
        version.hasRelease(atLeast: minimumRelease)
    }

    /// What a `metab` that `RuntimeDiscovery.validate` found too old lacks when its number
    /// meets the minimum: "built before --exit-on-eof". Nil when its number is below the
    /// minimum, which then says why. `validate` finds a build that meets the number too old
    /// only when it rejects `CLIServeLaunch.exitOnEOF`, so the screens that name one say
    /// that, rather than compare its number with a minimum it meets.
    public static func flagShortfall(_ version: String) -> String? {
        guard let parsed = MetabVersion(version), accepts(parsed) else { return nil }
        return "built before \(CLIServeLaunch.exitOnEOF)"
    }

    /// Replaces an older CLI install with one this app runs. It asks for a floor, not an
    /// exact version: uv records the requirement in the tool's receipt and every later
    /// `uv tool upgrade` keeps to it, so an exact pin would hold the install there.
    public static var upgradeCommand: String { "uv tool install --upgrade 'metabrowser>=\(minimum)'" }
}
