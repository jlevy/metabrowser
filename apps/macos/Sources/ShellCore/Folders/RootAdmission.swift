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
/// A volume mounted under an ordinary folder is not entered: the mount table, read
/// without touching any volume, marks every mount point but the system's and the Data
/// volume's as a place the walk stops before.
///
/// The server is started with a path, not a descriptor, so this cannot bind what the
/// server later resolves. Each background root is checked again when `RestoreQueue`
/// reaches it and once more just before its server spawns (`ServerSupervisor.mayLaunch`),
/// and a process that changes the path in the moment between that check and the server
/// resolving it is not something this can stop. The deferral is the app's
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
    /// a trailing slash, a line break, or a NUL, which would end the path `openat` sees
    /// before the end of the one checked.
    case invalid

    /// What looking a component up again found, after `openat` refused it.
    public enum SecondLookup: Equatable, Sendable {
        /// The entry's type, `st_mode & S_IFMT`.
        case success(mode_t)
        case failure(Int32)
    }

    /// - Parameters:
    ///   - homeDevice: the home folder's volume; nil reads it from `home`.
    ///   - mounts: the mount points; nil reads the mount table.
    ///   - beforeLooking: called with each path just before it is looked up, which is how
    ///     the tests watch what is looked at and change the filesystem mid-walk.
    public static func admit(
        _ saved: String, home: String, homeDevice: dev_t? = nil, mounts: [String]? = nil,
        beforeLooking: (String) -> Void = { _ in }
    ) -> RootAdmission {
        guard let components = canonicalComponents(saved) else { return .invalid }
        let isInside = { ProtectedLocations.isInside($0, home: home) }
        // A home folder in a protected place cannot be looked at to classify anything.
        guard !isInside(home), let table = mounts ?? mountPoints() else { return .deferred(saved) }
        let barriers = mountBarriers(table)
        // Nor one on a mount the walk would not enter: its stat could wait on a share.
        if barriers.contains(where: { ProtectedLocations.isWithin(home, $0) }) { return .deferred(saved) }
        var fd = Darwin.open("/", O_SEARCH | O_CLOEXEC)
        guard fd >= 0 else { return .deferred(saved) }
        defer { close(fd) }
        var path = ""
        for component in components {
            path += "/" + component
            if isInside(path) || barriers.contains(path.lowercased()) { return .deferred(saved) }
            beforeLooking(path)
            let next = openat(fd, component, O_SEARCH | O_NOFOLLOW | O_CLOEXEC)
            guard next >= 0 else {
                let error = errno
                guard error == ENOTDIR || error == ELOOP else { return error == ENOENT ? .gone : .deferred(saved) }
                beforeLooking(path)
                var info = stat()
                let lookup = fstatat(fd, component, &info, AT_SYMLINK_NOFOLLOW) == 0
                    ? SecondLookup.success(info.st_mode & S_IFMT) : .failure(errno)
                return refusedComponent(lookup, saved)
            }
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
            beforeLooking(home)
            guard stat(home, &homeInfo) == 0 else { return .deferred(saved) }
            device = homeInfo.st_dev
        }
        guard info.st_dev == device, let canonical = kernelPath(fd) else { return .deferred(saved) }
        return ProtectedLocations.contains(canonical, home: home) ? .deferred(saved) : .open(canonical)
    }

    /// After `openat` refused a component as not a folder or a link: only proof that it is
    /// missing, or that it is neither a folder nor a link, drops the tab. A link, a folder
    /// (the component changed between the two lookups), or a lookup that failed otherwise
    /// defers it.
    static func refusedComponent(_ lookup: SecondLookup, _ saved: String) -> RootAdmission {
        switch lookup {
        case .failure(ENOENT): .gone
        case .failure: .deferred(saved)
        case .success(S_IFDIR), .success(S_IFLNK): .deferred(saved)
        case .success: .gone
        }
    }

    /// `getfsstat(2)`: with no buffer, the number of mounts; with one, fills it and
    /// returns how many it filled, at most its capacity.
    public typealias MountEnumerator = (UnsafeMutablePointer<Darwin.statfs>?, Int32, Int32) -> Int32

    /// Spare entries allocated past the last count, so a mount added between counting
    /// and filling still fits.
    static let mountTableSpare = 16
    /// Fills tried before a table that keeps filling its buffer is given up on.
    static let mountTableAttempts = 4

    /// Every mount point, from the kernel's table without asking any volume (`MNT_NOWAIT`),
    /// or nil if the whole table cannot be read. A fill that uses the whole buffer may
    /// have left mounts out, so it is read again into a larger one, a bounded number of
    /// times.
    public static func mountPoints(fsstat: MountEnumerator = { getfsstat($0, $1, $2) }) -> [String]? {
        var capacity = Int(fsstat(nil, 0, MNT_NOWAIT))
        guard capacity > 0 else { return nil }
        for _ in 0..<mountTableAttempts {
            capacity += mountTableSpare
            var entries = Array(repeating: Darwin.statfs(), count: capacity)
            let filled = entries.withUnsafeMutableBufferPointer { buffer in
                fsstat(buffer.baseAddress, Int32(MemoryLayout<Darwin.statfs>.stride * buffer.count), MNT_NOWAIT)
            }
            guard filled > 0 else { return nil }
            guard Int(filled) < capacity else {
                capacity *= 2
                continue
            }
            return names(entries.prefix(Int(filled)))
        }
        return nil
    }

    private static func names(_ entries: ArraySlice<Darwin.statfs>) -> [String] {
        entries.map { entry in
            withUnsafeBytes(of: entry.f_mntonname) { bytes in
                String(decoding: bytes.prefix { $0 != 0 }, as: UTF8.self)
            }
        }
    }

    /// The mount points the walk stops before, lowercased, in both spellings of a
    /// firmlinked path: all but the system volume's and the Data volume's.
    static func mountBarriers(_ mounts: [String]) -> Set<String> {
        let data = ProtectedLocations.dataVolume
        var barriers: Set<String> = []
        for mount in mounts where mount != "/" && mount != data {
            barriers.insert(mount.lowercased())
            if mount.hasPrefix(data + "/") {
                barriers.insert(String(mount.dropFirst(data.count)).lowercased())
            } else {
                barriers.insert((data + mount).lowercased())
            }
        }
        return barriers
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
        guard path.hasPrefix("/"), !path.contains(where: \.isNewline), !path.unicodeScalars.contains("\0")
        else { return nil }
        if path == "/" { return [] }
        let components = path.dropFirst().split(separator: "/", omittingEmptySubsequences: false).map(String.init)
        guard components.allSatisfy({ !$0.isEmpty && $0 != "." && $0 != ".." }) else { return nil }
        return components
    }
}
