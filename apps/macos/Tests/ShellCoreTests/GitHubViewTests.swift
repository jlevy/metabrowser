import CoreGraphics
import Foundation
import Testing
@testable import ShellCore

@Suite struct GitHubViewPageTests {
    @Test func theButtonsPagesOnGitHubAreShown() {
        for href in [
            "https://github.com/octo/demo/blob/main/docs/guide.md",
            "https://github.com/octo/demo/tree/0123456789abcdef0123456789abcdef01234567/docs",
            "https://github.com/octo/demo/blob/main/docs/a%20b/%E9%9B%AA%20(1).md",
            "https://github.com/octo/demo/pull/12", "https://github.com/octo/demo/commit/0123456",
            "https://GitHub.com/octo/demo/tree/main",
            "https://github.com:443/octo/demo/tree/main",
        ] {
            #expect(GitHubView.page(href)?.absoluteString == href, "\(href)")
        }
    }

    /// Only github.com itself: the button names nothing else, so a marked link anywhere
    /// else opens no popover.
    @Test func anythingElseIsIgnored() {
        for href in [
            "", "about:blank", "javascript:alert(1)", "http://github.com/octo/demo",
            "https://www.github.com/octo/demo", "https://gist.github.com/octo/1",
            "https://raw.githubusercontent.com/octo/demo/main/a.md", "https://github.io/octo",
            "https://github.com.example.com/octo/demo", "https://example.com/?u=https://github.com/",
            "https://user@github.com/octo/demo", "https://github.com:8443/octo/demo",
            "https://%67ithub.com/octo/demo", "file:///tmp/a.md",
            "https://github.com/" + String(repeating: "a", count: GitHubLink.maximumLength),
        ] {
            #expect(GitHubView.page(href) == nil, "\(href.prefix(80))")
        }
    }
}

@Suite struct GitHubViewLocationTests {
    private func location(_ text: String) -> String { GitHubView.location(URL(string: text)) }

    @Test func itIsTheHostAndPathWithoutTheSchemeQueryOrFragment() {
        #expect(location("https://github.com/octo/demo/blob/main/README.md?plain=1#L3")
            == "github.com/octo/demo/blob/main/README.md")
        #expect(location("https://github.com/octo/demo/tree/main/docs/") == "github.com/octo/demo/tree/main/docs")
        #expect(location("https://github.com/") == "github.com")
        #expect(location("https://GitHub.com/login") == "github.com/login")
    }

    @Test func itDecodesThePathForReading() {
        #expect(location("https://github.com/octo/demo/blob/main/a%20b/%E9%9B%AA%20(1).md")
            == "github.com/octo/demo/blob/main/a b/雪 (1).md")
    }

    /// A line break or a bidirectional override in a decoded path could break the line or
    /// reorder what it says, so such a path stays encoded.
    @Test func aPathThatWouldBreakOrReorderTheLineStaysEncoded() {
        #expect(location("https://github.com/octo/demo/blob/main/a%0Ab.md") == "github.com/octo/demo/blob/main/a%0Ab.md")
        #expect(location("https://github.com/octo/demo/blob/main/%E2%80%AEdm.txt")
            == "github.com/octo/demo/blob/main/%E2%80%AEdm.txt")
    }

    @Test func noPageNamesNothing() {
        #expect(GitHubView.location(nil) == "")
        #expect(location("about:blank") == "")
    }
}

@Suite struct GitHubViewPolicyTests {
    private func url(_ text: String) -> URL { URL(string: text)! }

    @Test func gitHubsOwnDomainsStayInTheView() {
        for text in [
            "https://github.com/login", "https://github.com/sessions/two-factor", "https://gist.github.com/octo/1",
            "https://raw.githubusercontent.com/octo/demo/main/a.md", "https://avatars.githubusercontent.com/u/1",
            "https://github.githubassets.com/assets/app.js", "https://GITHUB.COM/octo", "https://github.com:443/octo",
        ] {
            #expect(GitHubViewPolicy.staysInView(url(text)), "\(text)")
        }
    }

