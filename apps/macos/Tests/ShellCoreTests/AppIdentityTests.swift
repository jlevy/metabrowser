import Foundation
import Testing
@testable import ShellCore

/// Both variants are named Metabrowser; the bundle identifier and the variant key the
/// build writes keep their settings apart and let the About box say which build it is.
///
/// mb-d71s: both variants keep their logs and saved session in folders named for the
/// app, `~/Library/Logs/Metabrowser/` and `~/Library/Application Support/Metabrowser/`,
/// so a development build and a release restore the same windows. A development build
/// wrote `Metabrowser Dev/` logs and kept its session under its bundle identifier.
@Suite struct AppIdentityTests {
    private let home = URL(filePath: "/Volumes/Home", directoryHint: .isDirectory)

    private func info(variant: String?, commit: String? = "abc1234") -> [String: Any] {
        var info: [String: Any] = [
            "CFBundleName": "Metabrowser", "CFBundleIdentifier": "io.github.jlevy.metabrowser.dev",
            "CFBundleShortVersionString": "0.1.0", "CFBundleVersion": "2466",
        ]
        if variant == "release" { info["CFBundleIdentifier"] = "io.github.jlevy.metabrowser" }
        info[AppIdentity.variantKey] = variant
        info[AppIdentity.commitKey] = commit
        return info
    }

    @Test func aDevelopmentBuildSaysSoAndUsesTheAppsFolders() {
        let dev = AppIdentity(infoDictionary: info(variant: "dev"))
        #expect(dev.name == "Metabrowser")
        #expect(dev.variant == .dev)
        #expect(dev.buildLine == "Development build · 0.1.0 (2466) · abc1234")
        #expect(dev.logsDirectory(home: home).path(percentEncoded: false) == "/Volumes/Home/Library/Logs/Metabrowser/")
        #expect(dev.supportDirectory(home: home).path(percentEncoded: false)
            == "/Volumes/Home/Library/Application Support/Metabrowser/")
    }

    @Test func aReleaseSaysSoAndUsesTheSameFolders() {
        let release = AppIdentity(infoDictionary: info(variant: "release"))
        let dev = AppIdentity(infoDictionary: info(variant: "dev"))
        #expect(release.variant == .release)
        #expect(release.buildLine == "Release · 0.1.0 (2466) · abc1234")
        #expect(release.logsDirectory(home: home).path(percentEncoded: false)
            == "/Volumes/Home/Library/Logs/Metabrowser/")
        #expect(release.supportDirectory(home: home).path(percentEncoded: false)
            == "/Volumes/Home/Library/Application Support/Metabrowser/")
        #expect(release.logsDirectory(home: home) == dev.logsDirectory(home: home))
        #expect(release.supportDirectory(home: home) == dev.supportDirectory(home: home))
        // Settings and recents stay apart, by bundle identifier.
        #expect(release.bundleIdentifier != dev.bundleIdentifier)
    }

    /// The folders follow the app's name, not its identifier: the setup check's copy
    /// (scripts/check-setup-flows.sh), renamed, never reads or replaces the session the
    /// development app and a release share.
    @Test func aCopyWithAnotherNameKeepsFoldersOfItsOwn() {
        var renamed = info(variant: "dev")
        renamed["CFBundleName"] = "Metabrowser Setup Check"
        renamed["CFBundleIdentifier"] = "io.github.jlevy.metabrowser.setupcheck"
        let copy = AppIdentity(infoDictionary: renamed)
        #expect(copy.logsDirectory(home: home).path(percentEncoded: false)
            == "/Volumes/Home/Library/Logs/Metabrowser Setup Check/")
        #expect(copy.supportDirectory(home: home).path(percentEncoded: false)
            == "/Volumes/Home/Library/Application Support/Metabrowser Setup Check/")
        var sameName = renamed
        sameName["CFBundleName"] = "Metabrowser"
        #expect(AppIdentity(infoDictionary: sameName).supportDirectory(home: home)
            == AppIdentity(infoDictionary: info(variant: "dev")).supportDirectory(home: home),
            "an identifier alone does not keep the session apart")
    }

    @Test func aBuildWithoutItsCommitLeavesItOut() {
        #expect(AppIdentity(infoDictionary: info(variant: "dev", commit: nil)).buildLine
            == "Development build · 0.1.0 (2466)")
        #expect(AppIdentity(infoDictionary: info(variant: "dev", commit: "")).buildLine
            == "Development build · 0.1.0 (2466)")
    }

    /// An unbundled run, such as the debug executable, or a bundle that lacks the key,
    /// is a development build: only the release path writes the release variant.
    @Test func anythingButTheReleaseKeyIsADevelopmentBuild() {
        #expect(AppIdentity(infoDictionary: info(variant: nil)).variant == .dev)
        #expect(AppIdentity(infoDictionary: info(variant: "beta")).variant == .dev)
        let bare = AppIdentity(infoDictionary: [:])
        #expect(bare.variant == .dev)
        #expect(bare.name == "Metabrowser")
        #expect(bare.bundleIdentifier == "io.github.jlevy.metabrowser.dev")
        #expect(bare.buildLine == "Development build · unbundled")
        #expect(bare.supportDirectory(home: home).path(percentEncoded: false)
            == "/Volumes/Home/Library/Application Support/Metabrowser/")
    }
}
