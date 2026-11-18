import WebKit

/// The configurations every folder window's web views are built from.
public enum WebConfiguration {
    /// A window's page: persistent cookies and local storage in the default store, since
    /// Metabrowser keeps its preferences in host-only cookies that every folder's server
    /// shares across ports, element full screen, the rules in `restrict(_:)`, and, given
    /// them, the page's own Print button (`PagePrintRequests`) and its View on GitHub
    /// button (`GitHubViewRequests`).
    public static func make(
        pagePrints: PagePrintRequests? = nil, gitHubViews: GitHubViewRequests? = nil
    ) -> WKWebViewConfiguration {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.preferences.isElementFullscreenEnabled = true
        restrict(configuration)
        pagePrints?.install(in: configuration)
        gitHubViews?.install(in: configuration)
        return configuration
    }

    /// The web view in a window's GitHub popover (`GitHubView`): github.com in
    /// `GitHubDataStore.shared`, with element full screen and the rules in `restrict(_:)`,
    /// and none of the page's scripts.
    public static func makeGitHub() -> WKWebViewConfiguration {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = GitHubDataStore.shared
        configuration.preferences.isElementFullscreenEnabled = true
        restrict(configuration)
        return configuration
    }

    /// The popover's web view, on `makeGitHub()`: a plain `WKWebView`, so a file dropped on
    /// it reaches github.com, as a screenshot dropped on a comment box should, where a
    /// folder's page, a `DropAwareWebView`, opens a dropped file in Metabrowser. Its zoom is
    /// its own: it starts at 100%, never at the pages' remembered zoom, and is never saved.
    public static func makeGitHubWebView(isInspectable: Bool) -> WKWebView {
        let webView = WKWebView(frame: .zero, configuration: makeGitHub())
        webView.isInspectable = isInspectable
        webView.allowsBackForwardNavigationGestures = true
        return webView
    }

    /// What a page may not do by itself. Applied again to the configuration WebKit hands
    /// to `createWebViewWith`, so a window a page opens follows the same rules.
    ///
    /// - `javaScriptCanOpenWindowsAutomatically` off: `window.open` needs a user gesture.
    ///   macOS defaults it to on (`WKPreferences.h`), and the navigation policy allows the
    ///   server's own origin, so a previewed HTML file could otherwise open tab after tab
    ///   of the folder's window without a click.
    public static func restrict(_ configuration: WKWebViewConfiguration) {
        configuration.preferences.javaScriptCanOpenWindowsAutomatically = false
    }
}

/// Where every GitHub popover keeps what github.com stores: its sign-in cookies, local
/// storage, and cache.
///
/// One persistent `WKWebsiteDataStore`, named by `identifier`, serves the GitHub popover in
/// every window and tab, so signing in to GitHub once holds in all of them, and WebKit
/// keeps it on disk, under `~/Library/WebKit/<bundle identifier>/WebsiteDataStore/`, so it
/// holds after a relaunch. Each build variant has its own bundle identifier and so its own store.
///
/// It is a store of its own, not the default one the folders' pages use, so a page a
/// folder's server serves never shares a cookie jar with github.com, and clearing it
/// (`clear()`, Metabrowser > Clear GitHub Data…) signs you out of GitHub without touching
/// Metabrowser's own preferences or any page's local storage.
public enum GitHubDataStore {
    /// Fixed for the life of the app: a new identifier is a new, empty store, which would
    /// sign everyone out and leave the old one on disk.
    public static let identifier = UUID(uuidString: "5DE648DD-D5B9-4F54-8403-7DAF088E158C")!

    /// The one store, made once and kept, so every popover's web view holds the same
    /// instance.
    public static let shared = WKWebsiteDataStore(forIdentifier: identifier)

    /// Removes everything GitHub stored, which signs you out of GitHub in every window.
    public static func clear() async {
        await shared.removeData(ofTypes: WKWebsiteDataStore.allWebsiteDataTypes(), modifiedSince: .distantPast)
    }
}
