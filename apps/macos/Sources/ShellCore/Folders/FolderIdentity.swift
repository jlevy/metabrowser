import Foundation

/// What a folder's server serves.
public nonisolated enum FolderKind: String, Codable, Equatable, Sendable {
    /// A folder on this Mac: its window has a proxy icon and a path menu.
    case folder
    /// A cached Git mirror: its cache path means nothing to the user, so it has neither.
    case mirror
}

/// Which folder a window shows, as `GET /api/identity` names it:
///
///     {"short_name": "fdu", "full_name": "~/wrk/github/fdu", "kind": "folder",
///      "kind_label": "Local folder", "title": "fdu • Metabrowser"}
public nonisolated struct FolderIdentity: Codable, Equatable, Sendable {
    public static let appName = "Metabrowser"

    /// The folder's own name, or a mirror's repository name: what tells windows apart.
    public var shortName: String
    /// The path with `~` for home, or a mirror's abbreviated origin.
    public var fullName: String
    public var kind: FolderKind
    /// "Local folder" or "Cached mirror".
    public var kindLabel: String
    /// "fdu • Metabrowser", the plain title.
    public var title: String

    public init(shortName: String, fullName: String, kind: FolderKind, kindLabel: String, title: String) {
        self.shortName = shortName
        self.fullName = fullName
        self.kind = kind
        self.kindLabel = kindLabel
        self.title = title
    }

    enum CodingKeys: String, CodingKey {
        case shortName = "short_name"
        case fullName = "full_name"
        case kind
        case kindLabel = "kind_label"
        case title
    }

    /// The plain title for `shortName`, worded as the server words it.
    public static func title(for shortName: String) -> String {
        "\(shortName) • \(appName)"
    }

    /// A local folder's identity, from its path alone, named as `metab` names it: the
    /// folder's own name, `~` for the home folder, and `/` for the root.
    ///
    /// A window shows it while its server starts, before there is a route to ask, and
    /// keeps it if asking fails.
    ///
    /// `root` is canonical, as the app opens it, and `home` is compared with symbolic
    /// links resolved, as `metab` compares it.
    public static func localFolder(
        _ root: URL, home: String = FileChecks.canonicalPath(NSHomeDirectory())
    ) -> FolderIdentity {
        var path = root.path(percentEncoded: false)
        while path.count > 1, path.hasSuffix("/") { path.removeLast() }
        let fullName = abbreviatingHome(path, home: home)
        let name = fullName == "~" || path == "/" ? fullName : (path as NSString).lastPathComponent
        return FolderIdentity(
            shortName: name, fullName: fullName, kind: .folder, kindLabel: "Local folder", title: title(for: name))
    }

    /// `path` with the home folder written `~`, as `metab` writes it.
    public static func abbreviatingHome(_ path: String, home: String) -> String {
        var home = home
        while home.count > 1, home.hasSuffix("/") { home.removeLast() }
        guard home.count > 1 else { return path }
        if path == home { return "~" }
        if path.hasPrefix(home + "/") { return "~" + path.dropFirst(home.count) }
        return path
    }
}

/// What a folder's server said when asked who it is.
public nonisolated enum IdentityAnswer: Equatable, Sendable {
    case identity(FolderIdentity)
    /// No answer, a status other than 200, or a body that is not an identity.
    case failed(String)

    /// The identity a window shows: the server's, else `fallback`.
    public func identity(or fallback: FolderIdentity) -> FolderIdentity {
        if case .identity(let identity) = self { return identity }
        return fallback
    }
}

/// Asks a ready server for its folder's identity.
public nonisolated enum IdentityClient {
    public static let path = "api/identity"
    /// An identity is a few hundred bytes; a body past this is not one.
    public static let byteLimit = 64 * 1024

    /// Sends a request and returns the status and body.
    public typealias Transport = @Sendable (URLRequest) async throws -> (status: Int, body: Data)

    public static func request(origin: URL, authorization: WebAuthorization) -> URLRequest {
        var request = URLRequest(url: origin.appending(path: path))
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if case .cookie(let name, let value) = authorization {
            request.setValue("\(name)=\(value)", forHTTPHeaderField: "Cookie")
        }
        return request
    }

    public static func fetch(
        origin: URL, authorization: WebAuthorization, transport: Transport = live
    ) async -> IdentityAnswer {
        do {
            let (status, body) = try await transport(request(origin: origin, authorization: authorization))
            return answer(status: status, body: body)
        } catch {
            return .failed("no answer: \(error.localizedDescription)")
        }
    }

    public static func answer(status: Int, body: Data) -> IdentityAnswer {
        guard status == 200 else { return .failed("status \(status)") }
        guard body.count <= byteLimit else { return .failed("a body of \(body.count) bytes") }
        let identity: FolderIdentity
        do {
            identity = try JSONDecoder().decode(FolderIdentity.self, from: body)
        } catch {
            return .failed("not an identity: \(error)")
        }
        guard !identity.shortName.isEmpty, !identity.title.isEmpty else {
            return .failed("an empty short_name or title")
        }
        return .identity(identity)
    }

    /// Ephemeral, uncached, never through a system proxy, and bounded in time, like
    /// the readiness probe.
    public static let live: Transport = { request in
        let (body, response) = try await session.data(for: request)
        return ((response as? HTTPURLResponse)?.statusCode ?? 0, body)
    }

    private static let session: URLSession = {
        let configuration = URLSessionConfiguration.ephemeral
        configuration.connectionProxyDictionary = [:]
        configuration.timeoutIntervalForRequest = 2
        configuration.timeoutIntervalForResource = 5
        configuration.requestCachePolicy = .reloadIgnoringLocalCacheData
        configuration.httpShouldSetCookies = false
        return URLSession(configuration: configuration)
    }()
}
