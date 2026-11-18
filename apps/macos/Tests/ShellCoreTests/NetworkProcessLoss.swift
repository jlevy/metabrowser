import Foundation
import OSLog

/// WebKit's network process ended under a test's page loads (mb-1cd0).
///
/// Every page load in a test process goes through one WebKit network process. When it
/// ends, WebKit fails each navigation then on its way with `WebKitErrorDomain` 300 ("WebKit
/// encountered an internal error"), and one whose response decision is held with 102 as
/// well. None of them commits afterward and nothing loads them again; only the next load
/// gets a new network process. On CI it ended while the WebKit suites' first loads were
/// on their way, and each of their tests waited out `eventually` for a commit or a finish
/// that could not come. Ending it at that point (`_terminateNetworkProcess`) reproduces
/// that run's failures exactly. What ended it on CI is not known, so
/// `rerunningIfTheNetworkProcessEnds` prints what WebKit logged about it.
///
/// A test whose pages load over HTTP therefore runs its scenario again on new pages when
/// this happens. Waiting longer would not help, because those loads never complete.
nonisolated struct NetworkProcessLost: Error, CustomStringConvertible {
    var description: String { "WebKit's network process ended under this test's page loads on every attempt" }
}

/// Whether `error`, a navigation's failure, is WebKit's report that its network process
/// ended under the load: `WebLoaderStrategy::networkProcessCrashed` fails every pending
/// load with WebCore's internal error.
nonisolated func isNetworkProcessLoss(_ error: any Error) -> Bool {
    let error = error as NSError
    return error.domain == "WebKitErrorDomain" && error.code == 300
}

/// `eventually` for a condition on page loads. It throws `NetworkProcessLost` once `lost`
/// holds, and `rerunningIfTheNetworkProcessEnds` then runs the scenario again. `lost` is
/// checked after `condition`, so a condition that a lost load's failure satisfied does
/// not count as met.
func eventually(unlessLost lost: () -> Bool, _ condition: () -> Bool) async throws -> Bool {
    let met = await eventually { lost() || condition() }
    if lost() { throw NetworkProcessLost() }
    return met
}

/// Runs `scenario`, which makes its own pages, until a run ends without WebKit's network
/// process ending under its loads, at most `attempts` times.
///
/// In each CI run that lost the network process, a single loss caused every failure, so
/// a second run is enough and a third allows for another loss. A loss on every attempt is
/// not chance, so the test then fails with `NetworkProcessLost`.
func rerunningIfTheNetworkProcessEnds(attempts: Int = 3, _ scenario: () async throws -> Void) async throws {
    let start = Date()
    for attempt in 1... {
        do {
            return try await scenario()
        } catch is NetworkProcessLost where attempt < attempts {
            print("WebKit's network process ended under this test's page loads; running it again "
                + "(attempt \(attempt + 1) of \(attempts)). WebKit logged:")
            for line in await webKitNetworkProcessLines(since: start) { print("  \(line)") }
        }
    }
}

/// The errors WebKit logged in this process about its network process since `start`,
/// which name what ended it, such as `NetworkProcessProxy::didClose (Network Process 0
/// crash)` or `NetworkProcessProxy::didBecomeUnresponsive`. This is best effort and reads
/// off the main actor, because reading the log store can take seconds on a loaded machine.
@concurrent nonisolated func webKitNetworkProcessLines(since start: Date) async -> [String] {
    let filter = NSPredicate(format: "subsystem == 'com.apple.WebKit' AND composedMessage CONTAINS[c] 'networkprocess'")
    guard let store = try? OSLogStore(scope: .currentProcessIdentifier),
        let entries = try? store.getEntries(at: store.position(date: start), matching: filter)
    else { return ["(this process's log could not be read)"] }
    return entries.compactMap { entry in
        guard let entry = entry as? OSLogEntryLog, entry.level == .error || entry.level == .fault else { return nil }
        return entry.composedMessage
    }
}
