import Foundation

/// Which repositories a link may start a server for, and the question asked about the
/// rest (`AppDelegate.open(_:with:)`).
///
/// A link into a repository that `metab`'s cache does not hold asks first, since a first
/// clone downloads it and reads it with the user's `gh` sign-in on the word of whatever
/// sent the link (`RepositoryCache`). The question waits beside the link queue rather
/// than in it, so the links behind it, into open repositories among them, go on
/// resolving while it is unanswered (review C8 on #539). Links into a repository that is
/// being looked up or asked about wait with it, and one answer covers them all; the
/// newest of them opens, as a link into an open repository replaces an older one. A
/// repository declined stays declined until the burst ends, when no link waits or is
/// resolving and no question waits, so a burst asks once (C7); a link sent after that
/// asks again. Questions are asked one at a time, in the order their links came.
public nonisolated struct CloneQuestions: Equatable, Sendable {
    /// The most repositories that wait for the cache or a question at once. Not measured:
    /// it bounds how many questions, each a modal answered in turn, a burst of links can
    /// line up; an agent handing the app a pull request and its files names one.
    public static let limit = 5

    /// What a link into a repository with no session does.
    public enum Arrival: Equatable, Sendable {
        /// The cache holds it, or the user said to clone it: open it.
        case open
        /// The first link into it: ask the cache, then `found(_:)` or `ask(_:)`.
        case lookUp
        /// The cache or a question is being asked about it: the link waits for the answer.
        case waits
        /// Declined in this burst: not opened, and counted (`endBurst()`).
        case declined
        /// `limit` repositories wait already: not opened, and counted (`takeDropped()`).
        case dropped
    }

    /// The repositories found in the cache or agreed to, which later links open without
    /// asking. Kept in memory only, for this run of the app.
    public private(set) var known: Set<SessionRoot> = []
    /// Each repository being looked up or asked about: the newest link into it, and how
    /// many links wait.
    private var waiting: [SessionRoot: Held] = [:]
    /// The repositories whose question waits to be asked, in order.
    private var unasked: [SessionRoot] = []
    /// The repository whose question is up.
    public private(set) var asking: SessionRoot?
    /// The repositories declined in this burst, with how many links into each were not
    /// opened besides the one the question named.
    private var declined: [SessionRoot: Int] = [:]
    private var dropped = 0

    private struct Held: Equatable, Sendable {
        var link: URL
        var count: Int
    }

    public init() {}

    /// A link into `repository`, which has no session.
    public mutating func arrive(_ link: URL, into repository: SessionRoot) -> Arrival {
        if known.contains(repository) { return .open }
        if let turnedAway = declined[repository] {
            declined[repository] = turnedAway + 1
            return .declined
        }
        if let held = waiting[repository] {
            waiting[repository] = Held(link: link, count: held.count + 1)
            return .waits
        }
        guard waiting.count < Self.limit else {
            dropped += 1
            return .dropped
        }
        waiting[repository] = Held(link: link, count: 1)
        return .lookUp
    }

    /// The cache holds it: the newest link into it, which opens now.
    public mutating func found(_ repository: SessionRoot) -> URL? {
        known.insert(repository)
        return waiting.removeValue(forKey: repository)?.link
    }

    /// The cache does not hold it, or could not say: it waits for its question.
    public mutating func ask(_ repository: SessionRoot) {
        guard waiting[repository] != nil, asking != repository, !unasked.contains(repository) else { return }
        unasked.append(repository)
    }

    /// The question to ask now, which is then `asking`; nil while one is up or none waits.
    public mutating func nextQuestion() -> SessionRoot? {
        guard asking == nil, !unasked.isEmpty else { return nil }
        asking = unasked.removeFirst()
        return asking
    }

    /// The user answered the question about `repository`: the newest link into it, to
    /// open, if they said to clone it, else nil.
    public mutating func answer(_ repository: SessionRoot, clone: Bool) -> URL? {
        if asking == repository { asking = nil }
        unasked.removeAll { $0 == repository }
        guard let held = waiting.removeValue(forKey: repository) else { return nil }
        if clone {
            known.insert(repository)
            return held.link
        }
        declined[repository] = held.count - 1
        return nil
    }

    /// Whether no repository is being looked up, waits for its question, or is asked
    /// about: with an idle link queue, the end of a burst.
    public var isIdle: Bool { waiting.isEmpty && asking == nil }

    /// The burst ended: forgets every decline, and returns how many links each turned
    /// away besides the one its question named, where that is any.
    public mutating func endBurst() -> [SessionRoot: Int] {
        defer { declined = [:] }
        return declined.filter { $0.value > 0 }
    }

    /// Links turned away since this last asked, because `limit` repositories waited.
    public mutating func takeDropped() -> Int {
        defer { dropped = 0 }
        return dropped
    }
}
