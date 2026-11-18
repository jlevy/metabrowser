import Foundation
import Testing
@testable import ShellCore

nonisolated private let pullRequest = URL(string: "https://github.com/o/r/pull/1")!
nonisolated private let mainTree = URL(string: "https://github.com/o/r/tree/main")!
nonisolated private let commit = URL(string: "https://github.com/o/r/commit/0123abc")!
nonisolated private let ready = ServerState.ready(ServerEndpoint(
    origin: URL(string: "http://127.0.0.1:8475")!, entryURL: URL(string: "http://127.0.0.1:8475/view/")!))
nonisolated private let failed = ServerState.failed(ServerFailure(summary: "The server stopped unexpectedly.", recentOutput: []))

/// What a link sent into a repository with a window does to its server: the decision
/// review C5 on #539 asked to move out of the app target, as a table of states.
@Suite struct RepositoryLinksTests {
    /// A server that is not starting starts again on any link, the same one included,
    /// since its window may have moved to another revision since (View on branch).
    @Test(arguments: [ready, failed, ServerState.stopped])
    func aLinkRestartsAServerThatIsNotStarting(_ state: ServerState) {
        var links = RepositoryLinks(target: pullRequest)
        #expect(links.receive(mainTree, state: state) == .restart)
        #expect(links.target == mainTree)
        #expect(links.receive(mainTree, state: state) == .restart)
        #expect(links.pending == nil)
    }

    /// C3: the link a start already runs on, sent again during that start (a second click
    /// during a first clone), is not held, so the start's end restarts nothing.
    @Test(arguments: [ServerState.starting, ServerState.stopping])
    func theLinkAStartRunsOnStartsNothingMore(_ state: ServerState) {
        var links = RepositoryLinks(target: pullRequest)
        #expect(links.receive(pullRequest, state: state) == .none)
        #expect(links.pending == nil)
        #expect(links.startEnded() == nil)
        #expect(links.target == pullRequest)
    }

    /// Another link waits for the start under way; the newest wins, and the start's end
    /// restarts on it.
    @Test func anotherLinkWaitsForTheStartAndTheNewestWins() {
        var links = RepositoryLinks(target: pullRequest)
        #expect(links.receive(mainTree, state: .starting) == .hold)
        #expect(links.receive(commit, state: .stopping) == .hold)
        #expect(links.startEnded() == commit)
        #expect(links.target == commit)
        #expect(links.pending == nil)
        #expect(links.startEnded() == nil)
    }

    /// C3: a held link followed by the start's own link leaves nothing held: the newest
    /// link is the one the start runs on.
    @Test func theStartsOwnLinkCancelsAHeldOne() {
        var links = RepositoryLinks(target: pullRequest)
        #expect(links.receive(mainTree, state: .starting) == .hold)
        #expect(links.receive(pullRequest, state: .starting) == .none)
        #expect(links.startEnded() == nil)
        #expect(links.target == pullRequest)
    }

    /// C2 and C3: a restart that waits at the launch gate while the ready server serves
    /// counts as a start on its target: the same link changes nothing, and another
    /// replaces it.
    @Test func aRestartWaitingAtTheGateCountsAsAStart() {
        var links = RepositoryLinks(target: pullRequest)
        #expect(links.receive(pullRequest, state: ready, restarting: true) == .none)
        #expect(links.receive(mainTree, state: ready, restarting: true) == .restart)
        #expect(links.target == mainTree)
    }

    /// C12: a link held for a start whose last window then closes starts nothing, and a
    /// shut-down session takes no more links.
    @Test func aShutDownSessionStartsNothing() {
        var links = RepositoryLinks(target: pullRequest)
        #expect(links.receive(mainTree, state: .starting) == .hold)
        links.shutDown()
        #expect(links.pending == nil)
        #expect(links.startEnded() == nil)
        #expect(links.receive(commit, state: .stopped) == .none)
        #expect(links.target == pullRequest)
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
    }
}

/// C1 on #539: a link whose selection the mirror lacks is served from the default branch
/// while `metab` fetches it, and the app says when the fetch did not find it.
@Suite struct LinkSelectionTests {
    private let origin = URL(string: "http://127.0.0.1:8475")!

    nonisolated private static func status(_ state: String?, ref: String? = "master") -> Data {
        let quoted = { (text: String?) in text.map { "\"\($0)\"" } ?? "null" }
        return Data(#"{"subject": "git_revision", "ref_name": \#(quoted(ref)), "selection_state": \#(quoted(state)), "selection_href": null}"#.utf8)
    }

    @Test func aPendingSelectionIsWatchedUntilItsFetchEnds() async {
        let asked = Recorder<URLRequest>()
        let outcome = await LinkSelection.watch(
            origin: origin, authorization: .cookie(name: "metab", value: "t"),
            transport: { request in
                asked.append(request)
                return (200, Self.status(asked.count < 3 ? "pending" : "not_found"))
            },
            interval: .milliseconds(1))
        #expect(outcome == .notFound(serving: "master"))
        #expect(asked.count == 3)
        #expect(asked.all.first?.url == origin.appending(path: "api/source/status"))
        #expect(asked.all.first?.value(forHTTPHeaderField: "Cookie") == "metab=t")
    }

    @Test(arguments: [
        (200, "found", LinkSelection.Outcome.shown),
        (200, "superseded", .shown),
        (200, nil, .shown),
        (200, "fetch_failed", .fetchFailed(serving: "master")),
        (200, "not_found", .notFound(serving: "master")),
    ] as [(Int, String?, LinkSelection.Outcome)])
    func whatEachStateSays(_ code: Int, _ state: String?, _ expected: LinkSelection.Outcome) async {
        let outcome = await LinkSelection.watch(
            origin: origin, authorization: .none, transport: { _ in (code, Self.status(state)) }, interval: .milliseconds(1))
        #expect(outcome == expected)
    }

    @Test func aStatusThatCannotBeReadOrAFetchThatOutlastsTheWatchSaysNothing() async {
        let refused = await LinkSelection.watch(origin: origin, authorization: .none, transport: { _ in (500, Data()) })
        #expect(refused == .unknown("status 500"))
        let garbled = await LinkSelection.watch(origin: origin, authorization: .none, transport: { _ in (200, Data("<html>".utf8)) })
        #expect(garbled == .unknown("not a source status"))
        let slow = await LinkSelection.watch(
            origin: origin, authorization: .none, transport: { _ in (200, Self.status("pending")) },
            interval: .milliseconds(1), attempts: 3)
        #expect(slow == .unknown("still fetching after 3 answers"))
        let link = URL(string: "https://github.com/o/r/tree/x")!
        #expect(LinkAlert.selectionMissing(slow, link: link, repository: "github.com/o/r") == nil)
        #expect(LinkAlert.selectionMissing(.shown, link: link, repository: "github.com/o/r") == nil)
    }

    /// The alert names the revision the windows show, and the link without its query.
    @Test func theAlertNamesWhatTheWindowsShow() {
        let link = URL(string: "https://github.com/o/r/tree/no-such/branch?tab=readme")!
        let missing = LinkAlert.selectionMissing(.notFound(serving: "master"), link: link, repository: "github.com/o/r")
        #expect(missing?.message == "github.com/o/r has nothing this link names")
        #expect(missing?.detail.contains("so its windows show master instead") == true)
        #expect(missing?.detail.hasSuffix("https://github.com/o/r/tree/no-such/branch?…") == true)
        let unfetched = LinkAlert.selectionMissing(.fetchFailed(serving: nil), link: link, repository: "github.com/o/r")
        #expect(unfetched?.detail.contains("its default branch until a refresh finds it") == true)
    }
}
