import Foundation
import Testing
@testable import ShellCore

nonisolated private let pullRequest = URL(string: "https://github.com/o/r/pull/1")!
nonisolated private let mainTree = URL(string: "https://github.com/o/r/tree/main")!
nonisolated private let commit = URL(string: "https://github.com/o/r/commit/0123abc")!
nonisolated private let ready = ServerState.ready(ServerEndpoint(
    origin: URL(string: "http://127.0.0.1:8475")!, entryURL: URL(string: "http://127.0.0.1:8475/view/")!))
nonisolated private let failed = ServerState.failed(ServerFailure(summary: "The server stopped unexpectedly.", recentOutput: []))

/// What a link sent into a repository's session does (bead mb-30xb): one server per
/// repository, started on the repository, opens every link into it, so no link starts
/// it again unless it is down.
@Suite struct RepositoryLinksTests {
    /// The defect: a second pull request of a repository started its server again on
    /// that pull request. A ready server opens any link at once, the same one again too.
    @Test func aReadyServerOpensEveryLinkWithoutStartingAgain() {
        var links = RepositoryLinks(waiting: pullRequest)
        #expect(links.serverReady() == pullRequest)
        #expect(links.receive(mainTree, state: ready) == .open)
        #expect(links.receive(commit, state: ready) == .open)
        #expect(links.receive(commit, state: ready) == .open)
        #expect(links.waiting == nil)
        #expect(links.serverReady() == nil)
    }

    /// A link sent while the server starts, such as during a first clone, waits for it;
    /// the newest wins, and opens once, when the server is ready.
    @Test(arguments: [ServerState.starting, ServerState.stopping])
    func aLinkWaitsForTheStartAndTheNewestWins(_ state: ServerState) {
        var links = RepositoryLinks(waiting: pullRequest)
        #expect(links.receive(mainTree, state: state) == .hold)
        #expect(links.receive(commit, state: state) == .hold)
        #expect(links.serverReady() == commit)
        #expect(links.serverReady() == nil)
    }

    /// A restart that waits at the launch gate while the old server serves: the link
    /// waits for the new server rather than opening in the one about to stop.
    @Test func aLinkWaitsForARestartUnderWay() {
        var links = RepositoryLinks()
        #expect(links.receive(mainTree, state: ready, restarting: true) == .hold)
        #expect(links.serverReady() == mainTree)
    }

    /// A failed or stopped server starts again for a link, which opens once it is ready.
    @Test(arguments: [failed, ServerState.stopped])
    func aLinkStartsAServerThatIsDown(_ state: ServerState) {
        var links = RepositoryLinks()
        #expect(links.receive(pullRequest, state: state) == .start)
        #expect(links.waiting == pullRequest)
        #expect(links.serverReady() == pullRequest)
    }

    /// A link waiting for a start whose last window then closes opens nothing, and a
    /// shut-down session takes no more links.
    @Test func aShutDownSessionOpensNothing() {
        var links = RepositoryLinks(waiting: pullRequest)
        #expect(links.receive(mainTree, state: .starting) == .hold)
        links.shutDown()
        #expect(links.serverReady() == nil)
        #expect(links.receive(commit, state: ready) == .none)
        #expect(links.receive(commit, state: .stopped) == .none)
    }
}

/// D1 on #539: which windows say that a restart of the ready server waits at the launch
/// gate, while the old server serves the others.
@Suite struct RestartWaitTests {
    /// Stands in for a window controller: an object, held by whatever still uses it.
    private final class Window {}

    /// File > Restart Server while another repository's clone holds the gate: the window
    /// it was chosen in says it waits once the supervisor says the restart waits.
    @Test func theWindowThatAskedSaysItWaitsOnceTheRestartWaits() {
        var wait = RestartWait<Window>()
        let asked = Window()
        #expect(wait.asked(from: asked, state: ready) == nil)
        let shown = wait.gateWait(true, state: ready)
        #expect(shown.count == 1 && shown[0] === asked)
        #expect(wait.isWaiting)
    }

