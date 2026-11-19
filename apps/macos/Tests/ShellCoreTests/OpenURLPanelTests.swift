import Foundation
import Testing
@testable import ShellCore

nonisolated private let repository = URL(string: "https://github.com/jlevy/metabrowser")!
nonisolated private let pullRequest = URL(string: "https://github.com/jlevy/metabrowser/pull/539")!
nonisolated private let plan = PresentPlan(kind: .pullRequest, repository: repository, link: pullRequest)
nonisolated private let metab = "metab 0.13.0 at /opt/metab"

/// What File > Open URL… hands to `metab`: only a full GitHub URL that `GitHubLink`, the
/// check every link sent to the app passes, accepts, once text that is plainly one is
/// written in full.
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

    /// Text that is plainly a GitHub URL is written in full, and then is exactly what the
    /// full URL is: the same link, or the same problem. GitHub answers each spelling as it
    /// answers the full one.
    @Test(arguments: [
        ("github.com/jlevy/kpress", "https://github.com/jlevy/kpress"),
        ("GitHub.com/jlevy/kpress", "https://GitHub.com/jlevy/kpress"),
        ("www.github.com/jlevy/kpress", "https://www.github.com/jlevy/kpress"),
        ("github.com/jlevy/metabrowser/pull/539/files", "https://github.com/jlevy/metabrowser/pull/539/files"),
        ("raw.githubusercontent.com/jlevy/metabrowser/main/README.md",
         "https://raw.githubusercontent.com/jlevy/metabrowser/main/README.md"),
        ("github.com", "https://github.com"),
        ("github.com?tab=repositories", "https://github.com?tab=repositories"),
        ("github.com/octo/demo/blob/main/a b.md", "https://github.com/octo/demo/blob/main/a b.md"),
        ("github.com/octo/demo/blob/main/a\\b.md", "https://github.com/octo/demo/blob/main/a\\b.md"),
        ("http://github.com/jlevy/kpress", "https://github.com/jlevy/kpress"),
        ("HTTP://www.GitHub.com/jlevy/kpress", "https://www.GitHub.com/jlevy/kpress"),
        ("http://raw.githubusercontent.com/jlevy/metabrowser/main/README.md",
         "https://raw.githubusercontent.com/jlevy/metabrowser/main/README.md"),
        ("//github.com/jlevy/kpress", "https://github.com/jlevy/kpress"),
        ("  github.com/jlevy/kpress\n", "https://github.com/jlevy/kpress"),
    ])
    func plainlyAGitHubURLIsWrittenInFull(_ text: String, _ full: String) {
        #expect(OpenURLEntry.corrected(text) == full)
        #expect(OpenURLEntry.link(text) == OpenURLEntry.link(full))
    }

    /// The owner's example, 2026-11-19, opens what the full URL opens.
    @Test func theOwnersExampleOpens() throws {
        let link = try OpenURLEntry.link("github.com/jlevy/kpress").get()
        #expect(link.absoluteString == "https://github.com/jlevy/kpress")
        #expect(GitHubLink.accepts(link))
    }

    /// Anything not plainly a GitHub URL is left as it is: another host, a host with a user
    /// name, a password, or a port, an SSH address, a path, and `owner/repo`.
    @Test(arguments: [
        "https://github.com/jlevy/kpress",
        "gitlab.com/jlevy/kpress",
        "gist.github.com/jlevy/0123",
        "github.com.evil.example/jlevy/kpress",
        "evilgithub.com/jlevy/kpress",
        "http://gitlab.com/jlevy/kpress",
        "http://user@github.com/jlevy/kpress",
        "http://github.com:80/jlevy/kpress",
        "ftp://github.com/jlevy/kpress",
        "//gitlab.com/jlevy/kpress",
        "///github.com/jlevy/kpress",
        "user@github.com/jlevy/kpress",
        "user:secret@github.com/jlevy/kpress",
        "github.com:8443/jlevy/kpress",
        "github.com:443/jlevy/kpress",
        "git@github.com:jlevy/kpress.git",
        "https:/github.com/jlevy/kpress",
        "~/src/kpress",
        "/srv/git/kpress",
        "./jlevy/kpress",
        "jlevy",
        "jlevy/kpress",
        "jlevy/kpress/",
        "docs/macos-app.md",
        "src/main.py",
        "jlevy/kpress/pull/1",
        "jlevy/kpress#12",
        "jlevy/.",
        "jlevy/..",
        "jle.vy/kpress",
        "jlevy/kp ress",
    ])
    func anythingElseIsLeftAsItIs(_ text: String) {
        #expect(OpenURLEntry.corrected(text) == text)
    }

    /// The owner's answer of 2026-11-18 (bead `mb-m4mg`), which 2026-11-19 kept: the panel
    /// takes no shorthand. `owner/repo` is refused as a relative path such as
    /// `docs/macos-app.md` is, with the same words, and neither reaches `metab`.
    @Test(arguments: ["jlevy/kpress", "docs/macos-app.md"])
    func aShorthandIsRefusedAsAPathIs(_ text: String) {
        #expect(OpenURLEntry.corrected(text) == text)
        #expect(OpenURLEntry.link(text) == .failure(.notAFullURL))
        var panel = OpenURLPanel()
        panel.edit(text)
        let opened = panel.open()
        #expect(opened == nil)
        #expect(panel.text == text)
        #expect(panel.message == OpenURLEntry.Problem.notAFullURL.message)
    }

    /// Anything else is said in the panel and never reaches `metab`, which would read
    /// text with no scheme as a local path.
    @Test(arguments: [
        ("", OpenURLEntry.Problem.empty),
        (" \n\t", .empty),
        ("gitlab.com/jlevy/metabrowser", .notAFullURL),
        ("gist.github.com/jlevy/0123", .notAFullURL),
        ("user:secret@github.com/jlevy/metabrowser", .notAFullURL),
        ("github.com:8443/jlevy/metabrowser", .notAFullURL),
        ("jlevy/metabrowser/pull/539", .notAFullURL),
        ("git@github.com:jlevy/metabrowser.git", .notAFullURL),
        ("~/src/metabrowser", .notAFullURL),
        ("//gitlab.com/jlevy/metabrowser", .notAFullURL),
        ("http://gitlab.com/jlevy/metabrowser", .notHTTPS),
        ("http://user@github.com/jlevy/metabrowser", .notHTTPS),
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
        ("https://github.com/octo/demo/blob/main/README\u{3164}.md", .character("\u{3164}")),
        ("https://github.com/octo/demo/blob/main/a\u{200B}b.md", .character("\u{200B}")),
        ("https://github.com/octo/demo/blob/main/a\u{00A0}b.md", .character("\u{00A0}")),
        ("https://github.com/octo/demo/blob/main/a\u{202E}b.md", .character("\u{202E}")),
        ("https://github.com/octo/demo/blob/main/README\u{FE0F}.md", .character("\u{FE0F}")),
        ("https://github.com/octo/demo/blob/main/\u{2800}.md", .character("\u{2800}")),
        ("https://github.com/octo/demo/blob/main/a\u{E000}.md", .character("\u{E000}")),
        ("https://github.com/octo/demo/blob/main/a\tb.md", .character("\t")),
        ("https://github.com/octo/demo/blob/main/a\nb.md", .character("\n")),
        ("https://github.com/octo/demo/blob/main/a\u{0085}b.md", .character("\u{0085}")),
        ("https://github.com/octo/demo/blob/main/a\\b.md", .character("\\")),
        ("https://github.com/octo/demo/blob/main/100%.md", .percent),
        ("https://github.com/octo/demo/blob/main/a%zz.md", .percent),
        ("https://github.com/octo/demo/blob/main/a%2", .percent),
        ("github.com/octo/demo/blob/main/a\\b.md", .character("\\")),
        ("jlevy/..", .notAFullURL),
    ])
    func anythingElseIsSaidAndNotSent(_ text: String, _ problem: OpenURLEntry.Problem) {
        #expect(OpenURLEntry.link(text) == .failure(problem))
    }

    /// The path, query, and fragment are sent as a browser sends them, as `metab` reads
    /// them: a space, an ASCII character a URL cannot hold raw, a second `#`, and a
    /// character outside ASCII that shows, percent-encoded as UTF-8, and an escape kept.
    @Test(arguments: [
        ("https://github.com/octo/demo/blob/main/a b.md", "https://github.com/octo/demo/blob/main/a%20b.md"),
        ("https://github.com/jlevy/meta browser", "https://github.com/jlevy/meta%20browser"),
        ("https://github.com/octo/demo/blob/main/a%20b c.md", "https://github.com/octo/demo/blob/main/a%20b%20c.md"),
        ("https://github.com/octo/demo/blob/main/café.md", "https://github.com/octo/demo/blob/main/caf%C3%A9.md"),
        ("https://github.com/octo/demo/blob/main/文档.md", "https://github.com/octo/demo/blob/main/%E6%96%87%E6%A1%A3.md"),
        ("https://github.com/octo/demo/blob/main/❤️.md", "https://github.com/octo/demo/blob/main/%E2%9D%A4%EF%B8%8F.md"),
        ("https://github.com/octo/demo/blob/main/1️⃣.md", "https://github.com/octo/demo/blob/main/1%EF%B8%8F%E2%83%A3.md"),
        (#"https://github.com/octo/demo/blob/main/a"b{c}|d^e`f<g>[1].md"#,
         "https://github.com/octo/demo/blob/main/a%22b%7Bc%7D%7Cd%5Ee%60f%3Cg%3E%5B1%5D.md"),
        ("https://github.com/octo/demo/blob/main/a.md#L1#x", "https://github.com/octo/demo/blob/main/a.md#L1%23x"),
        ("https://github.com/octo/demo/blob/main/a b.md?x=é#frag é",
         "https://github.com/octo/demo/blob/main/a%20b.md?x=%C3%A9#frag%20%C3%A9"),
    ])
    func thePathIsSentAsABrowserSendsIt(_ text: String, _ sent: String) throws {
        let link = try OpenURLEntry.link(text).get()
        #expect(link.absoluteString == sent)
        #expect(GitHubLink.accepts(link))
    }

    @Test func aLinkPastTheLimitIsTooLong() {
        // Within the limit as typed, but not once `https://` is written before it.
        let start = "github.com/octo/demo/blob/main/"
        let bare = start + String(repeating: "a", count: GitHubLink.maximumLength - start.utf8.count)
        #expect(bare.utf8.count == GitHubLink.maximumLength)
        #expect(OpenURLEntry.link(bare) == .failure(.tooLong))
        let long = "https://github.com/octo/demo/blob/main/" + String(repeating: "a", count: GitHubLink.maximumLength)
        #expect(OpenURLEntry.link(long) == .failure(.tooLong))
        // Within the limit as typed, but not once each é is sent as %C3%A9.
        let grown = "https://github.com/octo/demo/blob/main/" + String(repeating: "é", count: GitHubLink.maximumLength / 3)
        #expect(grown.utf8.count <= GitHubLink.maximumLength)
        #expect(OpenURLEntry.link(grown) == .failure(.tooLong))
    }

    /// Every problem has words of its own, which name no option of the command line.
    @Test func everyProblemSaysSomethingOfItsOwn() {
        let all: [OpenURLEntry.Problem] = [
            .empty, .tooLong, .notAFullURL, .notHTTPS, .credentials, .port, .notGitHub,
            .character("\\"), .character("\t"), .character("\u{3164}"), .percent, .notAURL,
        ]
        #expect(Set(all.map(\.message)).count == all.count)
        for problem in all {
            #expect(!problem.message.contains("--"))
        }
    }

    /// A character the panel does not send is named as `metab` names it, with the
    /// escape to write instead when it is outside ASCII.
    @Test func aCharacterIsNamedWithItsEscape() {
        let hidden = OpenURLEntry.Problem.character("\u{3164}").message
        #expect(hidden.contains("U+3164"))
        #expect(hidden.contains("%E3%85%A4"))
        let control = OpenURLEntry.Problem.character("\t").message
        #expect(control.contains("U+0009"))
        #expect(!control.contains("%09"))
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

    /// Text that is not a link is not sent: the panel says why, stays open with the text as
    /// typed, and the next edit clears the reason.
    @Test func textThatIsNotALinkIsSaidUnderTheField() {
        var panel = OpenURLPanel()
        panel.edit(" gitlab.com/jlevy/metabrowser ")
        let opened = panel.open()
        #expect(opened == nil)
        #expect(panel.message == OpenURLEntry.Problem.notAFullURL.message)
        #expect(panel.text == " gitlab.com/jlevy/metabrowser ")
        #expect(panel.phase == .editing)
        #expect(panel.canOpen)
        panel.edit("https://github.com/jlevy/metabrowser")
        #expect(panel.message == nil)
    }

    /// Open writes text that is plainly a GitHub URL in full, says nothing about it, and
    /// asks `metab` about the full URL, which the field now holds.
    @Test(arguments: [
        "github.com/jlevy/metabrowser/pull/539",
        " http://github.com/jlevy/metabrowser/pull/539\n",
        "//github.com/jlevy/metabrowser/pull/539",
    ])
    func openWritesAGitHubURLInFull(_ typed: String) {
        var panel = OpenURLPanel()
        panel.edit(typed)
        let opened = panel.open()
        #expect(opened == pullRequest)
        #expect(panel.text == pullRequest.absoluteString)
        #expect(panel.message == nil)
        #expect(panel.phase == .checking(pullRequest))
    }

    /// The field holds the full URL, so a refusal of it, the panel's or `metab`'s, is about
    /// what the field shows; editing it from there works as any edit does.
    @Test func aRefusalOfACorrectedURLIsAboutWhatTheFieldShows() throws {
        var panel = OpenURLPanel()
        panel.edit("github.com/octo/demo/blob/main/a\\b.md")
        let refused = panel.open()
        #expect(refused == nil)
        #expect(panel.text == "https://github.com/octo/demo/blob/main/a\\b.md")
        #expect(panel.message == OpenURLEntry.Problem.character("\\").message)

        let issues = try #require(URL(string: "https://github.com/jlevy/metabrowser/issues/1"))
        panel.edit("github.com/jlevy/metabrowser/issues/1")
        let opened = panel.open()
        #expect(opened == issues)
        #expect(panel.text == issues.absoluteString)
        let refusal = PresentRefusal(code: "unsupported_github_url", message: "GitHub issues pages are not opened")
        _ = panel.answered(.refused(refusal), for: issues, metab: metab)
        #expect(panel.text == issues.absoluteString)
        #expect(panel.message == refusal.message)
        let dropped = panel.edit("github.com/jlevy/metabrowser")
        #expect(dropped == nil)
        let reopened = panel.open()
        #expect(reopened == repository)
        #expect(panel.text == repository.absoluteString)
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
        // The panel closing after its plan stops no dry run: the plan's is over.
        let dropped = panel.cancel()
        #expect(dropped == nil)
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
    /// It returns the link it stopped awaiting, whose dry run the app stops; an edit
    /// with no answer awaited returns nothing.
    @Test func anEditDropsTheAnswerAwaited() {
        var panel = checking(pullRequest.absoluteString)
        #expect(panel.awaited == pullRequest)
        let dropped = panel.edit("https://github.com/jlevy/metabrowser/pull/540")
        #expect(dropped == pullRequest)
        #expect(panel.awaited == nil)
        let droppedAgain = panel.edit("https://github.com/jlevy/metabrowser/pull/541")
        #expect(droppedAgain == nil)
        #expect(panel.phase == .editing)
        let opensLate = panel.answered(.plan(plan), for: pullRequest, metab: metab)
        #expect(opensLate == nil)
        #expect(panel.phase == .editing)
        #expect(panel.message == nil)
    }

    /// Cancel, or closing the panel, returns the link it stopped awaiting, as an edit does.
    @Test func cancelDropsTheAnswerAwaited() {
        var panel = checking(pullRequest.absoluteString)
        let dropped = panel.cancel()
        #expect(dropped == pullRequest)
        let droppedAgain = panel.cancel()
        #expect(droppedAgain == nil)
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
