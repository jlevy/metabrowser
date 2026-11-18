import Foundation

/// Whether a repository's server found what the link it started on names (review C1 on
/// #539).
///
/// `metab` serves a link whose branch, tag, or commit its mirror lacks from the default
/// branch, announces `/view/`, and fetches once in the background
/// (`src/metabrowser/cli/git_pin_cli.py`). `/api/source/status` then says
/// `selection_state` `pending` until that fetch ends, and `found`, which a page shows by
/// going to `selection_href` itself (`static/source-freshness.js`), or `not_found` or
/// `fetch_failed`, where every window of the repository goes on showing the default
/// branch, which only a chip in the page says. So the app asks after each start of a
/// repository's server, while the answer is `pending`, and says when the link's selection
/// was not found. `null` is a link that named nothing the mirror lacked.
public nonisolated enum LinkSelection {
    public static let route = "api/source/status"
    /// A status is about a kilobyte; a body past this is not one.
    static let byteLimit = 64 * 1024
    /// How often the app asks while the fetch runs, and how many times before it stops
    /// watching. Not measured: they bound how long the app watches, not a cost; the
    /// page's chip still says what a longer fetch found, and a loopback request a second
    /// costs the server nothing it notices.
    public static let interval: Duration = .seconds(1)
    public static let attempts = 120

    public enum Outcome: Equatable, Sendable {
        /// Found, or the link named nothing the mirror lacked: nothing to say.
        case shown
        /// GitHub has nothing the link names; the server serves `serving`, a ref's name.
        case notFound(serving: String?)
        /// The fetch for it did not run, which the server's next refresh retries.
        case fetchFailed(serving: String?)
        /// Still pending after every attempt, or the status could not be read.
        case unknown(String)
    }

    enum Reading: Equatable {
        case pending
        case settled(Outcome)
    }

    static func read(status: Int, body: Data) -> Reading {
        guard status == 200 else { return .settled(.unknown("status \(status)")) }
        guard body.count <= byteLimit,
              let fields = try? JSONSerialization.jsonObject(with: body) as? [String: Any]
        else { return .settled(.unknown("not a source status")) }
        let serving = fields["ref_name"] as? String
        switch fields["selection_state"] as? String {
        case "pending": return .pending
        case "not_found": return .settled(.notFound(serving: serving))
        case "fetch_failed": return .settled(.fetchFailed(serving: serving))
        default: return .settled(.shown)  // null, found, superseded
        }
    }

    /// Asks `origin` until its answer is no longer `pending`, or `attempts` have been made.
    public static func watch(
        origin: URL, authorization: WebAuthorization, transport: IdentityClient.Transport = IdentityClient.live,
        interval: Duration = interval, attempts: Int = attempts
    ) async -> Outcome {
        let request = IdentityClient.request(origin: origin, authorization: authorization, route: route)
        let attempts = max(attempts, 1)
        for attempt in 1...attempts {
            let answer: (status: Int, body: Data)
            do {
                answer = try await transport(request)
            } catch {
                return .unknown("no answer: \(error.localizedDescription)")
            }
            if case .settled(let outcome) = read(status: answer.status, body: answer.body) { return outcome }
            guard attempt < attempts else { break }
            do { try await Task.sleep(for: interval) } catch { return .unknown("no longer asked") }
        }
        return .unknown("still fetching after \(attempts) answers")
    }
}

extension LinkAlert {
    /// What the app says when a repository's server did not find what `link` names, or
    /// nil when there is nothing to say. `name` is the repository's, as `github.com/o/r`.
    public static func selectionMissing(_ outcome: LinkSelection.Outcome, link: URL, repository name: String) -> LinkAlert? {
        let shown = GitHubLink.shown(link)
        switch outcome {
        case .shown, .unknown:
            return nil
        case .notFound(let serving):
            return LinkAlert(
                message: "\(name) has nothing this link names",
                detail: "Even after fetching, \(name) has no branch, tag, commit, or pull request that this link names, so its windows show \(serving ?? "its default branch") instead.\n\n\(shown)")
        case .fetchFailed(let serving):
            return LinkAlert(
                message: "Metabrowser could not fetch what this link names",
                detail: "Metabrowser’s copy of \(name) does not have what this link names yet, and fetching it failed, so its windows show \(serving ?? "its default branch") until a refresh finds it.\n\n\(shown)")
        }
    }
}
