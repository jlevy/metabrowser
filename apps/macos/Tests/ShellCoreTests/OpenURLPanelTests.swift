import Foundation
import Testing
@testable import ShellCore

nonisolated private let repository = URL(string: "https://github.com/jlevy/metabrowser")!
nonisolated private let pullRequest = URL(string: "https://github.com/jlevy/metabrowser/pull/539")!
nonisolated private let plan = PresentPlan(kind: .pullRequest, repository: repository, link: pullRequest)
nonisolated private let metab = "metab 0.13.0 at /opt/metab"

/// What File > Open URL… hands to `metab`: only a full GitHub URL that `GitHubLink`, the
/// check every link sent to the app passes, accepts.
@Suite struct OpenURLEntryTests {
    /// Each kind of link `metab` opens, as typed or pasted, is the link given to `metab`,
    /// unchanged but for the white space around it.
    @Test(arguments: [
        "https://github.com/jlevy/metabrowser",
        "https://github.com/jlevy/metabrowser/pull/539",
        "https://github.com/jlevy/metabrowser/pull/539/files",
        "https://github.com/jlevy/metabrowser/tree/main/docs",
        "https://github.com/jlevy/metabrowser/blob/claude/app-open-urls/docs/macos-app.md",
        "https://github.com/jlevy/metabrowser/commit/dcf2bcfa8",
        "https://raw.githubusercontent.com/jlevy/metabrowser/main/README.md",
        "https://www.github.com/jlevy/metabrowser",
        "HTTPS://GitHub.com/jlevy/metabrowser",
        "https://github.com:443/jlevy/metabrowser",
        "https://github.com/octo/demo/blob/main/README.md?plain=1#L3",
    ])
    func aFullGitHubURLIsTheLinkGivenToMetab(_ text: String) throws {
        for typed in [text, "  \(text)\n", "\t\(text) "] {
            let link = try OpenURLEntry.link(typed).get()
            #expect(link.absoluteString == text)
            #expect(GitHubLink.accepts(link))
        }
    }

    /// Anything else is said in the panel and never reaches `metab`, which would read a
    /// shorthand as a local path.
    @Test(arguments: [
        ("", OpenURLEntry.Problem.empty),
        (" \n\t", .empty),
        ("jlevy/metabrowser", .notAFullURL),
        ("github.com/jlevy/metabrowser", .notAFullURL),
        ("git@github.com:jlevy/metabrowser.git", .notAFullURL),
        ("~/src/metabrowser", .notAFullURL),
        ("http://github.com/jlevy/metabrowser", .notHTTPS),
        ("ssh://git@github.com/jlevy/metabrowser", .notHTTPS),
        ("file:///tmp/metabrowser", .notHTTPS),
        ("https://user:secret@github.com/jlevy/metabrowser", .credentials),
        ("https://ghp_token@github.com/jlevy/metabrowser", .credentials),
        ("https://github.com:8443/jlevy/metabrowser", .port),
        ("https://github.com:/jlevy/metabrowser", .port),
        ("https://gitlab.com/jlevy/metabrowser", .notGitHub),
        ("https://gist.github.com/jlevy/0123", .notGitHub),
        ("https://github.com.evil.example/jlevy/metabrowser", .notGitHub),
        ("https://github.com%2eevil.example/jlevy/metabrowser", .notGitHub),
        ("https://[::1]/jlevy/metabrowser", .notGitHub),
        ("https://github.com/jlevy/meta browser", .notAURL),
        ("https://github.com/octo/demo/blob/main/a b.md", .notAURL),
    ])
    func anythingElseIsSaidAndNotSent(_ text: String, _ problem: OpenURLEntry.Problem) {
        #expect(OpenURLEntry.link(text) == .failure(problem))
    }

    @Test func aLinkPastTheLimitIsTooLong() {
        let long = "https://github.com/octo/demo/blob/main/" + String(repeating: "a", count: GitHubLink.maximumLength)
        #expect(OpenURLEntry.link(long) == .failure(.tooLong))
    }

    /// Every problem has words of its own, which name no option of the command line.
    @Test func everyProblemSaysSomethingOfItsOwn() {
        let all: [OpenURLEntry.Problem] = [.empty, .tooLong, .notAFullURL, .notHTTPS, .credentials, .port, .notGitHub, .notAURL]
        #expect(Set(all.map(\.message)).count == all.count)
        for problem in all {
            #expect(!problem.message.contains("--"))
        }
    }
}

/// The panel's states: what Open, an edit, `metab`'s answer, and Cancel do.
@Suite struct OpenURLPanelTests {
    /// A panel asking `metab` about `text`, which `link` is.
    private func checking(_ text: String, link: URL = pullRequest) -> OpenURLPanel {
        var panel = OpenURLPanel()
        panel.edit(text)
        let opened = panel.open()
        #expect(opened == link)
        return panel
    }

    @Test func openWaitsForText() {
        var panel = OpenURLPanel()
        #expect(!panel.canOpen)
        let opened = panel.open()
        #expect(opened == nil)
        panel.edit("   ")
        #expect(!panel.canOpen)
        panel.edit("https://github.com/jlevy/metabrowser")
        #expect(panel.canOpen)
    }

