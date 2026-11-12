/// Which of a window's loads that wait (on a health check) may still load.
///
/// Each waiting load takes a ticket, and only the newest ticket's completion loads, so two
/// files opened in a running folder end on the second, and the page the window is to show
/// (`NextPage`) is taken once, not once per completion. A discard, a server change, or a
/// close cancels every waiting load: the page they would load is kept for the next one.
public nonisolated struct LoadTickets: Equatable, Sendable {
    private var newest = 0

    public init() {}

    /// A ticket for a load that is about to wait; it supersedes every earlier one.
    public mutating func begin() -> Int {
        newest += 1
        return newest
    }

    public mutating func cancelAll() {
        newest += 1
    }

    public func isCurrent(_ ticket: Int) -> Bool { ticket == newest }
}