    @Test func nothingElseDoes() {
        for text in [
            "http://github.com/login", "https://octo.github.io/demo", "https://evilgithub.com/",
            "https://github.com.example.com/", "https://example.com/github.com", "https://github.com:8443/",
            "https://user@github.com/", "https://accounts.google.com/", "mailto:octo@github.com",
        ] {
            #expect(!GitHubViewPolicy.staysInView(url(text)), "\(text)")
        }
    }

    @Test func gitHubPagesLoadInPlace() {
        let page = url("https://github.com/octo/demo/blob/main/a.md")
        #expect(GitHubViewPolicy.decide(page, isMainFrame: true, byUser: true) == .allow)
        // A redirect or a page's own script on github.com, such as signing in.
        #expect(GitHubViewPolicy.decide(url("https://github.com/session"), isMainFrame: true, byUser: false) == .allow)
        #expect(GitHubViewPolicy.decide(url("about:blank"), isMainFrame: true, byUser: false) == .allow)
    }

    @Test func anotherSiteOpensInTheDefaultBrowserOnlyWhenTheUserAsks() {
        let other = url("https://example.com/docs")
        #expect(GitHubViewPolicy.decide(other, isMainFrame: true, byUser: true) == .openExternally(other))
        #expect(GitHubViewPolicy.decide(other, isMainFrame: true, byUser: false) == .cancel)
        let mail = url("mailto:octo@example.com")
        #expect(GitHubViewPolicy.decide(mail, isMainFrame: true, byUser: true) == .openExternally(mail))
        #expect(GitHubViewPolicy.decide(url("file:///etc/hosts"), isMainFrame: true, byUser: true) == .cancel)
        #expect(GitHubViewPolicy.decide(url("javascript:alert(1)"), isMainFrame: true, byUser: true) == .cancel)
        #expect(GitHubViewPolicy.decide(nil, isMainFrame: true, byUser: true) == .cancel)
    }

    @Test func commandClickOpensAGitHubPageInTheDefaultBrowser() {
        let page = url("https://github.com/octo/demo/pulls")
        #expect(GitHubViewPolicy.decide(page, isMainFrame: true, byUser: true, wantsNewWindow: true) == .openExternally(page))
    }

    @Test func subframesAreThePagesOwn() {
        let other = url("https://viewscreen.example.com/render")
        #expect(GitHubViewPolicy.decide(other, isMainFrame: false, byUser: false) == .allow)
    }

    /// A download goes to the default browser, and only when the user asked for it: never
    /// a save panel over the popover.
    @Test func aDownloadOpensInTheDefaultBrowserWhenTheUserAsks() {
        let file = url("https://github.com/octo/demo/raw/main/a.zip")
        #expect(GitHubViewPolicy.decide(file, isMainFrame: true, byUser: true, shouldDownload: true) == .openExternally(file))
        #expect(GitHubViewPolicy.decide(file, isMainFrame: true, byUser: false, shouldDownload: true) == .cancel)
        #expect(GitHubViewPolicy.decide(url("blob:https://github.com/1"), isMainFrame: true, byUser: true, shouldDownload: true)
            == .cancel)
    }

    @Test func aResponseShowsOrItsDownloadFromGitHubOpensInTheBrowser() {
        let zip = url("https://codeload.github.com/octo/demo/zip/refs/heads/main")
        #expect(GitHubViewPolicy.decideResponse(zip, .show) == .allow)
        #expect(GitHubViewPolicy.decideResponse(zip, .download) == .openExternally(zip))
        #expect(GitHubViewPolicy.decideResponse(url("https://example.com/a.zip"), .download) == .cancel)
        #expect(GitHubViewPolicy.decideResponse(nil, .download) == .cancel)
    }

    @Test func aNewWindowForGitHubLoadsHereAndOtherwiseOpensInTheBrowser() {
        let page = url("https://github.com/octo/demo")
        let other = url("https://example.com/")
        #expect(GitHubViewPolicy.decideNewWindow(page) == .allow)
        #expect(GitHubViewPolicy.decideNewWindow(other) == .openExternally(other))
        #expect(GitHubViewPolicy.decideNewWindow(url("file:///etc/hosts")) == .cancel)
        #expect(GitHubViewPolicy.decideNewWindow(nil) == .cancel)
    }
}

