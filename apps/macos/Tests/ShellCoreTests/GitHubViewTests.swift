import CoreGraphics
import Foundation
import Testing
@testable import ShellCore

@Suite struct GitHubViewTogglePageTests {
    @Test func theTogglesPagesOnGitHubAreShown() {
        for href in [
            "https://github.com/octo/demo/blob/main/docs/guide.md",
            "https://github.com/octo/demo/tree/0123456789abcdef0123456789abcdef01234567/docs",
            "https://github.com/octo/demo/blob/main/docs/a%20b/%E9%9B%AA%20(1).md",
            "https://GitHub.com/octo/demo/tree/main",
            "https://github.com:443/octo/demo/tree/main",
        ] {
            #expect(GitHubView.togglePage(href)?.absoluteString == href, "\(href)")
        }
    }

    /// Only github.com itself: the toggle writes nothing else, so a marked link anywhere
    /// else shows nothing in the GitHub view.
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
            #expect(GitHubView.togglePage(href) == nil, "\(href.prefix(80))")
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

    @Test func subframesAndDownloadsAreThePagesOwn() {
        let other = url("https://viewscreen.example.com/render")
        #expect(GitHubViewPolicy.decide(other, isMainFrame: false, byUser: false) == .allow)
        #expect(GitHubViewPolicy.decide(other, isMainFrame: true, byUser: true, shouldDownload: true) == .download)
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

@Suite struct GitHubViewStateTests {
    private let readme = URL(string: "https://github.com/octo/demo/blob/main/README.md")!
    private let guide = URL(string: "https://github.com/octo/demo/blob/main/docs/guide.md")!

    @Test func everyWindowOpensInTheMetabrowserView() {
        let state = GitHubViewState()
        #expect(!state.showsGitHub && !state.hasGitHubView && state.openedFor == nil)
        #expect(state.toggleTitle == "Show GitHub View")
    }

    @Test func theFirstChoiceLoadsTheItemsPage() {
        var state = GitHubViewState()
        #expect(state.showGitHub(for: readme) == readme)
        #expect(state.showsGitHub && state.hasGitHubView)
        #expect(state.toggleTitle == "Show Metabrowser View")
    }

    /// Back to Metabrowser and to GitHub again, for the same item: the GitHub view shows as
    /// it was left, wherever the user went on github.com, and keeps its history.
    @Test func switchingBackAndForthKeepsBothViews() {
        var state = GitHubViewState()
        _ = state.showGitHub(for: readme)
        state.showMetabrowser()
        #expect(!state.showsGitHub && state.hasGitHubView)
        #expect(state.showGitHub(for: readme) == nil)
        #expect(state.showsGitHub)
    }

    @Test func anotherItemLoadsItsPageInTheSameView() {
        var state = GitHubViewState()
        _ = state.showGitHub(for: readme)
        state.showMetabrowser()
        #expect(state.showGitHub(for: guide) == guide)
        #expect(state.openedFor == guide)
        state.showMetabrowser()
        #expect(state.showGitHub(for: readme) == readme)
    }

    @Test func aDiscardedTabGivesUpItsGitHubViewAndShowsItsPage() {
        var state = GitHubViewState()
        _ = state.showGitHub(for: readme)
        state.discard()
        #expect(!state.showsGitHub && !state.hasGitHubView)
        #expect(state.showGitHub(for: readme) == readme)
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

@Suite struct ViewToggleTests {
    private let aspectRatio = AppIconMark.ink.width / AppIconMark.ink.height

    /// The marks are the view header's own: the stylesheet masks the same SVG.
    @Test func theMarksAreTheViewHeadersOwn() throws {
        let repository = URL(filePath: #filePath).deletingLastPathComponent().deletingLastPathComponent()
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        let css = try String(
            contentsOf: repository.appending(path: "src/metabrowser/static/styles.css"), encoding: .utf8)
        for svg in [ViewToggleMarks.github, ViewToggleMarks.metabrowser] {
            let encoded = svg.replacingOccurrences(of: "<", with: "%3C").replacingOccurrences(of: ">", with: "%3E")
            #expect(css.contains("url(\"data:image/svg+xml,\(encoded)\")"), "\(svg.prefix(80))")
        }
    }

    @Test func theToggleIsTheHeadersSizeInsetAsTheHeaderInsetsIt() {
        let layout = ViewToggleLayout(width: 800, markAspectRatio: aspectRatio)
        // Two 28 by 20 segments in a 1-point border: 58 by 22, 24 points from the edge.
        #expect(layout.toggle.size == CGSize(width: 58, height: 22))
        #expect(layout.toggle.maxX == CGFloat(800 - 24))
        // Centered in the 28-point bar.
        #expect(ViewToggleLayout.barHeight == 28)
        #expect(layout.toggle.minY == 3 && layout.toggle.maxY == 25)
        #expect(layout.metabrowser.size == CGSize(width: 28, height: 20))
        #expect(layout.github.size == CGSize(width: 28, height: 20))
        #expect(layout.metabrowser.minX == layout.toggle.minX + 1 && layout.github.minX == layout.metabrowser.maxX)
        #expect(layout.toggle.contains(layout.metabrowser) && layout.toggle.contains(layout.github))
    }

    @Test func theMarksAreCenteredInTheirSegmentsOnWholePoints() {
        let layout = ViewToggleLayout(width: 800, markAspectRatio: aspectRatio)
        #expect(layout.githubMark.size == CGSize(width: 14, height: 14))
        #expect(layout.metabrowser.contains(layout.metabrowserMark))
        #expect(layout.github.contains(layout.githubMark))
        // The Metabrowser mark fills the 16-point width of its box, as `contain` does.
        #expect(layout.metabrowserMark.width == 16)
        #expect(abs(layout.metabrowserMark.height - 16 / aspectRatio) < 0.001)
        for mark in [layout.metabrowserMark, layout.githubMark] {
            #expect(mark.minX == mark.minX.rounded() && mark.minY == mark.minY.rounded())
        }
    }

    @Test func theLabelTakesTheRestUpToAGapBeforeTheToggle() {
        let layout = ViewToggleLayout(width: 800, markAspectRatio: aspectRatio)
        #expect(layout.label.minX == 24)
        #expect(layout.label.maxX == layout.toggle.minX - 12)
        #expect(layout.label.height == ViewToggleLayout.barHeight)
        // A window too narrow for any label leaves it none, never a negative width.
        #expect(ViewToggleLayout(width: 100, markAspectRatio: aspectRatio).label.width == 0)
    }

    @Test func rightToLeftMirrorsTheBar() {
        let ltr = ViewToggleLayout(width: 800, markAspectRatio: aspectRatio)
        let rtl = ViewToggleLayout(width: 800, markAspectRatio: aspectRatio, rightToLeft: true)
        #expect(rtl.toggle.minX == 24)
        #expect(rtl.toggle.size == ltr.toggle.size)
        // The Metabrowser segment leads, on the right.
        #expect(rtl.metabrowser.minX > rtl.github.minX)
        #expect(rtl.label.minX == rtl.toggle.maxX + 12 && rtl.label.width == ltr.label.width)
    }
}
