import Testing
@testable import ShellCore

/// Every asynchronous path that loads a window's next page (readiness attaching the
/// server, a health-gated load) takes a ticket first and loads only if its ticket is still
/// the newest just before it takes the page.
@Suite struct PageLoadsTests {
    private let b = PageAddress.view(of: "b.md")

    /// Replays a window's loads: each `(ticket, label)` completion loads only if
    /// `take(for:)` lets it, and records what it loaded ("entry" for the entry page).
    private func complete(_ order: [Int], on pages: inout PageLoads) -> [String] {
        order.compactMap { ticket in
            switch pages.take(for: ticket) {
            case .superseded: nil
            case .page(let page): page.map(\.reference) ?? "entry"
            }
        }
    }

    /// The server becomes ready (attach), then `show(B)` asks for B before either load
    /// runs. Whichever finishes first, the window loads B, once, and never the entry page.
    @Test(arguments: [false, true])
    func readinessThenAShownPageEndsOnThatPage(showFinishesFirst: Bool) {
        var pages = PageLoads()
        let attached = pages.begin()
        pages.request(b)
        let shown = pages.begin()
        let loaded = complete(showFinishesFirst ? [shown, attached] : [attached, shown], on: &pages)
        #expect(loaded == [b.reference])
    }

    /// The server becomes ready, then the window closes before the load runs: nothing
    /// loads, and the page is kept rather than taken.
    @Test func readinessThenACloseLoadsNothing() {
        var pages = PageLoads(requested: b)
        let attached = pages.begin()
        pages.cancelAll()  // windowWillClose
        #expect(complete([attached], on: &pages) == [])
        #expect(pages.saved(showing: nil) == b)
    }

    @Test func theNewestLoadTakesTheRequestedPageOrTheEntryPage() {
        var pages = PageLoads(requested: b)
        let ticket = pages.begin()
        #expect(complete([ticket], on: &pages) == [b.reference])
        var empty = PageLoads()
        let emptyTicket = empty.begin()
        #expect(complete([emptyTicket], on: &empty) == ["entry"])
    }

    @Test func aPageShownBeforeARestartIsLoadedAfterIt() {
        var pages = PageLoads()
        pages.remember(shown: b)
        let attached = pages.begin()
        #expect(complete([attached], on: &pages) == [b.reference])
    }
}
