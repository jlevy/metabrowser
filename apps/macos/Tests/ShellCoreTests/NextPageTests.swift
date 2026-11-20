import Testing
@testable import ShellCore

@Suite struct NextPageTests {
    private let a = PageAddress.view(of: "a.md")
    private let b = PageAddress.view(of: "b.md")

    /// The defect: a window showed a.md, its server failed, b.md was opened, and Retry
    /// remembered the old view's a.md over the request, so a.md loaded again.
    @Test func aRequestOutlastsTheRestartThatRemembersTheOldPage() {
        var next = NextPage()
        next.request(b)  // opened while the server is down
        next.remember(shown: a)  // Retry: the starting server remembers the old view's page
        #expect(next.take() == b)
    }

    @Test func aRequestIsWhatIsSavedAndWhatADiscardKeeps() {
        var next = NextPage()
        next.request(b)
        // Quitting before Retry saves the request, not the old view's page.
        #expect(next.saved(showing: a) == b)
        // Discarding the tab remembers the old page and keeps the request.
        next.remember(shown: a)
        #expect(next.saved(showing: nil) == b)
        #expect(next.take() == b)
    }

    @Test func withoutARequestTheShownPageComesBack() {
        var next = NextPage()
        next.remember(shown: a)
        #expect(next.saved(showing: nil) == a)
        #expect(next.take() == a)
    }

    @Test func aPageShownNowIsSavedOverOneRememberedBefore() {
        var next = NextPage()
        next.remember(shown: a)
        #expect(next.saved(showing: b) == b)
    }

    @Test func takingALoadForgetsBoth() {
        var next = NextPage()
        next.remember(shown: a)
        next.request(b)
        #expect(next.take() == b)
        #expect(next.take() == nil)
        #expect(next.saved(showing: nil) == nil)
    }

    @Test func aLaterRequestReplacesAnEarlierOne() {
        var next = NextPage()
        next.request(a)
        next.request(b)
        #expect(next.take() == b)
    }
}
