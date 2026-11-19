import WebKit

/// The configurations every folder window's web views are built from.
public enum WebConfiguration {
    /// A window's page: persistent cookies and local storage in the default store, since
    /// Metabrowser keeps its preferences in host-only cookies that every folder's server
    /// shares across ports, element full screen, the rules in `restrict(_:)`, and, given
    /// them, the page's own Print button (`PagePrintRequests`) and its links marked to open
    /// in a web pane (`WebViewRequests`).
    public static func make(
        pagePrints: PagePrintRequests? = nil, webViews: WebViewRequests? = nil
    ) -> WKWebViewConfiguration {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.preferences.isElementFullscreenEnabled = true
        restrict(configuration)
        pagePrints?.install(in: configuration)
        webViews?.install(in: configuration)
        return configuration
    }

    /// A web pane's web view (`WebSite`): its site in `WebDataStore.shared`, with element
    /// full screen and the rules in `restrict(_:)`, and none of the page's scripts.
    public static func makeWebPane() -> WKWebViewConfiguration {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = WebDataStore.shared
        configuration.preferences.isElementFullscreenEnabled = true
        restrict(configuration)
        return configuration
    }

    /// A web pane's web view, on `makeWebPane()`: a plain `WKWebView`, so a file dropped on
    /// it reaches the site, as a screenshot dropped on a GitHub comment box should, where a
    /// folder's page, a `DropAwareWebView`, opens a dropped file in Metabrowser. Its zoom is
    /// its own: it starts at 100%, never at the pages' remembered zoom, and is never saved.
    public static func makeWebPaneView(isInspectable: Bool) -> WKWebView {
        let webView = WKWebView(frame: .zero, configuration: makeWebPane())
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

/// Where every web pane keeps what its sites store: their sign-in cookies, local storage,
/// and cache, as one browser profile does.
///
/// One persistent `WKWebsiteDataStore`, named by `identifier`, serves the pane in every
/// window and tab, for every site (`WebSite.known`), so signing in to a site once holds in
/// all of them, and WebKit keeps it on disk, under
/// `~/Library/WebKit/<bundle identifier>/WebsiteDataStore/`, so it holds after a relaunch.
/// Each build variant has its own bundle identifier and so its own store. WebKit keeps each
/// site's cookies and storage apart within it, by site, as in a browser.
///
/// It is a store of its own, not the default one the folders' pages use, so a page a
/// folder's server serves never shares a cookie jar with a site, and clearing it
/// (Metabrowser > Clear Website Data…) signs you out of a site, or of all of them, without
/// touching Metabrowser's own preferences or any page's local storage.
public enum WebDataStore {
    /// Fixed for the life of the app: a new identifier is a new, empty store, which would
    /// sign everyone out and leave the old one on disk. It is the identifier the GitHub
    /// popover's store had before the store served every site (mb-730z), so that sign-in
    /// holds.
    public static let identifier = UUID(uuidString: "5DE648DD-D5B9-4F54-8403-7DAF088E158C")!

    /// The one store, made once and kept, so every pane's web view holds the same instance.
    public static let shared = WKWebsiteDataStore(forIdentifier: identifier)

    /// The sites that have stored something, by the name WebKit gives each record, its
    /// registrable domain, such as `github.com`, sorted.
    public static func sites() async -> [String] {
        let records = await shared.dataRecords(ofTypes: WKWebsiteDataStore.allWebsiteDataTypes())
        return Set(records.map(\.displayName)).sorted()
    }

    /// Removes what the sites in `sites` stored, by `sites()`'s names, or, given nil,
    /// everything, which signs you out of each.
    public static func clear(_ sites: Set<String>? = nil) async {
        let types = WKWebsiteDataStore.allWebsiteDataTypes()
        guard let sites else {
            return await shared.removeData(ofTypes: types, modifiedSince: .distantPast)
        }
        let records = await shared.dataRecords(ofTypes: types).filter { sites.contains($0.displayName) }
        await shared.removeData(ofTypes: types, for: records)
    }
}
