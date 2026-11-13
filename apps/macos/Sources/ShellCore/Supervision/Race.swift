import Foundation

/// The result of whichever operation finishes first, or nil once `limit` elapses.
///
/// The losers are cancelled, so each operation must return promptly on cancellation:
/// `Latch.wait()` and `AsyncStream` iteration do.
public nonisolated func firstResult<T: Sendable>(
    within limit: Duration, of operations: [@Sendable () async -> T?]
) async -> T? {
    await withTaskGroup(of: T?.self) { group in
        for operation in operations {
            group.addTask { await operation() }
        }
        group.addTask {
            try? await Task.sleep(for: limit)
            return nil
        }
        let first = await group.next() ?? nil
        group.cancelAll()
        return first
    }
}
