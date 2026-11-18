import Foundation
import OSLog

/// WebKit's network process ended under a test's page loads (mb-1cd0).
///
/// Every page load in a test process goes through one WebKit network process. When it
/// ends, WebKit fails each navigation then on its way with `WebKitErrorDomain` 300 ("WebKit
/// encountered an internal error"), and one whose response decision is held with 102 as
/// well. None of them commits or finishes afterward, and nothing loads them again. A test
/// that waited for one would wait out `eventually` and fail on what followed, as the WebKit
/// suites did on CI when `DownloadTests` made WebKit end the network process. A test that
/// waits through `eventually(unlessLost:)` fails at once with this error, which carries
/// what WebKit logged about the network process, the cause included.
nonisolated struct NetworkProcessLost: Error, CustomStringConvertible {
    /// WebKit's errors in this process that mention the network process.
    var webKitLog: [String]

    var description: String {
        (["WebKit's network process ended under this test's page loads, which will not complete. WebKit logged:"]
            + webKitLog.map { "  \($0)" }).joined(separator: "\n")
    }
}

/// Whether `error`, a navigation's failure, is WebKit's report that its network process
/// ended under the load: `WebLoaderStrategy::networkProcessCrashed` fails every pending
/// load with WebCore's internal error.
nonisolated func isNetworkProcessLoss(_ error: any Error) -> Bool {
    let error = error as NSError
    return error.domain == "WebKitErrorDomain" && error.code == 300
}

/// `eventually` for a condition on page loads. It throws `NetworkProcessLost` once `lost`
/// holds. `lost` is checked after `condition`, so a condition that the lost load's failure
/// satisfied does not count as met.
func eventually(unlessLost lost: () -> Bool, _ condition: () -> Bool) async throws -> Bool {
    let met = await eventually { lost() || condition() }
    if lost() { throw NetworkProcessLost(webKitLog: await webKitNetworkProcessLog()) }
    return met
}

/// The errors and faults WebKit logged in this process that mention the network process,
/// which name what ended it: for example, `Received an invalid message
/// 'DownloadProxy_DidCreateDestination' from the Networking process`. Each content process
/// logs its own line, so repeated lines are counted instead of listed. The log is read off
/// the main actor, because reading it can take seconds on a loaded machine.
@concurrent nonisolated func webKitNetworkProcessLog() async -> [String] {
    let filter = NSPredicate(format: "subsystem == 'com.apple.WebKit' AND composedMessage CONTAINS[c] 'network'")
    guard let store = try? OSLogStore(scope: .currentProcessIdentifier),
        let entries = try? store.getEntries(matching: filter)
    else { return ["(this process's log could not be read)"] }
    var counted: [(message: String, count: Int)] = []
    for case let entry as OSLogEntryLog in entries where entry.level == .error || entry.level == .fault {
        // "WebContent[123] 0x10c06c0e0 - WebLoaderStrategy::...", without what varies
        let message = entry.composedMessage.replacing(#/^(WebContent\[\d+\] )?0x[0-9a-f]+ - /#, with: "")
        if let index = counted.firstIndex(where: { $0.message == message }) {
            counted[index].count += 1
        } else {
            counted.append((message, 1))
        }
    }
    if counted.isEmpty { return ["(nothing about its network process)"] }
    return counted.map { $0.count > 1 ? "\($0.count) times: \($0.message)" : $0.message }
}
