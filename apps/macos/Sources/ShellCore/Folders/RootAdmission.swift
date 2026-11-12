import Darwin
import Foundation

/// Whether a saved session's root may start in the background, and under which identity.
///
/// A root a launch restores was canonical when it was saved, but the file may have been
/// edited since, and a folder on its path replaced or relinked. Only a root whose
/// identity is established without doubt warms in the background: a walk from `/`
/// opens each component relative to the one before, with `O_NOFOLLOW`, never opening
/// anything that is, in any spelling, a protected location or inside one. The opened
/// folder must be on the home folder's volume, and the kernel's name for it
/// (`F_GETPATH`, which undoes case variants and the Data volume's firmlinks) must hold
/// no protected location. Anything less certain (a link anywhere on the path, another
/// volume, a protected spelling) waits for its tab to be selected, under the spelling
/// it was saved with, untouched, so selecting it serves what the path names then.
///
/// The server is started with a path, not a descriptor, so this cannot bind what the
/// server later resolves: `RestoreQueue` checks each background root again just before
/// it starts, and a process that changes the path in the moment between that check and
/// the server resolving it is not something this can stop. The deferral is the app's
/// own policy, so a restore raises no prompt for a folder nobody is looking at; macOS
/// enforces its privacy grants regardless.
public nonisolated enum RootAdmission: Equatable, Sendable {
    /// May start in the background, under this canonical path.
    case open(String)
    /// Waits until one of its tabs is selected, under the saved spelling, unchanged.
    case deferred(String)
    /// Gone, or not a folder.
    case gone
    /// Not an absolute path spelled as a canonical one: a `.`, `..`, or empty component,
    /// a trailing slash, or a line break.
    case invalid

    /// - Parameters:
    ///   - homeDevice: the home folder's volume; nil reads it from `home`.
    ///   - beforeOpening: called with each path just before it is opened, which is how
    ///     the tests watch what is looked at and change the filesystem mid-walk.
    public static func admit(
        _ saved: String, home: String, homeDevice: dev_t? = nil, beforeOpening: (String) -> Void = { _ in }
    ) -> RootAdmission {
        guard let components = canonicalComponents(saved) else { return .invalid }
        let isInside = { ProtectedLocations.isInside($0, home: home) }
        var fd = Darwin.open("/", O_SEARCH | O_CLOEXEC)
        guard fd >= 0 else { return .deferred(saved) }
        defer { close(fd) }
        var path = ""
        for component in components {
            path += "/" + component
            if isInside(path) { return .deferred(saved) }
            beforeOpening(path)
            let next = openat(fd, component, O_SEARCH | O_NOFOLLOW | O_CLOEXEC)
            guard next >= 0 else { return failure(errno, at: fd, component, saved) }
            close(fd)
            fd = next
        }
        var info = stat()
        guard fstat(fd, &info) == 0 else { return .deferred(saved) }
        let device: dev_t
        if let homeDevice {
            device = homeDevice
        } else {
            var homeInfo = stat()
            guard stat(home, &homeInfo) == 0 else { return .deferred(saved) }
            device = homeInfo.st_dev
        }
        guard info.st_dev == device, let canonical = kernelPath(fd) else { return .deferred(saved) }
        return ProtectedLocations.contains(canonical, home: home) ? .deferred(saved) : .open(canonical)
    }

    /// Why `component` did not open: missing or not a folder drops the tab, and a link,
    /// or anything uncertain, defers it.
    private static func failure(_ error: Int32, at parent: Int32, _ component: String, _ saved: String) -> RootAdmission {
        switch error {
        case ENOENT:
            return .gone
        case ENOTDIR, ELOOP:
            var info = stat()
            guard fstatat(parent, component, &info, AT_SYMLINK_NOFOLLOW) == 0 else { return .gone }
            return info.st_mode & S_IFMT == S_IFLNK ? .deferred(saved) : .gone
        default:
            return .deferred(saved)
        }
    }

    /// The path the kernel gives an open folder, with the volume's own case and without
    /// the Data volume's firmlinks.
    private static func kernelPath(_ fd: Int32) -> String? {
        var buffer = [CChar](repeating: 0, count: Int(MAXPATHLEN))
        guard fcntl(fd, F_GETPATH, &buffer) == 0 else { return nil }
        return String(decoding: buffer.prefix { $0 != 0 }.map { UInt8(bitPattern: $0) }, as: UTF8.self)
    }

    /// The components of `path` if it is spelled as a canonical absolute path.
    static func canonicalComponents(_ path: String) -> [String]? {
        guard path.hasPrefix("/"), !path.contains(where: \.isNewline) else { return nil }
        if path == "/" { return [] }
        let components = path.dropFirst().split(separator: "/", omittingEmptySubsequences: false).map(String.init)
        guard components.allSatisfy({ !$0.isEmpty && $0 != "." && $0 != ".." }) else { return nil }
        return components
    }
}