    /// The supervisor says only when its first waiter begins to wait, so a restart asked
    /// for while one waits, a link's or another Restart Server's, shows its window at once,
    /// whichever window that is.
    @Test func aRestartAskedWhileAnotherWaitsShowsItsWindowAtOnce() {
        var wait = RestartWait<Window>()
        let first = Window(), linked = Window()
        _ = wait.asked(from: first, state: ready)
        _ = wait.gateWait(true, state: ready)
        #expect(wait.asked(from: linked, state: ready) === linked)
        #expect(wait.asked(from: first, state: ready) === first)
        _ = wait.gateWait(false, state: ready)
        #expect(!wait.isWaiting)
        #expect(wait.asked(from: linked, state: ready) == nil)
    }

    /// A server that is not ready shows its state in every window, so no window is singled
    /// out, and one that changes state forgets the windows that asked.
    @Test(arguments: [ServerState.starting, ServerState.stopping, ServerState.stopped, failed])
    func aServerThatIsNotReadyShowsItsStateInEveryWindow(_ state: ServerState) {
        var wait = RestartWait<Window>()
        let asked = Window()
        _ = wait.gateWait(true, state: state)
        #expect(wait.asked(from: asked, state: state) == nil)
        #expect(wait.gateWait(true, state: ready).isEmpty)
    }

    @Test func theWindowsThatAskedAreForgottenWhenTheServerChanges() {
        var wait = RestartWait<Window>()
        let asked = Window()
        _ = wait.asked(from: asked, state: ready)
        wait.serverChanged()
        #expect(wait.gateWait(true, state: ready).isEmpty)
        withExtendedLifetime(asked) {}
    }

    /// A window asks once however often it asks, and a window freed is not kept.
    @Test func eachWindowIsKeptOnceAndAFreedOneIsNot() {
        var wait = RestartWait<Window>()
        let kept = Window()
        _ = wait.asked(from: kept, state: ready)
        _ = wait.asked(from: kept, state: ready)
        do {
            let closed = Window()
            _ = wait.asked(from: closed, state: ready)
        }
        let shown = wait.gateWait(true, state: ready)
        #expect(shown.count == 1 && shown[0] === kept)
        #expect(wait.asked(from: nil, state: ready) == nil)
    }
}

/// The question before a clone, which waits beside the link queue (reviews B2, C7, C8,
/// and C9 on #539).
@Suite struct CloneQuestionsTests {
    private let r = SessionRoot.repository(URL(string: "https://github.com/o/r")!)
    private let s = SessionRoot.repository(URL(string: "https://github.com/o/s")!)

    private func link(_ n: Int, in root: SessionRoot? = nil) -> URL {
        (root ?? r).url.appending(path: "pull/\(n)")
    }

    @Test func aCachedRepositoryOpensAndIsNotLookedUpAgain() {
        var questions = CloneQuestions()
        #expect(questions.arrive(link(1), into: r) == .lookUp)
        #expect(!questions.isIdle)
        #expect(questions.found(r) == link(1))
        #expect(questions.isIdle)
        #expect(questions.arrive(link(2), into: r) == .open)
        #expect(questions.nextQuestion() == nil)
    }

    /// C8: the question waits beside the queue, links into the repository wait with it,
    /// and one answer opens the newest of them.
    @Test func linksIntoARepositoryBeingAskedAboutWaitForOneAnswer() {
        var questions = CloneQuestions()
        #expect(questions.arrive(link(1), into: r) == .lookUp)
        questions.ask(r)
        #expect(questions.arrive(link(2), into: r) == .waits)
        #expect(questions.nextQuestion() == r)
        #expect(questions.arrive(link(3), into: r) == .waits)
        #expect(questions.nextQuestion() == nil)  // one question at a time
        #expect(!questions.isIdle)
        #expect(questions.answer(r, clone: true) == link(3))
        #expect(questions.isIdle)
        #expect(questions.arrive(link(4), into: r) == .open)
        #expect(questions.endBurst().isEmpty)
    }

    /// C7: a decline covers the links that waited with the question and those sent until
    /// the burst ends, which are said once; a link after that asks again.
    @Test func aDeclineHoldsUntilTheBurstEnds() {
        var questions = CloneQuestions()
        _ = questions.arrive(link(1), into: r)
        questions.ask(r)
        _ = questions.arrive(link(2), into: r)
        #expect(questions.nextQuestion() == r)
        #expect(questions.answer(r, clone: false) == nil)
        #expect(questions.isIdle)
        #expect(questions.arrive(link(3), into: r) == .declined)
        #expect(questions.endBurst() == [r: 2])
        #expect(questions.endBurst().isEmpty)
        #expect(questions.arrive(link(4), into: r) == .lookUp)
    }

