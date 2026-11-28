import CoreFoundation
import WebKit

public final class NavigationHistoryRequests: NSObject, WKScriptMessageHandler {
    public static let action = "navigation-history"
    public static let handlerName = "metabrowserNavigation"

    public enum Direction: String {
        case back, forward
    }

    public struct Label {
        public let url: String
        public let title: String
        public let icon: String?
        public let context: String?
    }

    public enum Request {
        case state(String)
        case history(Direction, url: String)
        case reveal(Bool, url: String)
        case label(Label)
    }

    private let onRequest: (WKWebView, WKFrameInfo, Request) -> Void

    public init(onRequest: @escaping (WKWebView, WKFrameInfo, Request) -> Void) {
        self.onRequest = onRequest
    }

    func install(in configuration: WKWebViewConfiguration) {
        configuration.userContentController.add(self, name: Self.handlerName)
    }

    public func userContentController(_ controller: WKUserContentController, didReceive message: WKScriptMessage) {
        guard let view = message.webView, let request = Self.request(from: message.body) else { return }
        onRequest(view, message.frameInfo, request)
    }

    static func request(from body: Any) -> Request? {
        guard let fields = body as? [String: Any], let kind = fields["kind"] as? String else { return nil }
        guard let url = fields["url"] as? String, !url.isEmpty, url.utf8.count <= 65_536 else { return nil }
        switch kind {
        case "state":
            return .state(url)
        case "history":
            guard let direction = (fields["direction"] as? String).flatMap(Direction.init(rawValue:)) else {
                return nil
            }
            return .history(direction, url: url)
        case "reveal":
            guard let flag = fields["visible"] as? NSNumber, CFGetTypeID(flag) == CFBooleanGetTypeID() else {
                return nil
            }
            return .reveal(flag.boolValue, url: url)
        case "label":
            guard let title = fields["title"] as? String, !title.isEmpty, title.utf8.count <= 512
            else { return nil }
            let icon = (fields["icon"] as? String).flatMap { $0.utf8.count <= 32 ? $0 : nil }
            let context = (fields["context"] as? String).flatMap { $0.utf8.count <= 512 ? $0 : nil }
            return .label(Label(url: url, title: title, icon: icon, context: context))
        default:
            return nil
        }
    }

    public static func allows(_ frame: WKFrameInfo, under policy: NavigationPolicy) -> Bool {
        let origin = frame.securityOrigin
        return policy.isAppDocument(
            scheme: origin.protocol, host: origin.host, port: origin.port, isMainFrame: frame.isMainFrame)
    }
}
