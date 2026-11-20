import Foundation

/// Opens a link into a repository in the server of its mirror, which already serves the
/// repository: `POST /api/source/link`, which `src/metabrowser/source_routes.py`
/// (`api_source_link`) answers.
///
/// The app keeps one mirror per repository, started on the repository itself and never
/// on a link (`SessionRoot`, `FolderSession.open(link:)`), as the owner decided on
/// 2026-11-19. Every link into it, the first one included, goes to this route, which
/// starts a refresh of the mirror and says where the window goes: a pull request's page
/// at `/pull/<n>` and a commit's at `/commit/<id>`, which switch nothing, or for a
/// branch, a folder, a file, or the repository itself the `/view/` address of the
/// revision the link names, which the server switches its pin to first. Only the mirror
/// knows where a ref that holds a `/` ends, so the server decides both; the app never
/// shows a link's page at another revision than the link's (Switching the Pin, in
/// `docs/project/architecture/arch-source-sessions-and-pins.md`).
///
/// A ref or commit the mirror lacks is `202 selection_pending` while the refresh the
/// request started runs. The app then asks `/api/source/status` until `refreshing` is
/// false, and asks the route once more with `"fetch": false`, which answers the page or
/// `404`: no second refresh, and no question that waits forever.
public nonisolated enum SourceLink {
    public static let route = "api/source/link"
    public static let statusRoute = "api/source/status"
    /// An answer is under a kilobyte, a status included; a body past this is not one.
    static let byteLimit = 64 * 1024
    /// How often the app asks whether the refresh a pending link waits for has ended,
    /// and how many times before it stops waiting. Not measured: they bound how long the
    /// app waits, not a cost; a loopback request a second costs the server nothing it
    /// notices, and a refresh that outlasts them leaves the window where it was.
    public static let interval: Duration = .seconds(1)
    public static let attempts = 120

    public enum Outcome: Equatable, Sendable {
        /// The page the window goes to, on the server that answered.
        case page(PageAddress)
        /// Even after the refresh, the mirror has nothing the link names: `code` is the
        /// route's, such as `ref_not_found`. The window stays where it was.
        case notFound(code: String)
        /// No answer the app can act on: the window stays where it was.
        case unknown(String)
    }

    enum Answer: Equatable {
        case page(PageAddress)
        case pending
        case notFound(String)
        case failed(String)
    }

    /// The request for `link`; `fetch` false asks for no refresh.
    static func request(origin: URL, authorization: WebAuthorization, link: URL, fetch: Bool) -> URLRequest {
        var request = IdentityClient.request(origin: origin, authorization: authorization, route: route)
        request.httpMethod = "POST"
        // The server parses only a JSON body on a state-changing request.
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        let body: [String: Any] = ["link": link.absoluteString, "fetch": fetch]
        request.httpBody = try? JSONSerialization.data(withJSONObject: body, options: [.sortedKeys])
        return request
    }

    static func read(status: Int, body: Data) -> Answer {
        guard body.count <= byteLimit,
              let fields = try? JSONSerialization.jsonObject(with: body) as? [String: Any]
        else { return .failed("status \(status), not a link's answer") }
        switch status {
        case 200:
            guard let href = fields["href"] as? String, let page = PageAddress(reference: href) else {
                return .failed("an href that is not a page of the server")
            }
            return .page(page)
        case 202 where fields["code"] as? String == "selection_pending":
            return .pending
        case 404:
            return .notFound(fields["code"] as? String ?? "not_found")
        default:
            return .failed("status \(status): \(fields["code"] as? String ?? "no code")")
        }
    }

    /// Whether the mirror's refresh still runs, from `/api/source/status`; nil for an
    /// answer that is not a status.
    static func refreshing(status: Int, body: Data) -> Bool? {
        guard status == 200, body.count <= byteLimit,
              let fields = try? JSONSerialization.jsonObject(with: body) as? [String: Any]
        else { return nil }
        return fields["refreshing"] as? Bool
    }

    /// Asks the server at `origin` to open `link`, waiting for the refresh it starts when
    /// the mirror lacks what the link names.
    public static func open(
        _ link: URL, origin: URL, authorization: WebAuthorization,
        transport: IdentityClient.Transport = IdentityClient.live,
        interval: Duration = interval, attempts: Int = attempts
    ) async -> Outcome {
        switch await ask(link, origin: origin, authorization: authorization, fetch: true, transport: transport) {
        case .page(let page): return .page(page)
        case .notFound(let code): return .notFound(code: code)
        case .failed(let reason): return .unknown(reason)
        case .pending: break
        }
        let status = IdentityClient.request(origin: origin, authorization: authorization, route: statusRoute)
        var ended = false
        for _ in 0..<max(attempts, 1) {
            do { try await Task.sleep(for: interval) } catch { return .unknown("no longer asked") }
            let answer: (status: Int, body: Data)
            do {
                answer = try await transport(status)
            } catch {
                return .unknown("no answer: \(error.localizedDescription)")
            }
            guard let running = refreshing(status: answer.status, body: answer.body) else {
                return .unknown("not a source status")
            }
            if !running {
                ended = true
                break
            }
        }
        guard ended else { return .unknown("still fetching after \(attempts) answers") }
        switch await ask(link, origin: origin, authorization: authorization, fetch: false, transport: transport) {
        case .page(let page): return .page(page)
        case .notFound(let code): return .notFound(code: code)
        case .failed(let reason): return .unknown(reason)
        case .pending: return .unknown("still pending after the refresh ended")
        }
    }

    private static func ask(
        _ link: URL, origin: URL, authorization: WebAuthorization, fetch: Bool, transport: IdentityClient.Transport
    ) async -> Answer {
        do {
            let answer = try await transport(request(origin: origin, authorization: authorization, link: link, fetch: fetch))
            return read(status: answer.status, body: answer.body)
        } catch {
            return .failed("no answer: \(error.localizedDescription)")
        }
    }
}

extension LinkAlert {
    /// What the app says when the mirror of `name`, a repository's name as
    /// `github.com/o/r`, has nothing `link` names even after a refresh, or nil.
    public static func linkNotFound(_ outcome: SourceLink.Outcome, link: URL, repository name: String) -> LinkAlert? {
        guard case .notFound = outcome else { return nil }
        return LinkAlert(
            message: "\(name) has nothing this link names",
            detail: "Even after fetching, \(name) has no branch, tag, commit, or file that this link names, so its window stays where it was.\n\n\(GitHubLink.shown(link))",
            links: .notOpened(1))
    }
}