@Suite struct GitHubPopoverStateTests {
    private let readme = URL(string: "https://github.com/octo/demo/blob/main/README.md")!
    private let guide = URL(string: "https://github.com/octo/demo/blob/main/docs/guide.md")!

    @Test func theFirstOpeningLoadsTheItemsPage() {
        var state = GitHubPopoverState()
        #expect(state.openedFor == nil)
        #expect(state.open(readme) == readme)
        #expect(state.openedFor == readme)
    }

    /// Opened again for the same item, it shows as it was left, with no load.
    @Test func theSameItemShowsItAsItWasLeft() {
        var state = GitHubPopoverState()
        _ = state.open(readme)
        #expect(state.open(readme) == nil)
    }

    @Test func anotherItemLoadsItsPage() {
        var state = GitHubPopoverState()
        _ = state.open(readme)
        #expect(state.open(guide) == guide)
        #expect(state.open(readme) == readme)
    }

    @Test func afterItsWebViewIsLetGoItLoadsAgain() {
        var state = GitHubPopoverState()
        _ = state.open(readme)
        state.discard()
        #expect(state.openedFor == nil)
        #expect(state.open(readme) == readme)
    }
}

@Suite struct GitHubPopoverLayoutTests {
    private let screen = CGSize(width: 1728, height: 1079)

    @Test func itTakesMostOfALargeWindow() {
        let size = GitHubPopoverLayout.contentSize(window: CGSize(width: 1400, height: 900), screen: screen)
        #expect(size == CGSize(width: 1260, height: 765))
    }

    @Test func itIsNeverSmallerThanTheMinimum() {
        let size = GitHubPopoverLayout.contentSize(window: CGSize(width: 600, height: 400), screen: screen)
        #expect(size == GitHubPopoverLayout.minimumSize)
    }

    /// The screen wins over the minimum, less a margin for the popover's border and arrow.
    @Test func itStaysOnASmallScreen() {
        let size = GitHubPopoverLayout.contentSize(
            window: CGSize(width: 700, height: 500), screen: CGSize(width: 760, height: 540))
        #expect(size == CGSize(width: 760 - GitHubPopoverLayout.screenMargin, height: 540 - GitHubPopoverLayout.screenMargin))
        #expect(GitHubPopoverLayout.contentSize(window: CGSize(width: 1400, height: 900), screen: nil)
            == CGSize(width: 1260, height: 765))
    }

    private let bounds = CGRect(x: 0, y: 0, width: 1000, height: 600)
    private let button = CGRect(x: 880, y: 12, width: 100, height: 24)

    /// In a flipped web view the button's CSS rectangle is its rectangle in points at
    /// 100%; unflipped, it is measured up from the bottom.
    @Test func theAnchorIsTheButtonInTheWebView() {
        let flipped = GitHubPopoverLayout.anchor(button, viewportWidth: 1000, in: bounds, flipped: true)
        #expect(flipped == button)
        let unflipped = GitHubPopoverLayout.anchor(button, viewportWidth: 1000, in: bounds, flipped: false)
        #expect(unflipped == CGRect(x: 880, y: 600 - 12 - 24, width: 100, height: 24))
    }

    /// At 200% page zoom the viewport is half the web view's width in CSS pixels.
    @Test func itFollowsThePagesZoom() {
        let zoomed = GitHubPopoverLayout.anchor(
            CGRect(x: 440, y: 6, width: 50, height: 12), viewportWidth: 500, in: bounds, flipped: true)
        #expect(zoomed == CGRect(x: 880, y: 12, width: 100, height: 24))
    }

    @Test func itIsClippedToTheWebView() {
        let partly = GitHubPopoverLayout.anchor(
            CGRect(x: 950, y: -10, width: 100, height: 24), viewportWidth: 1000, in: bounds, flipped: true)
        #expect(partly == CGRect(x: 950, y: 0, width: 50, height: 14))
    }

    /// A button scrolled out of sight, or of no size, leaves the popover pointing at the web
    /// view's top right corner, where the button sits.
    @Test func aButtonOutOfSightPointsAtTheTopRightCorner() {
        let gone = CGRect(x: 880, y: -100, width: 100, height: 24)
        #expect(GitHubPopoverLayout.anchor(gone, viewportWidth: 1000, in: bounds, flipped: true)
            == CGRect(x: 999, y: 0, width: 1, height: 1))
        #expect(GitHubPopoverLayout.anchor(gone, viewportWidth: 1000, in: bounds, flipped: false)
            == CGRect(x: 999, y: 599, width: 1, height: 1))
        #expect(GitHubPopoverLayout.anchor(.zero, viewportWidth: 0, in: bounds, flipped: true)
            == CGRect(x: 999, y: 0, width: 1, height: 1))
    }
}

