import AppKit
import ShellCore

/// The launch notice for a copy run from its disk image or translocated: what it means
/// and how to move the app. The move is the user's, in Finder; the app moves nothing.
enum LaunchLocationNotice {
    static let suppressedKey = "launchLocationNoticeSuppressed"

    static func showIfNeeded(defaults: UserDefaults = .standard) {
        let bundle = Bundle.main.bundleURL
        let volume: LaunchLocation.Volume?
        do {
            volume = try LaunchLocation.Volume(of: bundle)
        } catch {
            // The path alone still detects translocation; a disk image goes unflagged.
            AppLog.app.error("could not read the volume of \(bundle.path, privacy: .public): \(error, privacy: .public)")
            volume = nil
        }
        let location = LaunchLocation(bundlePath: bundle.path(percentEncoded: false), volume: volume)
        guard let notice = location.notice else { return }
        AppLog.app.info("running from \(bundle.path, privacy: .public): \(String(describing: location), privacy: .public)")
        guard !defaults.bool(forKey: suppressedKey) else { return }

        let alert = NSAlert()
        alert.messageText = notice.title
        alert.informativeText = notice.message
        alert.addButton(withTitle: notice.showsTheApp ? "Show in Finder" : "Open Applications Folder")
        alert.addButton(withTitle: "Continue")
        alert.showsSuppressionButton = true
        alert.suppressionButton?.title = "Don’t remind me"
        let response = alert.runModal()
        if alert.suppressionButton?.state == .on { defaults.set(true, forKey: suppressedKey) }
        guard response == .alertFirstButtonReturn else { return }
        NSWorkspace.shared.open(URL(filePath: "/Applications", directoryHint: .isDirectory))
        if notice.showsTheApp { NSWorkspace.shared.activateFileViewerSelecting([bundle]) }
    }
}
