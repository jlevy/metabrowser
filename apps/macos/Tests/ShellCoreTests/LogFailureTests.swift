import Darwin
import Foundation
import Testing
@testable import ShellCore

/// A log that cannot be kept is reported where the user sees it, never dropped: a
/// launch fails with the reason, and output the log could not take says so.
@Suite struct LogFailureTests {
    @Test func aSymlinkPlantedAtTheLogIsRefusedByPrepareAndBySpawn() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let target = directory.appending(path: "elsewhere")
        let log = directory.appending(path: "x.log")
        try FileManager.default.createSymbolicLink(at: log, withDestinationURL: target)
        #expect(throws: ServerLogError("open", log.path(percentEncoded: false), code: ELOOP)) {
            try ServerLog.prepare(log)
        }
        #expect(throws: SpawnError.log(path: log.path(percentEncoded: false), code: ELOOP)) {
            try SpawnedProcess(LaunchSpec(executable: "/usr/bin/true", logURL: log))
        }
        #expect(!FileManager.default.fileExists(atPath: target.path))
    }

    @Test func aLogThatCannotBeCreatedFailsTheLaunchWithItsReason() async throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let blocker = directory.appending(path: "Logs")
        try Data().write(to: blocker)  // a file where the log folder should be
        let log = blocker.appending(path: "x.log")
        let subject = ServerSupervisor(
            spec: LaunchSpec(executable: "/usr/bin/true", logURL: log), launch: CLIServeLaunch(),
            makeProcess: { spec in
                if let url = spec.logURL { try ServerLog.prepare(url) }
                return try SpawnedProcess(spec)
            })
        var events: [String] = []
        subject.onEvent = { events.append($0) }
        await subject.start()
        guard case .failed(let failure) = subject.state else {
            Issue.record("expected a failure, got \(subject.state)")
            return
        }
        #expect(failure.summary.contains("could not create the server log \(blocker.path(percentEncoded: false))"))
        #expect(events.count == 1)
        #expect(events.first?.hasPrefix("could not start /usr/bin/true: could not create the server log") == true)
    }

    @Test func anAppendThatFailsThrowsWithThePath() {
        let log = URL(filePath: "/nonexistent-\(UUID().uuidString)/x.log")
        #expect(throws: ServerLogError("append to", log.path(percentEncoded: false), code: ENOENT)) {
            try ServerLog.append("started pid 7", to: log)
        }
    }

    @Test func aFailedLogWriteIsReportedOnceAndEndsTheLog() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let path = directory.appending(path: "x.log").path(percentEncoded: false)
        FileManager.default.createFile(atPath: path, contents: nil)
        let readOnly = try #require(FileHandle(forReadingAtPath: path))  // every write fails
        let log = ChildLog(path: path, handle: readOnly, start: 0)
        log.append(Data("one\n".utf8))
        log.append(Data("two\n".utf8))
        let shown = try log.recentLines(limit: 10)
        #expect(shown.count == 1)
        #expect(shown.first?.hasPrefix("could not write the server log, so it ends here: ") == true)
    }
}