@Suite struct GitHubViewRequestTests {
    private let href = "https://github.com/octo/demo/blob/main/README.md"

    @Test func aClickCarriesThePageAndWhereTheButtonIs() throws {
        let request = try #require(GitHubViewRequests.Request([
            "href": href, "rect": [880.5, 12, 100, 24] as [Any], "viewportWidth": 1000,
        ] as [String: Any]))
        #expect(request.page.absoluteString == href)
        #expect(request.link == CGRect(x: 880.5, y: 12, width: 100, height: 24))
        #expect(request.viewportWidth == 1000)
    }

    @Test func aMessageOfAnotherShapeIsDropped() {
        let rect: [Any] = [880, 12, 100, 24]
        for body: Any in [
            href, [href], ["href": href] as [String: Any],
            ["href": href, "rect": rect] as [String: Any],
            ["href": href, "rect": [880, 12, 100] as [Any], "viewportWidth": 1000] as [String: Any],
            ["href": href, "rect": [880, 12, -1, 24] as [Any], "viewportWidth": 1000] as [String: Any],
            ["href": href, "rect": [Double.nan, 12, 100, 24] as [Any], "viewportWidth": 1000] as [String: Any],
            ["href": href, "rect": ["880", 12, 100, 24] as [Any], "viewportWidth": 1000] as [String: Any],
            ["href": href, "rect": rect, "viewportWidth": 0] as [String: Any],
            ["href": href, "rect": rect, "viewportWidth": Double.infinity] as [String: Any],
            ["href": "https://example.com/", "rect": rect, "viewportWidth": 1000] as [String: Any],
            ["href": 1, "rect": rect, "viewportWidth": 1000] as [String: Any],
        ] {
            #expect(GitHubViewRequests.Request(body) == nil, "\(body)")
        }
    }
}

@Suite struct AppDocumentTests {
    private let policy = NavigationPolicy(origin: URL(string: "http://127.0.0.1:8411")!)

    @Test func onlyTheServersOwnMainFrame() {
        #expect(policy.isAppDocument(scheme: "http", host: "127.0.0.1", port: 8411, isMainFrame: true))
        #expect(!policy.isAppDocument(scheme: "http", host: "127.0.0.1", port: 8411, isMainFrame: false))
        #expect(!policy.isAppDocument(scheme: "http", host: "127.0.0.1", port: 8412, isMainFrame: true))
        #expect(!policy.isAppDocument(scheme: "http", host: "localhost", port: 8411, isMainFrame: true))
        // An opaque origin, such as a `/raw` file's under its CSP sandbox.
        #expect(!policy.isAppDocument(scheme: "", host: "", port: 0, isMainFrame: true))
        #expect(!NavigationPolicy().isAppDocument(scheme: "http", host: "127.0.0.1", port: 8411, isMainFrame: true))
    }
}
