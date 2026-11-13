import Foundation
import Testing
@testable import ShellCore

/// A copy run from its disk image or translocated by Gatekeeper (mb-3n79). There is no
/// API for either, so the app reads the bundle's path and volume, as Sparkle does.
@Suite struct LaunchLocationTests {
    private let writable = LaunchLocation.Volume(name: "Macintosh HD", isReadOnly: false)

    @Test func anAppInAnApplicationsFolderGetsNoNotice() {
        for path in ["/Applications/Metabrowser.app", "/Volumes/Home/Applications/Metabrowser.app"] {
            let location = LaunchLocation(bundlePath: path, volume: writable)
            #expect(location == .installed)
            #expect(location.notice == nil)
        }
    }

    @Test func aReadOnlyVolumeIsADiskImage() throws {
        let location = LaunchLocation(
            bundlePath: "/Volumes/Metabrowser/Metabrowser.app",
            volume: LaunchLocation.Volume(name: "Metabrowser", isReadOnly: true))
        #expect(location == .diskImage(volume: "Metabrowser"))
        let notice = try #require(location.notice)
        #expect(notice.title == "Move Metabrowser to Applications")
        #expect(notice.message.contains("“Metabrowser”"))
        #expect(notice.showsTheApp)
    }

    /// The translocated copy is on a read-only mount too; translocation is what it says.
    @Test func anAppTranslocationPathIsTranslocated() throws {
        let location = LaunchLocation(
            bundlePath: "/private/var/folders/x1/abc/T/AppTranslocation/0F1E2D3C-AAAA-BBBB-CCCC-123456789ABC/d/Metabrowser.app",
            volume: LaunchLocation.Volume(name: "Metabrowser", isReadOnly: true))
        #expect(location == .translocated)
        let notice = try #require(location.notice)
        #expect(notice.message.contains("temporary"))
        // The translocated path hides where the app really is, so there is nothing to show.
        #expect(!notice.showsTheApp)
    }

    @Test func anUnknownVolumeIsJudgedByThePathAlone() {
        #expect(LaunchLocation(bundlePath: "/Volumes/Metabrowser/Metabrowser.app", volume: nil) == .installed)
    }

    @Test func theVolumeOfARealPathIsRead() throws {
        let volume = try LaunchLocation.Volume(of: URL(filePath: "/System/Library/CoreServices/Finder.app"))
        #expect(volume.isReadOnly)  // the sealed system volume
        let temporary = try LaunchLocation.Volume(of: FileManager.default.temporaryDirectory)
        #expect(!temporary.isReadOnly)
        #expect(throws: (any Error).self) { try LaunchLocation.Volume(of: URL(filePath: "/nonexistent-\(UUID())")) }
    }
}