    /// A shorthand is not sent: the panel says why, stays open, and the next edit clears it.
    @Test func textThatIsNotALinkIsSaidUnderTheField() {
        var panel = OpenURLPanel()
        panel.edit("jlevy/metabrowser")
        let opened = panel.open()
        #expect(opened == nil)
        #expect(panel.message == OpenURLEntry.Problem.notAFullURL.message)
        #expect(panel.phase == .editing)
        #expect(panel.canOpen)
        panel.edit("https://github.com/jlevy/metabrowser")
        #expect(panel.message == nil)
    }

    /// Open sends the link once: a second press while `metab` is asked does nothing.
    @Test func openSendsTheLinkOnce() {
        var panel = checking("  \(pullRequest.absoluteString)\n")
        #expect(panel.phase == .checking(pullRequest))
        #expect(panel.isChecking)
        #expect(!panel.canOpen)
        let openedAgain = panel.open()
        #expect(openedAgain == nil)
    }

    /// A plan closes the panel and is opened; nothing changes the panel after that.
    @Test func aPlanClosesThePanel() {
        var panel = checking(pullRequest.absoluteString)
        let opens = panel.answered(.plan(plan), for: pullRequest, metab: metab)
        #expect(opens == plan)
        #expect(panel.phase == .closed)
        panel.edit("https://github.com/jlevy/tbd")
        #expect(panel.text == pullRequest.absoluteString)
        let opened = panel.open()
        #expect(opened == nil)
        let opensLate = panel.answered(.plan(plan), for: pullRequest, metab: metab)
        #expect(opensLate == nil)
    }

    /// `metab`'s refusal is said in its own words, and the panel stays open with the text.
    @Test func aRefusalIsSaidAndThePanelStaysOpen() throws {
        let issues = "https://github.com/jlevy/metabrowser/issues/1"
        let link = try #require(URL(string: issues))
        var panel = checking(issues, link: link)
        let refusal = PresentRefusal(
            code: "unsupported_github_url",
            message: "GitHub issues pages are not opened; open the repository at https://github.com/jlevy/metabrowser")
        let opens = panel.answered(.refused(refusal), for: link, metab: metab)
        #expect(opens == nil)
        #expect(panel.message == refusal.message)
        #expect(panel.phase == .editing)
        #expect(panel.text == issues)
        #expect(panel.canOpen)
    }

    @Test func aLongRefusalIsShortened() {
        var panel = checking(pullRequest.absoluteString)
        let long = String(repeating: "x", count: PresentAnswer.shownLineLength * 2)
        _ = panel.answered(.refused(PresentRefusal(code: "c", message: long)), for: pullRequest, metab: metab)
        #expect(panel.message?.count == PresentAnswer.shownLineLength)
    }

    /// An answer the app cannot read names the `metab` and the reason, and never its
    /// output, which can hold a traceback or JSON.
    @Test func anUnreadableAnswerNamesMetabAndNotItsOutput() throws {
        var panel = checking(pullRequest.absoluteString)
        let answer = PresentAnswer.unreadable(
            reason: "printed no answer (exit status 1)",
            output: ["Traceback (most recent call last):", #"{"kind": "#])
        let opens = panel.answered(answer, for: pullRequest, metab: metab)
        #expect(opens == nil)
        let message = try #require(panel.message)
        #expect(message.contains(metab))
        #expect(message.contains("printed no answer (exit status 1)"))
        #expect(!message.contains("Traceback"))
        #expect(!message.contains("{"))
        #expect(panel.phase == .editing)
    }

    /// An edit while `metab` is asked drops its answer: the text it answered about is gone.
    @Test func anEditDropsTheAnswerAwaited() {
        var panel = checking(pullRequest.absoluteString)
        panel.edit("https://github.com/jlevy/metabrowser/pull/540")
        #expect(panel.phase == .editing)
        let opensLate = panel.answered(.plan(plan), for: pullRequest, metab: metab)
        #expect(opensLate == nil)
        #expect(panel.phase == .editing)
        #expect(panel.message == nil)
    }

    @Test func cancelDropsTheAnswerAwaited() {
        var panel = checking(pullRequest.absoluteString)
        panel.cancel()
        let opensLate = panel.answered(.plan(plan), for: pullRequest, metab: metab)
        #expect(opensLate == nil)
        #expect(panel.phase == .closed)
        let opened = panel.open()
        #expect(opened == nil)
    }

    /// With no `metab` to ask, the link goes to the link queue, which waits for one.
    @Test func aLinkBeingCheckedCanBeHandedOn() {
        var panel = checking(pullRequest.absoluteString)
        let handed = panel.handOff()
        #expect(handed == pullRequest)
        #expect(panel.phase == .closed)
        let handedAgain = panel.handOff()
        #expect(handedAgain == nil)
        var editing = OpenURLPanel()
        editing.edit(pullRequest.absoluteString)
        let editingHanded = editing.handOff()
        #expect(editingHanded == nil)
    }
}
