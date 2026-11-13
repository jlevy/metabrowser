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

    /// Why `root` cannot be served this way, or nil. The announcement is one line of
    /// text that contains the root, so a line break in the path would let the folder's
    /// name forge an announcement. The JSON ready line of host mode removes this class.
    public static func unservableReason(_ root: URL) -> String? {
        let path = root.path(percentEncoded: false)
        return path.contains(where: { $0.isNewline }) ? "its path contains a line break" : nil
    }

    /// Parses `Serving <root> at <url>`, optionally followed by `  [dev build: …]`.
    ///
    /// The root may contain anything but a line break, including " at ", so the URL is
    /// the token after the last " at ", and it must end the line (before the optional
    /// suffix). Only plain HTTP on a loopback address with an explicit port is accepted.
    public static func parseServingLine(_ line: String) -> ServerEndpoint? {
        guard line.hasPrefix("Serving "), !line.contains(where: { $0.isNewline }) else { return nil }
        var text = Substring(line)
        if let suffix = text.range(of: "  [dev build: ", options: .backwards), text.hasSuffix("]") {
            text = text[..<suffix.lowerBound]
        }
        guard let marker = text.range(of: " at ", options: .backwards) else { return nil }
        let token = text[marker.upperBound...]
        guard token.hasPrefix("http://"), !token.contains(where: { $0.isWhitespace }),
              let url = URL(string: String(token)),
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

extension ServerLaunch {
    /// The command that serves `root` with `setup`'s `metab`: its arguments and stdin line,
    /// the allowlisted environment with `setup`'s tool directories first on `PATH`, and
    /// the folder as the working directory, since `metab .` run from Terminal reads
    /// `.env` files upward from the folder.
    public func spec(
        serving root: URL, with setup: RuntimeSetup, inherited: [String: String], logURL: URL?
    ) -> LaunchSpec {
        LaunchSpec(
            executable: setup.runtime.executable,
            arguments: arguments(serving: root),
            environment: ChildEnvironment.build(inherited: inherited, toolDirectories: setup.tools.directories),
            workingDirectory: root.path(percentEncoded: false),
            stdinLine: stdinLine,
            logURL: logURL)
    }
}
