import Foundation
import WebKit

/// A page's Open link, clicked in a folder window, which opens the file it names in the
/// app macOS assigns to its type (`OpenFilePlan`).
///
/// A page marks such a link `data-metabrowser-open-file` (`attribute`), as the `pdf`
/// plugin's Open is: an `a` whose `href` is the file's `/raw?path=<identity>` on the
/// folder's server, whose `download` is the file's name, and whose marker's value is the
/// subject the path belongs to, `filesystem` or `git_revision` (`Request.Subject`). In a
/// browser it is a download, which follows the browser's rule for the type. The page
/// draws it only when the host says it can open files (`HostDescriptor`), and it knows
/// nothing else of the app.
///
/// A user script, installed by `WebConfiguration.make` in each page's main frame, takes a
/// trusted primary click with no modifier key on a marked link, cancels the link's own
/// download, and posts its `href`, its subject, and its `download` name to this handler.
/// The script and the handler live in the app's own content world (`world`), as
/// `WebViewRequests`' do, so the page's scripts cannot post to the handler, and a click a
/// script dispatches is not trusted. A click with a modifier or another button, and any
/// click in a document with an opaque origin, such as a sandboxed `/raw` document, is left
/// to the link, which downloads the file through the save panel. A link with a `download`
/// attribute and no marker is never the script's.
public final class OpenFileRequests: NSObject, WKScriptMessageHandler {
    public static let handlerName = "metabrowserOpenFile"
    /// The attribute that marks an Open link, whose value is the link's subject.
    public static let attribute = "data-metabrowser-open-file"
    /// The action the host descriptor names for this handler (`HostDescriptor`), which a
    /// page asks about before it draws an Open link.
    public static let action = "open-file"
    /// A link the script takes.
    public static var marker: String { "a[\(attribute)]" }
    /// The app's own content world, where the script runs and the handler answers.
    public static var world: WKContentWorld { .defaultClient }

    static var source: String {
        """
        window.addEventListener("click", (event) => {
            if (self.origin === "null" || !event.isTrusted || event.button !== 0 || event.metaKey
                || event.ctrlKey || event.shiftKey || event.altKey) {
                return;
            }
            const link = event.target instanceof Element ? event.target.closest('\(marker)') : null;
            if (!(link instanceof HTMLAnchorElement)) {
                return;
            }
            event.preventDefault();
            window.webkit.messageHandlers.\(handlerName).postMessage({
                href: link.href,
                subject: link.getAttribute("\(attribute)") ?? "",
                name: link.getAttribute("download") ?? "",
            });
        }, true);
        """
    }

    /// One click on a marked link, as the script posts it.
    public nonisolated struct Request: Equatable, Sendable {
        /// What a marked link's path belongs to, as the page's `mb.sourceKind()` says.
        public enum Subject: String, Equatable, Sendable {
            /// A folder on disk: the path is relative to the folder's root.
            case filesystem = "filesystem"
            /// A pinned revision or a mirror, which has no file on disk: the path is an
            /// opaque wire, and only the server can answer it.
            case gitRevision = "git_revision"
        }

        /// The link's `href`: an `http` or `https` URL whose path is `/raw` and whose query
        /// has one non-empty `path`.
        public let href: URL
        public let subject: Subject
        /// The `path` parameter, decoded as the server decodes a query.
        public let path: String
        /// A file name to keep a copy under and to name in an alert: the link's `download`,
        /// or the last part of `path` when that is not a usable name.
        public let name: String

        /// Nil for a message of any other shape.
        public init?(_ body: Any) {
            guard let body = body as? [String: Any], let text = body["href"] as? String,
                  let subject = (body["subject"] as? String).flatMap(Subject.init(rawValue:)),
                  let href = URL(string: text), let path = Self.rawPath(href)
            else { return nil }
            let fallback = path.split(separator: "/", omittingEmptySubsequences: false).last.map(String.init)
            guard let name = Self.fileName(body["name"] as? String) ?? Self.fileName(fallback) else { return nil }
            self.href = href
            self.subject = subject
            self.path = path
            self.name = name
        }

        /// The one `path` of a `/raw` URL on `http` or `https`, or nil. The query is read
        /// as a form, as the server reads it: `+` is a space, then percent-escapes decode.
        static func rawPath(_ href: URL) -> String? {
            guard let scheme = href.scheme?.lowercased(), scheme == "http" || scheme == "https",
                  let parts = URLComponents(url: href, resolvingAgainstBaseURL: false), parts.host?.isEmpty == false,
                  parts.path == "/raw"
            else { return nil }
            let values = (parts.percentEncodedQueryItems ?? []).filter { $0.name == "path" }
            guard values.count == 1,
                  let path = values[0].value?.replacingOccurrences(of: "+", with: " ").removingPercentEncoding,
                  !path.isEmpty, !path.contains("\0")
            else { return nil }
            return path
        }

        /// `text` if it can name a file in a folder of its own: not empty, `.` or `..`, with
        /// no `/` or NUL, and no longer than a file name may be (`NAME_MAX` bytes).
        static func fileName(_ text: String?) -> String? {
            guard let text, !text.isEmpty, text != ".", text != "..", !text.contains("/"), !text.contains("\0"),
                  text.utf8.count <= Int(NAME_MAX)
            else { return nil }
            return text
        }
    }

    private let onRequest: (WKWebView, WKFrameInfo, Request) -> Void

    /// `onRequest` gets the web view, the frame that asked, and what it asked for. A
    /// message of another shape is dropped.
    public init(onRequest: @escaping (WKWebView, WKFrameInfo, Request) -> Void) {
        self.onRequest = onRequest
    }

    func install(in configuration: WKWebViewConfiguration) {
        let controller = configuration.userContentController
        controller.addUserScript(WKUserScript(
            source: Self.source, injectionTime: .atDocumentStart, forMainFrameOnly: true, in: Self.world))
        controller.add(self, contentWorld: Self.world, name: Self.handlerName)
    }

    public func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let webView = message.webView, let request = Request(message.body) else { return }
        onRequest(webView, message.frameInfo, request)
    }
}

extension OpenFileRequests {
    /// Whether a window opens the file a click in `frame` asks for: only from the main
    /// frame of a document of the server's own origin, as for the page's Print button
    /// (`PagePrintRequests.allows`), so a `/raw` HTML file, whose CSP sandbox gives it an
    /// opaque origin, cannot use a marked link of its own; and only for a link to the
    /// server's own origin.
    public static func allows(_ frame: WKFrameInfo, _ request: Request, under policy: NavigationPolicy) -> Bool {
        let origin = frame.securityOrigin
        return policy.allowsOpenFile(
            request.href, scheme: origin.protocol, host: origin.host, port: origin.port, isMainFrame: frame.isMainFrame)
    }
}

extension NavigationPolicy {
    /// Whether a document whose security origin is `scheme`, `host`, and `port` (0 for the
    /// scheme's default, as WebKit reports it) may open the file at `href`: the main frame
    /// of a page of the server's own origin (`isAppDocument`), asking for a file of the
    /// server's own origin.
    public func allowsOpenFile(_ href: URL, scheme: String, host: String, port: Int, isMainFrame: Bool) -> Bool {
        isAppDocument(scheme: scheme, host: host, port: port, isMainFrame: isMainFrame) && isAppOrigin(href)
    }
}
