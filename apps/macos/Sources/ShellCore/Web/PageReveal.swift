/// Which of a window's WebKit navigations may still change what the window shows.
///
/// A window covers its page with the status view until the navigation its `load`
/// submitted commits, and shows that navigation's provisional failure in place of the
/// page. Server state that replaces the page (the server starting, failing, or waiting,
/// a discarded page, a window that gave up after its content process kept dying)
/// supersedes that navigation, and so does a newer load. WebKit still delivers a
/// superseded navigation's commit or failure if it was already on its way, and the window
/// must not let it hide the server's failure and Retry, or replace the server's
/// diagnostic with a page error. So each callback is matched, by identity, against the
/// one navigation that may reveal the page, and a supersede leaves none.
///
/// `PageLoads` covers the loads still waiting to submit; this covers the one submitted.
/// `Navigation` is `WKNavigation` in the app, which hands WebKit's callbacks the object
/// `load` returned. Holding it keeps its address from naming a later navigation.
public struct PageReveal<Navigation: AnyObject> {
    private enum Awaiting {
        case nothing
        /// The window's load: only its commit reveals the page.
        case navigation(Navigation)
        /// The next commit reveals the page: the window's load was cancelled by a
        /// navigation it did not start, such as the page's own, or WebKit named none.
        case nextCommit
    }

    private var awaiting = Awaiting.nothing

    public init() {}

    /// `load` submitted `navigation`: its commit reveals the page, and no earlier
    /// navigation's callback changes the status.
    public mutating func submitted(_ navigation: Navigation?) {
        awaiting = navigation.map(Awaiting.navigation) ?? .nextCommit
    }

    /// Server state replaced the page: no navigation submitted until now may reveal it
    /// or report a failure. True if one was still on its way, which the window then stops.
    @discardableResult
    public mutating func supersede() -> Bool {
        defer { awaiting = .nothing }
        if case .nothing = awaiting { return false }
        return true
    }

    /// The window reloaded after its content process died. The reload reveals the page
    /// in place of a load still on its way; with none, the page was shown, and nothing
    /// reveals it.
    public mutating func reloaded(_ navigation: Navigation?) {
        if case .nothing = awaiting { return }
        submitted(navigation)
    }

    /// Whether `navigation`'s commit reveals the page. It does once, for the window's load.
    public mutating func reveals(onCommit navigation: Navigation?) -> Bool {
        guard isAwaited(navigation) else { return false }
        awaiting = .nothing
        return true
    }

    /// Whether the window shows `navigation`'s provisional failure in place of the page.
    /// A `cancelled` one shows nothing: a cancel of the window's load by another
    /// navigation passes the reveal to the next commit.
    public mutating func reports(failureOf navigation: Navigation?, cancelled: Bool) -> Bool {
        guard isAwaited(navigation) else { return false }
        awaiting = cancelled ? .nextCommit : .nothing
        return !cancelled
    }

    private func isAwaited(_ navigation: Navigation?) -> Bool {
        switch awaiting {
        case .nothing: false
        case .navigation(let awaited): navigation === awaited
        case .nextCommit: true
        }
    }
}
