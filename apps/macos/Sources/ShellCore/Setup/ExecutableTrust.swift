import Darwin

/// Whether the app may run an executable it found by itself, rather than one the user
/// chose: only one no other account can change.
///
/// The check walks the path one component at a time from `/`, following each symbolic
/// link, and refuses it if anything on the way belongs to an account other than this
/// user or root, or if a directory or the file itself is writable by its group or by
/// every account, or has an access control entry that grants a right to change it.
/// Each directory passed is then one only this user or root can change, so no other
/// account can replace any link or file under it. Group write is refused even for the
/// `admin` group, which a standard Homebrew prefix grants, because that group's members
/// are other accounts.
///
/// The app applies it to the uv it runs to ask where `uv tool install` puts `metab`.
public nonisolated enum ExecutableTrust {
    /// One file system object, as `lstat(2)` and its access control list describe it.
    public struct Node: Equatable, Sendable {
        public enum Kind: Equatable, Sendable {
            case directory
            case file
            /// A symbolic link, with its target as written.
            case link(String)
            case other
        }

        public var kind: Kind
        public var owner: uid_t
        public var mode: mode_t
        /// Whether an allow entry of its access control list grants a right to change it.
        public var aclGrantsWrite: Bool

        public init(kind: Kind, owner: uid_t, mode: mode_t, aclGrantsWrite: Bool) {
            self.kind = kind
            self.owner = owner
            self.mode = mode
            self.aclGrantsWrite = aclGrantsWrite
        }
    }

    /// More links than this on one path is a loop, as `MAXSYMLINKS` has it.
    static let linkLimit = 32

    /// Why the app may not run `path`, or nil if it may.
    public static func refusal(
        _ path: String, uid: uid_t = getuid(), inspect: (String) -> Node? = { live($0) }
    ) -> String? {
        guard path.hasPrefix("/") else { return "\(path) is not an absolute path" }
        func check(_ node: Node, _ name: String) -> String? {
            if node.owner != uid && node.owner != 0 {
                return "\(name) belongs to another account (uid \(node.owner))"
            }
            if case .link = node.kind { return nil }  // its directory decides who can replace it
            if node.mode & S_IWOTH != 0 { return "\(name) can be changed by every account" }
            if node.mode & S_IWGRP != 0 { return "\(name) can be changed by its group" }
            if node.aclGrantsWrite {
                return "\(name) has an access control entry that grants a right to change it"
            }
            return nil
        }
        guard let root = inspect("/") else { return "/ cannot be read" }
        if let reason = check(root, "/") { return reason }
        var directory = "/"
        var remaining = components(path)
        var links = 0
        while !remaining.isEmpty {
            let name = remaining.removeFirst()
            if name == ".." {
                // Every ancestor of a directory reached was checked on the way down.
                directory = parent(of: directory)
                continue
            }
            let next = directory == "/" ? "/" + name : directory + "/" + name
            guard let node = inspect(next) else { return "\(next) does not exist" }
            if let reason = check(node, next) { return reason }
            switch node.kind {
            case .link(let target):
                links += 1
                guard links <= linkLimit else { return "\(path) passes through too many symbolic links" }
                if target.hasPrefix("/") { directory = "/" }
                remaining = components(target) + remaining
            case .directory:
                directory = next
            case .file:
                return remaining.isEmpty ? nil : "\(next) is not a directory"
            case .other:
                return "\(next) is not a regular file"
            }
        }
        return "\(path) is not a regular file"
    }

    private static func components(_ path: String) -> [String] {
        path.split(separator: "/").map(String.init).filter { $0 != "." }
    }

    private static func parent(of directory: String) -> String {
        guard let slash = directory.lastIndex(of: "/"), slash != directory.startIndex else { return "/" }
        return String(directory[..<slash])
    }

    /// `path` itself, not what a link at it points to, or nil if there is nothing there.
    public static func live(_ path: String) -> Node? {
        var info = stat()
        guard lstat(path, &info) == 0 else { return nil }
        let kind: Node.Kind
        switch info.st_mode & S_IFMT {
        case S_IFDIR: kind = .directory
        case S_IFREG: kind = .file
        case S_IFLNK:
            var buffer = [CChar](repeating: 0, count: Int(PATH_MAX) + 1)
            let count = readlink(path, &buffer, Int(PATH_MAX))
            guard count >= 0 else { return nil }
            kind = .link(String(decoding: buffer[..<count].map { UInt8(bitPattern: $0) }, as: UTF8.self))
        default: kind = .other
        }
        return Node(kind: kind, owner: info.st_uid, mode: info.st_mode, aclGrantsWrite: aclGrantsWrite(path))
    }

    /// Whether an allow entry of `path`'s extended access control list grants any right to
    /// change it, or what it holds. Whom the entry names is not looked up, so one naming
    /// this user counts too; an owner needs none, so such entries are rare.
    private static func aclGrantsWrite(_ path: String) -> Bool {
        guard let acl = acl_get_link_np(path, ACL_TYPE_EXTENDED) else { return false }
        defer { acl_free(UnsafeMutableRawPointer(acl)) }
        let writes: [acl_perm_t] = [
            ACL_WRITE_DATA, ACL_APPEND_DATA, ACL_DELETE, ACL_DELETE_CHILD, ACL_WRITE_ATTRIBUTES,
            ACL_WRITE_EXTATTRIBUTES, ACL_WRITE_SECURITY, ACL_CHANGE_OWNER,
        ]
        var entry: acl_entry_t?
        var which = ACL_FIRST_ENTRY.rawValue
        while acl_get_entry(acl, which, &entry) == 0, let current = entry {
            which = ACL_NEXT_ENTRY.rawValue
            var tag = ACL_UNDEFINED_TAG
            guard acl_get_tag_type(current, &tag) == 0, tag == ACL_EXTENDED_ALLOW else { continue }
            var permissions: acl_permset_t?
            if acl_get_permset(current, &permissions) == 0, let permissions,
               writes.contains(where: { acl_get_perm_np(permissions, $0) == 1 }) {
                return true
            }
        }
        return false
    }
}
