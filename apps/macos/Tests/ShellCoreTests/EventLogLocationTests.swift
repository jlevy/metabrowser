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

    /// The three outcomes of Help > Open Event Log: a segment to open, and two answers that are
    /// told in an alert rather than left as a menu item that does nothing.
    @Test func aSegmentIsOpenedAndTheOtherAnswersAreToldInAnAlert() {
        let segment = URL(filePath: "/state/events/events-b.jsonl")
        #expect(EventLogLocation.action(for: .found(segment)) == .open(segment))

        let directory = URL(filePath: "/state/events", directoryHint: .isDirectory)
        guard case .tell(let title, let message) = EventLogLocation.action(for: .empty(directory)) else {
            Issue.record("a directory with no segment was opened")
            return
        }
        #expect(title == "There is no event log yet")
        #expect(message.contains("/state/events"))

        guard case .tell(let failedTitle, let failedMessage) = EventLogLocation.action(for: .unavailable("boom"))
        else {
            Issue.record("an answer metab could not give was opened")
            return
        }
        #expect(failedTitle == "Could not open the event log")
        #expect(failedMessage.contains("boom"))
        #expect(failedMessage.contains("Check Setup"))
    }

    /// The segment opens in the log's own directory, where the general rule would put it inside
    /// the open home folder that holds it, whose server records what it answers.
    @Test func theSegmentOpensInTheLogsOwnDirectoryEvenInsideAnOpenFolder() {
        let segment = URL(filePath: "/Homes/me/.local/state/metabrowser/events/events-b.jsonl")
        #expect(EventLogLocation.target(for: segment)
            == OpenTarget(root: "/Homes/me/.local/state/metabrowser/events", page: .view(of: "events-b.jsonl")))
        #expect(OpenTarget.resolve(segment.path(percentEncoded: false), kind: .file, openRoots: ["/Homes/me"])
            == OpenTarget(
                root: "/Homes/me", page: .view(of: ".local/state/metabrowser/events/events-b.jsonl")))
    }

    @Test func theCommandAsksTheRouteOfTheFolderWithoutStartingAServer() {
        #expect(EventLogLocation.arguments(folder: "/support") == ["/support", "--api", "/api/event-log?limit=1", "--format", "json"])
    }
}