    @Test func anExplicitOpenSupersedesAnOlderCacheLookup() {
        var questions = CloneQuestions()
        #expect(questions.arrive(link(1), into: r) == .lookUp)

        let wasShowing = questions.openedExplicitly(r)
        #expect(!wasShowing)
        questions.ask(r)
        #expect(questions.nextQuestion() == nil)

        // The explicit request does not authorize another link after its session closes.
        #expect(questions.arrive(link(2), into: r) == .lookUp)
    }

    @Test func aLateCacheHitDoesNotReopenTheOlderLink() {
        var questions = CloneQuestions()
        #expect(questions.arrive(link(1), into: r) == .lookUp)
        let wasShowing = questions.openedExplicitly(r)
        #expect(!wasShowing)

        #expect(questions.found(r) == nil)
        #expect(questions.isIdle)
    }

    @Test func anExplicitOpenOnlySupersedesTheMatchingQuestion() {
        var questions = CloneQuestions()
        _ = questions.arrive(link(1), into: r)
        _ = questions.arrive(link(1, in: s), into: s)
        questions.ask(r)
        questions.ask(s)

        #expect(questions.nextQuestion() == r)
        let dismissedOtherQuestion = questions.openedExplicitly(s)
        #expect(!dismissedOtherQuestion)
        #expect(questions.asking == r)
        let dismissedActiveQuestion = questions.openedExplicitly(r)
        #expect(dismissedActiveQuestion)
        #expect(questions.answer(r, clone: false) == nil)
        #expect(questions.nextQuestion() == nil)
        #expect(questions.endBurst().isEmpty)
    }

    @Test func anExplicitOpenLeavesEarlierExternalDeclinesInTheirBurst() {
        var questions = CloneQuestions()
        _ = questions.arrive(link(1), into: r)
        questions.ask(r)
        _ = questions.nextQuestion()
        _ = questions.answer(r, clone: false)

        let wasShowing = questions.openedExplicitly(r)
        #expect(!wasShowing)
        #expect(questions.arrive(link(2), into: r) == .declined)
        #expect(questions.endBurst() == [r: 1])
    }

    /// A decline with no other link into the repository has nothing more to say.
    @Test func aLoneDeclineSaysNothingMore() {
        var questions = CloneQuestions()
        _ = questions.arrive(link(1), into: r)
        questions.ask(r)
        _ = questions.nextQuestion()
        _ = questions.answer(r, clone: false)
        #expect(questions.endBurst().isEmpty)
    }

    @Test func questionsAreAskedOneAtATimeInTheOrderTheirLinksCame() {
        var questions = CloneQuestions()
        _ = questions.arrive(link(1), into: r)
        _ = questions.arrive(link(1, in: s), into: s)
        questions.ask(r)
        questions.ask(s)
        questions.ask(s)  // asked once
        #expect(questions.nextQuestion() == r)
        #expect(questions.nextQuestion() == nil)
        #expect(questions.answer(r, clone: true) == link(1))
        #expect(questions.nextQuestion() == s)
        #expect(questions.answer(s, clone: true) == link(1, in: s))
        #expect(questions.nextQuestion() == nil)
        #expect(questions.isIdle)
    }

    /// C9: past `limit` repositories waiting for the cache or a question, links into
    /// another are counted, not kept.
    @Test func repositoriesPastTheLimitAreCounted() {
        var questions = CloneQuestions()
        let roots = (0...CloneQuestions.limit).map { SessionRoot.repository(URL(string: "https://github.com/o/r\($0)")!) }
        for root in roots.dropLast() { #expect(questions.arrive(link(1, in: root), into: root) == .lookUp) }
        #expect(questions.arrive(link(1, in: roots.last), into: roots.last!) == .dropped)
        #expect(questions.arrive(link(2, in: roots[0]), into: roots[0]) == .waits)  // a waiting one still gathers
        #expect(questions.takeDropped() == 1)
        #expect(questions.takeDropped() == 0)
    }
}

/// B1 and C9 on #539: what a burst could not open is one alert, and what it keeps is
/// bounded however long the burst runs.
@Suite struct LinkProblemsTests {
    private let one = LinkAlert(message: "Metabrowser cannot open this link", detail: "why")

