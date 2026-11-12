import Darwin
import Foundation

/// A page of a folder's server without the server's origin, which changes each time the
/// server starts: a path, with any query and fragment.
public nonisolated struct PageAddress: Codable, Hashable, Sendable {
    /// `/view/docs/plan.md?mode=raw#top`.
    public let reference: String

    /// Only a path-absolute reference is a page of the server: a scheme or a host, which
    /// `//` would start, names another one.
    public init?(reference: String) {
        guard reference.hasPrefix("/"), !reference.hasPrefix("//"),
              let parts = URLComponents(string: reference), parts.scheme == nil, parts.host == nil
        else { return nil }
        self.reference = reference
    }

    /// The page `url` shows.
    public init?(_ url: URL) {
        guard let parts = URLComponents(url: url, resolvingAgainstBaseURL: true) else { return nil }
        var page = URLComponents()
        page.percentEncodedPath = parts.percentEncodedPath
        page.percentEncodedQuery = parts.percentEncodedQuery
        page.percentEncodedFragment = parts.percentEncodedFragment
        guard let reference = page.string else { return nil }
        self.init(reference: reference)
    }

    /// `metab`'s view route for a path relative to the served folder, spelled as
    /// `view_routes.format_view_href` spells it: each segment's UTF-8 bytes, with every
    /// byte outside `A-Z a-z 0-9 _ . - ~` written `%XX`.
    public static func view(of relativePath: String) -> PageAddress {
        let segments = relativePath.split(separator: "/", omittingEmptySubsequences: false).map(escape)
        // Every segment is escaped, so the reference is a path that starts with one slash.
        return PageAddress(reference: "/view/" + segments.joined(separator: "/"))!
    }

    /// The page on the server at `origin`.
    public func url(on origin: URL) -> URL? {
        URL(string: reference).flatMap { NavigationPolicy.rebase($0, onto: origin) }
    }

    public init(from decoder: any Decoder) throws {
        let container = try decoder.singleValueContainer()
        let reference = try container.decode(String.self)
        guard let page = PageAddress(reference: reference) else {
            throw DecodingError.dataCorruptedError(in: container, debugDescription: "not a page of the server")
        }
        self = page
    }

    public func encode(to encoder: any Encoder) throws {
        var container = encoder.singleValueContainer()
        try container.encode(reference)
    }

    private static let unescaped = Set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_.-~".utf8)

    private static func escape(_ segment: Substring) -> String {
        var escaped = ""
        for byte in segment.utf8 {
            if unescaped.contains(byte) {
                escaped.unicodeScalars.append(UnicodeScalar(byte))
            } else {
                escaped += String(format: "%%%02X", byte)
            }
        }
        return escaped
    }
}

/// What a path handed to the app opens: a folder as its own root, or a file at its view
/// route inside a folder.
///
/// A file opens in the most specific open folder that contains it, so it joins the
/// server already showing it, and otherwise in its own folder, as `metab FILE` serves
/// the file's folder. This is the rule the topology brief gives the agent front door.
public nonisolated struct OpenTarget: Equatable, Sendable {
    public enum Kind: Equatable, Sendable {
        case folder
        case file
        /// Missing, or neither a folder nor a regular file (a device, a socket, a pipe).
        case other

        /// What is at `path`, after symbolic links.
        public init(of path: String) {
            var info = stat()
            guard stat(path, &info) == 0 else {
                self = .other
                return
            }
            switch info.st_mode & S_IFMT {
            case S_IFDIR: self = .folder
            case S_IFREG: self = .file
            default: self = .other
            }
        }
    }

    /// The canonical folder whose server shows the target.
    public var root: String
    /// The page to show, or nil for the folder's entry page.
    public var page: PageAddress?

    public init(root: String, page: PageAddress?) {
        self.root = root
        self.page = page
    }

    /// - Parameters:
    ///   - path: an absolute path with symbolic links resolved, as `metab` resolves a file
    ///     before serving its folder; a link to a file elsewhere opens where it points.
    ///   - openRoots: the canonical roots of the folders open now.
    public static func resolve(_ path: String, kind: Kind, openRoots: some Collection<String>) -> OpenTarget? {
        guard path.hasPrefix("/") else { return nil }
        switch kind {
        case .folder:
            return OpenTarget(root: path, page: nil)
        case .file:
            let container = openRoots.filter { contains($0, path) }.max { $0.count < $1.count }
            let root = container ?? (path as NSString).deletingLastPathComponent
            let relative = String(path.dropFirst(root == "/" ? 1 : root.count + 1))
            return OpenTarget(root: root, page: .view(of: relative))
        case .other:
            return nil
        }
    }

    /// Whether `path` is strictly inside `root`.
    static func contains(_ root: String, _ path: String) -> Bool {
        path.hasPrefix(root == "/" ? "/" : root + "/") && path != root
    }
}
