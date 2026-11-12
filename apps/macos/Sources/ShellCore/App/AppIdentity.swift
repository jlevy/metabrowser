import Foundation

/// Which build of the app is running, read from its bundle's property list.
///
/// Both variants are named Metabrowser. Their bundle identifiers differ, which keeps
/// their user defaults, recent folders, privacy grants, and LaunchServices records apart.
/// Their logs and saved session go to folders named for the app, which both share, and
/// the variant the build stamps says in the About box which build this is (see
/// README.md, Variants).
public nonisolated struct AppIdentity: Equatable, Sendable {
    public enum Variant: String, Equatable, Sendable {
        case dev
        case release
    }

    /// The property-list keys `scripts/build-app.sh` writes.
    public static let variantKey = "MetabrowserBuildVariant"
    public static let commitKey = "MetabrowserSourceCommit"

    public var name: String
    public var bundleIdentifier: String
    public var variant: Variant
    /// `CFBundleShortVersionString`, or nil outside a bundle.
    public var version: String?
    /// `CFBundleVersion`: the commit count of the build.
    public var build: String?
    /// The short commit the build came from, with `-dirty` if `apps/macos` had changes.
    public var commit: String?

    /// Anything but the release variant counts as a development build: an unbundled run
    /// (the debug executable) has no property list, and only the release path writes
    /// the release variant.
    public init(infoDictionary info: [String: Any]) {
        func string(_ key: String) -> String? {
            (info[key] as? String).flatMap { $0.isEmpty ? nil : $0 }
        }
        variant = string(Self.variantKey).flatMap(Variant.init(rawValue:)) ?? .dev
        name = string("CFBundleName") ?? "Metabrowser"
        bundleIdentifier = string("CFBundleIdentifier") ?? "io.github.jlevy.metabrowser.dev"
        version = string("CFBundleShortVersionString")
        build = string("CFBundleVersion")
        commit = string(Self.commitKey)
    }

    /// This process's bundle.
    public static var current: AppIdentity { AppIdentity(infoDictionary: Bundle.main.infoDictionary ?? [:]) }

    /// "Development build · 0.1.0 (2466) · abc1234", or "Release · …": the About box's line.
    public var buildLine: String {
        let kind = variant == .release ? "Release" : "Development build"
        guard let version else { return "\(kind) · unbundled" }
        let numbered = build.map { "\(version) (\($0))" } ?? version
        return ([kind, numbered] + [commit].compactMap(\.self)).joined(separator: " · ")
    }

    /// `~/Library/Logs/Metabrowser/`, named for the app, for either variant; Console.app
    /// lists it under Log Reports. Copies running at once, a development build and a
    /// release among them, keep their servers' logs apart in it (`ServerLogLease`).
    public func logsDirectory(home: URL = URL(filePath: NSHomeDirectory())) -> URL {
        home.appending(path: "Library/Logs/\(name)", directoryHint: .isDirectory)
    }

    /// `~/Library/Application Support/Metabrowser/`, named for the app rather than the
    /// bundle identifier, for either variant, so a development build and a release
    /// restore the same windows (`SessionStore`). Settings stay apart, in the user
    /// defaults the bundle identifier names, and so do the recent folders macOS keeps for
    /// it. A copy with another name, such as the setup check's, keeps its own.
    public func supportDirectory(home: URL = URL(filePath: NSHomeDirectory())) -> URL {
        home.appending(path: "Library/Application Support/\(name)", directoryHint: .isDirectory)
    }
}
