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
    /// source checkout meet this, and one built before the flag existed fails to start
    /// with an unknown-option error, which the window shows.
    public static let minimumRelease = [0, 12, 1]

    public static var minimum: String { minimumRelease.map(String.init).joined(separator: ".") }

    /// A pre-release or development build of the minimum counts as the minimum. A source
    /// checkout reports the next release with `.devN`, which PEP 440 orders before that
    /// release, so without this no development build would run. Its number says only
    /// that it was built after 0.12.0, not which changes it has: one built before the
    /// route reached `main` runs too, and its windows keep the names derived from their
    /// paths.
    public static func accepts(_ version: MetabVersion) -> Bool {
        version.hasRelease(atLeast: minimumRelease)
    }

    /// Replaces an older CLI install with one this app runs. It asks for a floor, not an
    /// exact version: uv records the requirement in the tool's receipt and every later
    /// `uv tool upgrade` keeps to it, so an exact pin would hold the install there.
    public static var upgradeCommand: String { "uv tool install --upgrade 'metabrowser>=\(minimum)'" }
}
