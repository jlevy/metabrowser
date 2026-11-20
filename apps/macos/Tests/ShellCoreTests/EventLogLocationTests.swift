import Foundation
import Testing

@testable import ShellCore

/// What Help > Open Event Log makes of the answers `metab` can give; the golden's answers,
/// and the command line the app writes, are read in `AppContractTests`.
struct EventLogLocationTests {
    private func answer(_ json: String, status: Int32 = 0) -> CommandResult {
        CommandResult(status: status << 8, output: json.split(separator: "\n", omittingEmptySubsequences: false).map(String.init))
    }

    @Test func theNewestSegmentIsTheFirstTheRouteLists() {
        let result = answer(#"{"directory": "/state/events", "files": [{"name": "events-b.jsonl"}, {"name": "events-a.jsonl"}]}"#)
        #expect(EventLogLocation.read(result) == .found(URL(filePath: "/state/events/events-b.jsonl")))
    }

    @Test func aDirectoryWithNoSegmentIsEmpty() {
        let result = answer(#"{"directory": "/state/events", "state": "absent", "files": []}"#)
        #expect(EventLogLocation.read(result) == .empty(URL(filePath: "/state/events", directoryHint: .isDirectory)))
    }

    /// A name is a segment's, never a path: one with a separator is not followed out of the folder.
    @Test func aNameThatIsAPathIsNotASegment() {
        let result = answer(#"{"directory": "/state/events", "files": [{"name": "../secret"}]}"#)
        #expect(EventLogLocation.read(result) == .empty(URL(filePath: "/state/events", directoryHint: .isDirectory)))
    }

    @Test func anAnswerWithoutADirectoryOrSegmentsIsUnavailable() {
        for json in ["{}", #"{"directory": "", "files": []}"#, #"{"directory": "/x"}"#, #"{"files": []}"#] {
            guard case .unavailable = EventLogLocation.read(answer(json)) else {
                Issue.record("\(json) was read as an answer")
                continue
            }
        }
    }

    @Test func aFailureSaysWhatMetabPrintedOrHowItEnded() {
        let printed = CommandResult(status: 1 << 8, output: ["Error: no such option"])
        #expect(EventLogLocation.read(printed) == .unavailable("Error: no such option"))
        let silent = CommandResult(status: 1 << 8, output: [])
        guard case .unavailable(let why) = EventLogLocation.read(silent) else {
            Issue.record("a silent failure was read as an answer")
            return
        }
        #expect(!why.isEmpty)
        #expect(EventLogLocation.read(CommandResult(status: nil, output: [], launchError: "no such file"))
            == .unavailable("could not run: no such file"))
        guard case .unavailable = EventLogLocation.read(CommandResult(status: nil, output: [], timedOut: true)) else {
            Issue.record("a command that timed out was read as an answer")
            return
        }
    }

    @Test func theCommandAsksTheRouteOfTheFolderWithoutStartingAServer() {
        #expect(EventLogLocation.arguments(folder: "/support") == ["/support", "--api", "/api/event-log?limit=1", "--format", "json"])
    }
}
