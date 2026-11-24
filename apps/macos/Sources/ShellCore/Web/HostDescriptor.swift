import WebKit

/// What the page's host can do beyond what any browser does, as the page reads it: a
/// frozen `window.metabrowserHost` (`name`) of action names, such as `open-file`
/// (`OpenFileRequests.action`), which the SDK's `mb.host.supports(action)` answers from.
///
/// It names actions, never the host, so a plugin asks whether its host can open a file,
/// not whether it is in the app, and a browser, which defines none, supports nothing. It
/// is a hint for what to draw: the handler behind each action checks every request
/// itself. A user script, installed by `WebConfiguration.make` for the handlers it is
/// given, defines it at document start in the page's own world, where the page's scripts
/// read it, in the main frame only, and not in a document with an opaque origin, such as
/// a sandboxed `/raw` document, which no handler answers. The property can be neither
/// written nor redefined, so a page's script cannot make the host claim another action.
public enum HostDescriptor {
    /// The global the page reads.
    public static let name = "metabrowserHost"

    /// The script that defines the descriptor with `actions`, each a name of lowercase
    /// letters, digits, and hyphens, which needs no escaping in a JavaScript string.
    static func source(actions: [String]) -> String {
        precondition(actions.allSatisfy(isActionName), "an action is lowercase letters, digits, and hyphens")
        let list = actions.map { "\"\($0)\"" }.joined(separator: ", ")
        return """
            (() => {
                if (self.origin === "null") {
                    return;
                }
                Object.defineProperty(window, "\(name)", {
                    value: Object.freeze({ actions: Object.freeze([\(list)]) }),
                    writable: false,
                    configurable: false,
                    enumerable: false,
                });
            })();
            """
    }

    static func isActionName(_ action: String) -> Bool {
        !action.isEmpty && action.allSatisfy { ("a"..."z").contains($0) || ("0"..."9").contains($0) || $0 == "-" }
    }

    /// Installs the descriptor for `actions`, or nothing when there are none, as for a
    /// configuration with no handler that answers one.
    static func install(actions: [String], in configuration: WKWebViewConfiguration) {
        guard !actions.isEmpty else { return }
        configuration.userContentController.addUserScript(WKUserScript(
            source: source(actions: actions), injectionTime: .atDocumentStart, forMainFrameOnly: true))
    }
}