    @Test func nothingNotedIsNoAlertAndOneIsItself() {
        var problems = LinkProblems()
        #expect(problems.take() == nil)
        problems.note(one)
        #expect(problems.take() == one)
        #expect(problems.isEmpty)
    }

    @Test func aBurstsProblemsAreOneAlertThatKeepsTheFirstFew() {
        var problems = LinkProblems()
        for _ in 0..<1_000 { problems.note(one) }
        #expect(problems.shown.count == LinkAlert.shownInBatch)
        #expect(problems.more == 1_000 - LinkAlert.shownInBatch)
        problems.noteTurnedAway(3, .queueFull)
        problems.noteTurnedAway(1, .questionsFull)
        problems.noteTurnedAway(0, .runtimeWaitFull)
        let alert = problems.take()
        #expect(alert?.message == "Metabrowser could not open 1004 links")
        // C12: what the queue does, in its constant's words.
        #expect(alert?.detail.contains(
            "3 more links were not opened: Metabrowser resolves one link at a time and keeps \(LinkQueue.limit) waiting.") == true)
        #expect(alert?.detail.contains(
            "1 more link was not opened: Metabrowser asks about \(CloneQuestions.limit) repositories it has no copy of at a time.") == true)
        #expect(alert?.detail.contains("waiting for a metab") == false)
        #expect(alert?.detail.contains("and \(1_000 - LinkAlert.shownInBatch) more.") == true)
        #expect(alert?.detail.components(separatedBy: "Metabrowser cannot open this link: why").count == LinkAlert.shownInBatch + 1)
        #expect(problems.isEmpty)
    }

    /// C7: a decline that turned links away is said once, naming the repository.
    @Test func aDeclineIsSaidWithTheLinksItTurnedAway() {
        let alert = LinkAlert.declined("github.com/o/r", count: 2)
        #expect(alert.message == "Metabrowser did not clone github.com/o/r")
        #expect(alert.detail.hasPrefix("2 more links into github.com/o/r were not opened, since you declined to clone it."))
        #expect(LinkAlert.declined("github.com/o/r", count: 1).detail.hasPrefix("1 more link into github.com/o/r was not opened"))
        #expect(alert.links == .notOpened(2))
    }

    /// D3: the title counts links, not the problems it lists. Hand check 16's burst plus an
    /// issues link: a refusal and a decline of two more links are three links not opened.
    @Test func theTitleCountsTheLinksADeclineStandsFor() {
        var problems = LinkProblems()
        problems.note(one)
        problems.note(LinkAlert.declined("github.com/o/r", count: 2))
        #expect(problems.take()?.message == "Metabrowser could not open 3 links")

        // Past the problems listed, the links are still counted, and so are those turned away.
        var many = LinkProblems()
        for _ in 0..<LinkAlert.shownInBatch { many.note(one) }
        many.note(LinkAlert.declined("github.com/o/r", count: 4))
        many.noteTurnedAway(2, .queueFull)
        #expect(many.take()?.message == "Metabrowser could not open \(LinkAlert.shownInBatch + 6) links")
    }
}

/// The ready server opens a link (`SourceLink`, `POST /api/source/link`): its page, or,
/// for what the mirror lacks, the page once the refresh the request started has ended.
@Suite struct SourceLinkTests {
    private let origin = URL(string: "http://127.0.0.1:8475")!
    private let link = URL(string: "https://github.com/o/r/tree/release/v1/docs")!

