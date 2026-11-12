import Darwin
import Foundation

/// What is at a path, without following it if it is a symbolic link.
public nonisolated enum PathEntry: Equatable, Sendable {
    case directory
    /// A symbolic link, and the target it names, as written.
    case symlink(String)
    case missing
    /// Anything else: a file, a device, a pipe, a socket.
    case other

    /// `lstat(2)`, and `readlink(2)` for a link.
    public static func inspect(_ path: String) -> PathEntry {
        var info = stat()
        guard lstat(path, &info) == 0 else { return .missing }
        switch info.st_mode & S_IFMT {
        case S_IFDIR:
            return .directory
        case S_IFLNK:
            var buffer = [CChar](repeating: 0, count: Int(PATH_MAX) + 1)
            let count = readlink(path, &buffer, Int(PATH_MAX))
            guard count >= 0 else { return .missing }
            return .symlink(String(decoding: buffer[..<count].map { UInt8(bitPattern: $0) }, as: UTF8.self))
        default:
            return .other
        }
    }
}

/// Whether a saved session's root may start, and under which identity.
///
/// A root a launch restores was canonical when it was saved, but the file may have been
/// edited since, and a folder on its path may have become a symbolic link, into
/// Documents for instance. So a restored root is resolved again before its protection
/// is decided, one component at a time with `lstat` and `readlink`, and the walk stops
/// before it would look at anything in a protected location: looking there could raise
/// the privacy prompt that restore defers. Ordinary opens resolve with `realpath(3)`,
/// which reaches the same identity for a path outside protected locations.
public nonisolated enum RootAdmission: Equatable, Sendable {
    /// Resolved, and outside every protected location: the root may start in the
    /// background, under this canonical path.
    case open(String)
    /// The root is, is inside, or holds a protected location, so its server waits until
    /// one of its tabs is selected. The path is resolved up to the protected location.
    case deferred(String)
    /// Gone, or not a folder.
    case gone
    /// Not an absolute path spelled as a canonical one (no `.`, `..`, or empty
    /// components, no trailing slash, no line break), or a loop of links.
    case invalid

    /// More links than `realpath(3)` follows (`MAXSYMLINKS`) is a loop.
    public static let linkLimit = 32

    public static func admit(
        _ saved: String, home: String, inspect: (String) -> PathEntry = PathEntry.inspect
    ) -> RootAdmission {
        guard let components = canonicalComponents(saved) else { return .invalid }
        var resolved = "/"
        var remaining = components[...]
        var links = 0
        while let next = remaining.popFirst() {
            switch next {
            case "", ".": continue
            case "..":
                resolved = (resolved as NSString).deletingLastPathComponent
                continue
            default: break
            }
            let candidate = resolved == "/" ? "/" + next : resolved + "/" + next
            if ProtectedLocations.isInside(candidate, home: home) {
                return .deferred(lexical(candidate, remaining))
            }
            switch inspect(candidate) {
            case .directory:
                resolved = candidate
            case .symlink(let target):
                links += 1
                guard links <= linkLimit, !target.isEmpty else { return .invalid }
                if target.hasPrefix("/") { resolved = "/" }
                remaining = (target.split(separator: "/", omittingEmptySubsequences: false).map(String.init) + remaining)[...]
            case .missing, .other:
                return .gone
            }
        }
        return ProtectedLocations.contains(resolved, home: home) ? .deferred(resolved) : .open(resolved)
    }

    /// `base` with `rest` appended, `.` and empty components dropped and `..` taken
    /// lexically: the identity of a deferred root, whose rest is not looked at.
    static func lexical(_ base: String, _ rest: ArraySlice<String>) -> String {
        var path = base
        for component in rest where !component.isEmpty && component != "." {
            if component == ".." {
                path = (path as NSString).deletingLastPathComponent
            } else {
                path = path == "/" ? "/" + component : path + "/" + component
            }
        }
        return path
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
