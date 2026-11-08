/// Allows at most `limit` recoveries within any `window`, so an automatic retry that
/// keeps failing stops and says so instead of looping.
public nonisolated struct RecoveryBudget: Sendable {
    public let limit: Int
    public let window: Duration
    private var recent: [ContinuousClock.Instant] = []

    public init(limit: Int, within window: Duration) {
        self.limit = limit
        self.window = window
    }

    /// Records an attempt at `now` and says whether it is within the budget.
    public mutating func allow(at now: ContinuousClock.Instant = .now) -> Bool {
        recent.removeAll { $0.duration(to: now) >= window }
        guard recent.count < limit else { return false }
        recent.append(now)
        return true
    }
}
