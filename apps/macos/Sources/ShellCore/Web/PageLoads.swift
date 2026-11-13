/// A window's next page, and the loads that wait to load it.
///
/// Every load that waits before it loads (readiness attaching the server, which first
/// installs its authorization; a health-gated load) takes a ticket with `begin()`, and
/// asks `take(for:)` just before it loads. Only the newest ticket gets the page: a newer
/// load, a discard, a server change, or a close (`cancelAll()`) supersedes every older
/// one, which then loads nothing and leaves the page for the next. So the page is taken
/// once, by the load that should show it.
public nonisolated struct PageLoads: Equatable, Sendable {
    /// What a load may do when its turn comes.
    public enum Load: Equatable, Sendable {
        /// A newer load or a cancel superseded it: load nothing.
        case superseded
        /// Load this page, or the server's entry page for nil.
        case page(PageAddress?)
    }

    private var next: NextPage
    private var tickets = LoadTickets()

    public init(requested: PageAddress? = nil) {
        next = NextPage(requested: requested)
    }

    public mutating func request(_ page: PageAddress) { next.request(page) }
    public mutating func remember(shown page: PageAddress) { next.remember(shown: page) }
    public func saved(showing current: PageAddress?) -> PageAddress? { next.saved(showing: current) }

    /// A ticket for a load about to wait; it supersedes every earlier one.
    public mutating func begin() -> Int { tickets.begin() }

    public mutating func cancelAll() { tickets.cancelAll() }

    /// For `ticket`'s load, now: superseded, or the page to load, which it takes.
    public mutating func take(for ticket: Int) -> Load {
        tickets.isCurrent(ticket) ? .page(next.take()) : .superseded
    }
}
