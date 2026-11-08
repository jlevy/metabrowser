import Foundation

/// Where a ready server is reached.
public nonisolated struct ServerEndpoint: Equatable, Sendable {
    /// `http://127.0.0.1:<port>`: what the navigation policy keeps in the window.
    public var origin: URL
    /// The first page to load.
    public var entryURL: URL

    public init(origin: URL, entryURL: URL) {
        self.origin = origin
        self.entryURL = entryURL
    }
}

/// What a window installs before its first load so the server accepts it.
public nonisolated enum WebAuthorization: Equatable, Sendable {
    /// The server needs nothing: the CLI's serve mode has no session token today.
    case none
    /// An HttpOnly, SameSite=Strict cookie on the server's host. Cookies ignore ports,
    /// so a host-mode server names it per instance.
    case cookie(name: String, value: String)
}

/// How one kind of server is started, recognized as ready, and authorized.
///
/// The supervisor and the windows depend only on this, so the brief's host mode (port
/// 0, a JSON ready line, a stdin token, `/healthz`, a session cookie) replaces
/// `CLIServeLaunch` without touching either. See README.md, "Gaps to Close".
public nonisolated protocol ServerLaunch: Sendable {
    /// The arguments after the executable that serve `root`.
    func arguments(serving root: URL) -> [String]
    /// The first line written to the child's stdin, or nil if the server reads none.
    var stdinLine: String? { get }
    /// The endpoint, if `line` is the server's announcement of its address.
    func endpoint(announcedBy line: String) -> ServerEndpoint?
    /// The URL polled after the announcement until it answers 2xx.
    func readinessURL(for endpoint: ServerEndpoint) -> URL
    /// What each window installs before loading the endpoint.
    func authorization(for endpoint: ServerEndpoint) -> WebAuthorization
}

/// Today's `metab ROOT --no-open` serve mode, unchanged.
///
/// It serves on the first free port walking up from `basePort` (`--port 0` is
/// rejected), and prints `Serving <root> at http://127.0.0.1:<port>/view/…` to stdout
/// before its socket listens, which is why readiness also polls for a 2xx.
public nonisolated struct CLIServeLaunch: ServerLaunch {
    public static let defaultBasePort = 8411
    public static let host = "127.0.0.1"

    public var basePort: Int

    public init(basePort: Int = CLIServeLaunch.defaultBasePort) {
        self.basePort = basePort
    }

    public func arguments(serving root: URL) -> [String] {
        [root.path(percentEncoded: false), "--no-open", "--host", Self.host, "--port", String(basePort)]
    }

    public var stdinLine: String? { nil }

    public func endpoint(announcedBy line: String) -> ServerEndpoint? {
        Self.parseServingLine(line)
    }

    /// The printed `/view/` URL is the index route the CLI itself polls before opening a
    /// browser; there is no `/healthz` yet.
    public func readinessURL(for endpoint: ServerEndpoint) -> URL { endpoint.entryURL }

    public func authorization(for endpoint: ServerEndpoint) -> WebAuthorization { .none }

    /// Parses `Serving <root> at <url>`, optionally followed by `  [dev build: …]`.
    ///
    /// The root may contain anything, including " at ", so the URL is the last
    /// " at http://" match. Only plain HTTP on a loopback address with an explicit
    /// port is accepted.
    public static func parseServingLine(_ line: String) -> ServerEndpoint? {
        guard line.hasPrefix("Serving "),
              let marker = line.range(of: " at http://", options: .backwards)
        else { return nil }
        let rest = line[marker.upperBound...].prefix { !$0.isWhitespace }
        guard let url = URL(string: "http://" + rest),
              url.scheme == "http",
              let host = url.host(percentEncoded: false),
              host == "127.0.0.1" || host == "::1",
              let port = url.port, (1...65535).contains(port),
              url.user == nil, url.password == nil
        else { return nil }
        let authority = host.contains(":") ? "[\(host)]:\(port)" : "\(host):\(port)"
        guard let origin = URL(string: "http://\(authority)") else { return nil }
        return ServerEndpoint(origin: origin, entryURL: url)
    }
}
