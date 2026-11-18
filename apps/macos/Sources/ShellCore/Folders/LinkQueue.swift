import Foundation

/// The links waiting for `metab` to resolve them (`PresentDryRun`), resolved one at a
/// time.
///
/// Any local process can send the app links with `open -b`, so a burst is bounded here:
/// one `metab` resolves at a time, a link equal to one waiting or being resolved is
/// dropped as a repeat, and past `limit` waiting links the rest are counted, not kept,
/// so the app says once how many it dropped (`LinkProblems`).
public nonisolated struct LinkQueue: Equatable, Sendable {
    /// The most links that wait at once. Not measured: it bounds a burst rather than a
    /// cost, and an agent that hands the app a pull request and a few of its files sends
    /// well under it.
    public static let limit = 20

    public enum Offer: Equatable, Sendable {
        /// It waits its turn.
        case queued
        /// The same link waits or is being resolved already.
        case repeated
        /// `limit` links wait already; it is counted in `dropped`.
        case dropped
    }

    public private(set) var waiting: [URL] = []
    /// The link being resolved now.
    public private(set) var current: URL?
    /// Links turned away since `takeDropped()` last asked.
    public private(set) var dropped = 0

    public init() {}

    public mutating func offer(_ link: URL) -> Offer {
        let text = link.absoluteString
        if current?.absoluteString == text || waiting.contains(where: { $0.absoluteString == text }) { return .repeated }
        guard waiting.count < Self.limit else {
            dropped += 1
            return .dropped
        }
        waiting.append(link)
        return .queued
    }

    /// The next link to resolve, which is now `current`; nil while one is being resolved
    /// or none waits.
    public mutating func next() -> URL? {
        guard current == nil, !waiting.isEmpty else { return nil }
        current = waiting.removeFirst()
        return current
    }

    /// The current link is resolved, and whatever it opened has been decided.
    public mutating func finish() {
        current = nil
    }

    /// Whether no link waits or is being resolved: what the app checks before it offers
    /// the Open panel, since a link being resolved is about to open a window.
    public var isIdle: Bool { current == nil && waiting.isEmpty }

    public mutating func takeDropped() -> Int {
        defer { dropped = 0 }
        return dropped
    }
}
