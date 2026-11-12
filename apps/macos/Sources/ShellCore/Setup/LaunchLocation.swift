import Foundation

/// Where the running copy of the app is, as far as updating it is concerned.
///
/// A copy opened from its disk image runs from a read-only volume, and a quarantined
/// copy opened where it was downloaded runs from a randomized read-only mirror (App
/// Translocation). Neither can be replaced in place, and the first stops working when
/// the image is ejected. macOS offers no API to detect either, so this reads the
/// bundle's path and volume, as Sparkle does.
public nonisolated enum LaunchLocation: Equatable, Sendable {
    case installed
    case diskImage(volume: String)
    case translocated

    public struct Volume: Equatable, Sendable {
        public var name: String
        public var isReadOnly: Bool

        public init(name: String, isReadOnly: Bool) {
            self.name = name
            self.isReadOnly = isReadOnly
        }

        /// The volume `url` is on. Whether it is read-only comes from `statfs`, the mount's
        /// own flag: `URLResourceKey.volumeIsReadOnlyKey` reports the sealed system volume
        /// as writable, by its volume group.
        public init(of url: URL) throws {
            var info = statfs()
            guard statfs(url.path(percentEncoded: false), &info) == 0 else {
                throw POSIXError(POSIXErrorCode(rawValue: errno) ?? .EIO)
            }
            let mountPoint = withUnsafeBytes(of: info.f_mntonname) { String(decoding: $0.prefix { $0 != 0 }, as: UTF8.self) }
            let name = try? url.resourceValues(forKeys: [.volumeLocalizedNameKey]).volumeLocalizedName
            self.init(
                name: name ?? (mountPoint as NSString).lastPathComponent,
                isReadOnly: UInt32(info.f_flags) & UInt32(MNT_RDONLY) != 0)
        }
    }

    /// `volume` is nil when it could not be read, which leaves the path alone to judge.
    public init(bundlePath: String, volume: Volume?) {
        if bundlePath.contains("/AppTranslocation/") {
            self = .translocated
        } else if let volume, volume.isReadOnly {
            self = .diskImage(volume: volume.name)
        } else {
            self = .installed
        }
    }

    public struct Notice: Equatable, Sendable {
        public var title: String
        public var message: String
        /// Whether revealing the running copy in Finder helps: it does on a disk image,
        /// where it can be dragged from, and not for a translocated copy, whose path
        /// hides where the app really is.
        public var showsTheApp: Bool
    }

    /// What the app says at launch, or nil when it is where it belongs. Moving the app is
    /// left to the user, in Finder.
    public var notice: Notice? {
        let title = "Move Metabrowser to Applications"
        switch self {
        case .installed:
            return nil
        case .diskImage(let volume):
            return Notice(
                title: title,
                message: "Metabrowser is running from “\(volume)”, which is read-only, as a disk image is."
                    + " Drag Metabrowser to the Applications folder, then quit this copy and open Metabrowser from Applications."
                    + " A copy here cannot be updated, and stops working once the disk image is ejected.",
                showsTheApp: true)
        case .translocated:
            return Notice(
                title: title,
                message: "macOS is running Metabrowser from a temporary, read-only copy, because it was opened where it was downloaded."
                    + " Quit Metabrowser, drag it from there to the Applications folder in Finder, and open it from Applications."
                    + " A copy run this way cannot be updated.",
                showsTheApp: false)
        }
    }
}
