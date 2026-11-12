import Foundation
import Testing
@testable import ShellCore

/// Both variants are named Metabrowser; the bundle identifier and the variant key the
/// build writes keep their files apart and let the About box say which build it is.
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

    @Test func aDevelopmentBuildSaysSoAndKeepsItsFilesApart() {
        let dev = AppIdentity(infoDictionary: info(variant: "dev"))
        #expect(dev.name == "Metabrowser")
        #expect(dev.variant == .dev)
        #expect(dev.buildLine == "Development build · 0.1.0 (2466) · abc1234")
        #expect(dev.logsDirectory(home: home).path(percentEncoded: false) == "/Volumes/Home/Library/Logs/Metabrowser Dev/")
        #expect(dev.supportDirectory(home: home).path(percentEncoded: false)
            == "/Volumes/Home/Library/Application Support/io.github.jlevy.metabrowser.dev/")
    }

    @Test func aReleaseSaysSoAndKeepsTheReleaseFolders() {
        let release = AppIdentity(infoDictionary: info(variant: "release"))
        #expect(release.variant == .release)
        #expect(release.buildLine == "Release · 0.1.0 (2466) · abc1234")
        #expect(release.logsDirectory(home: home).path(percentEncoded: false) == "/Volumes/Home/Library/Logs/Metabrowser/")
        #expect(release.supportDirectory(home: home).path(percentEncoded: false)
            == "/Volumes/Home/Library/Application Support/io.github.jlevy.metabrowser/")
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
    }
}
