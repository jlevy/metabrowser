import Testing
@testable import ShellCore

/// A window that loads only after a health check can have several loads waiting at once
/// (two files opened in a running folder, say). Only the newest may load, and it loads
/// the newest page; a discard, a server change, or a close cancels them all.
@Suite struct LoadTicketsTests {
    private let a = PageAddress.view(of: "a.md")
    private let b = PageAddress.view(of: "b.md")

    /// The two opens' checks may finish in either order; the window ends on `b`, and the
    /// page is taken once, so the other completion does not load the entry page.
    @Test(arguments: [false, true])
    func overlappingOpensEndOnTheNewestPage(newestFinishesFirst: Bool) {
        var tickets = LoadTickets()
        var next = NextPage()
        next.request(a)
        let first = tickets.begin()
        next.request(b)
        let second = tickets.begin()
        var loaded: [PageAddress?] = []
        for ticket in newestFinishesFirst ? [second, first] : [first, second] where tickets.isCurrent(ticket) {
            loaded.append(next.take())
        }
        #expect(loaded == [b])
    }

    @Test func aDiscardAServerChangeOrACloseCancelsEveryWaitingLoad() {
        var tickets = LoadTickets()
        let waiting = tickets.begin()
        tickets.cancelAll()
        #expect(!tickets.isCurrent(waiting))
        let after = tickets.begin()
        #expect(tickets.isCurrent(after))
    }
}
