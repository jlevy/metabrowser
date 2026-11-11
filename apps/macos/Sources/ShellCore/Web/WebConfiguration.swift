import WebKit

/// The configuration every folder window's web view is built from.
public enum WebConfiguration {
    /// Persistent cookies and local storage, since Metabrowser keeps its preferences in
    /// host-only cookies that every folder's server shares across ports, element full
    /// screen, and the rules in `restrict(_:)`.
    public static func make() -> WKWebViewConfiguration {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .default()
        configuration.preferences.isElementFullscreenEnabled = true
        restrict(configuration)
        return configuration
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