    nonisolated private static func json(_ text: String) -> Data { Data(text.utf8) }
    nonisolated private static let opened = json(#"{"href": "/view/g1-ZG9jcw/", "kind": "tree", "changed": true, "refresh": "started", "status": {}}"#)
    nonisolated private static let pending = json(#"{"code": "selection_pending", "kind": "tree", "refresh": "started", "status": {}}"#)
    nonisolated private static func status(refreshing: Bool) -> Data {
        json(#"{"subject": "git_revision", "refreshing": \#(refreshing)}"#)
    }

    @Test func aLinkTheMirrorHasOpensAtItsPageAndAsksForARefresh() async throws {
        let asked = Recorder<URLRequest>()
        let outcome = await SourceLink.open(
            link, origin: origin, authorization: .cookie(name: "metab", value: "t"),
            transport: { request in
                asked.append(request)
                return (200, Self.opened)
            })
        #expect(outcome == .page(PageAddress(reference: "/view/g1-ZG9jcw/")!))
        let request = try #require(asked.all.first)
        #expect(asked.count == 1)
        #expect(request.url == origin.appending(path: "api/source/link"))
        #expect(request.httpMethod == "POST")
        #expect(request.value(forHTTPHeaderField: "Content-Type") == "application/json")
        #expect(request.value(forHTTPHeaderField: "Cookie") == "metab=t")
        let body = try #require(request.httpBody.flatMap { try JSONSerialization.jsonObject(with: $0) as? [String: Any] })
        #expect(body["link"] as? String == link.absoluteString)
        #expect(body["fetch"] as? Bool == true)
    }

    /// What the mirror lacks waits for the refresh to end, then is asked for once more
    /// without another refresh.
    @Test func aPendingLinkIsAskedForAgainOnceTheRefreshEnds() async throws {
        let asked = Recorder<URLRequest>()
        let outcome = await SourceLink.open(
            link, origin: origin, authorization: .none,
            transport: { request in
                asked.append(request)
                if request.url?.path() == "/api/source/status" {
                    return (200, Self.status(refreshing: asked.count < 3))
                }
                return asked.count == 1 ? (202, Self.pending) : (200, Self.opened)
            },
            interval: .milliseconds(1))
        #expect(outcome == .page(PageAddress(reference: "/view/g1-ZG9jcw/")!))
        #expect(asked.all.map { $0.url?.path() } == [
            "/api/source/link", "/api/source/status", "/api/source/status", "/api/source/link",
        ])
        let last = try #require(asked.all.last?.httpBody.flatMap { try JSONSerialization.jsonObject(with: $0) as? [String: Any] })
        #expect(last["fetch"] as? Bool == false)
    }

    @Test func whatTheMirrorLacksAfterTheRefreshIsNotFound() async {
        let outcome = await SourceLink.open(
            link, origin: origin, authorization: .none,
            transport: { request in
                if request.url?.path() == "/api/source/status" { return (200, Self.status(refreshing: false)) }
                let body = request.httpBody.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
                return body?["fetch"] as? Bool == false
                    ? (404, Self.json(#"{"error": "no", "code": "ref_not_found"}"#)) : (202, Self.pending)
            },
            interval: .milliseconds(1))
        #expect(outcome == .notFound(code: "ref_not_found"))
        let alert = LinkAlert.linkNotFound(outcome, link: link, repository: "github.com/o/r")
        #expect(alert?.message == "github.com/o/r has nothing this link names")
        #expect(alert?.detail.contains("so its window stays where it was") == true)
        #expect(alert?.links == .notOpened(1))
    }

    @Test func anAnswerTheAppCannotReadLeavesTheWindowWhereItWas() async {
        let refused = await SourceLink.open(link, origin: origin, authorization: .none, transport: { _ in (409, Self.json(#"{"code": "other_repository"}"#)) })
        #expect(refused == .unknown("status 409: other_repository"))
        let garbled = await SourceLink.open(link, origin: origin, authorization: .none, transport: { _ in (200, Self.json("<html>")) })
        #expect(garbled == .unknown("status 200, not a link's answer"))
        let elsewhere = await SourceLink.open(link, origin: origin, authorization: .none, transport: { _ in (200, Self.json(#"{"href": "https://example.com/"}"#)) })
        #expect(elsewhere == .unknown("an href that is not a page of the server"))
        let slow = await SourceLink.open(
            link, origin: origin, authorization: .none,
            transport: { request in
                request.url?.path() == "/api/source/status" ? (200, Self.status(refreshing: true)) : (202, Self.pending)
            },
            interval: .milliseconds(1), attempts: 3)
        #expect(slow == .unknown("still fetching after 3 answers"))
        #expect(LinkAlert.linkNotFound(slow, link: link, repository: "github.com/o/r") == nil)
    }
}
