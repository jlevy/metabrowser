import Darwin
import Foundation
import Testing
@testable import ShellCore

/// A server's stderr goes straight to its log, so a stalled app cannot block the server
/// through a full pipe; stdout stays a pipe, for the announcement. The error view reads
/// this child's part of the log, so it still shows both.
@Suite struct ServerOutputTests {
    private func lines(of child: SpawnedProcess) async -> [String] {
        var seen: [String] = []
        for await line in child.lines { seen.append(line) }
        return seen
    }

    private func log(in directory: URL) -> URL { directory.appending(path: "server.log") }

    @Test func withALogStderrIsTheLogFileAndStdoutIsAPipe() async throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let script = #"[ -p /dev/fd/1 ] && echo "stdout pipe"; [ -p /dev/fd/2 ] || echo "stderr file" >&2"#
        let child = try SpawnedProcess(LaunchSpec(executable: "/bin/sh", arguments: ["-c", script], logURL: log(in: directory)))
        #expect(await lines(of: child) == ["stdout pipe"])
        #expect(await child.waitForExit() == 0)
        let written = try String(contentsOf: log(in: directory), encoding: .utf8)
        #expect(written.split(separator: "\n").sorted() == ["stderr file", "stdout pipe"])
        child.release()
    }

    @Test func withoutALogStderrJoinsStdoutOnThePipe() async throws {
        let child = try SpawnedProcess(LaunchSpec(executable: "/bin/sh", arguments: ["-c", "echo out; echo err >&2"]))
        #expect(await lines(of: child) == ["out", "err"])
        #expect(child.recentOutput() == ["out", "err"])
        child.release()
    }

    @Test func recentOutputIsThisChildsOutputFromTheLogWithoutTheAppsLines() async throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let url = log(in: directory)
        try Data("an earlier run\n".utf8).write(to: url)
        let child = try SpawnedProcess(LaunchSpec(
            executable: "/bin/sh", arguments: ["-c", "echo announced; echo 'Traceback: boom' >&2; read wait"],
            logURL: url))
        for await line in child.lines where line == "announced" { break }
        try ServerLog.append("stopping pid \(child.pid)", to: url)
        #expect(await eventually { child.recentOutput().count == 2 })
        #expect(Set(child.recentOutput()) == ["announced", "Traceback: boom"])
        child.closeLifeline()
        _ = await child.waitForExit()
        child.release()
    }

    @Test func aFailedLogWriteIsShownWithTheRecentOutput() async throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let url = log(in: directory)
        let child = try SpawnedProcess(LaunchSpec(executable: "/bin/sh", arguments: ["-c", "echo one"], logURL: url))
        _ = await lines(of: child)
        child.noteLogFailure("could not write the server log, so it ends here: disk full")
        #expect(child.recentOutput() == ["one", "could not write the server log, so it ends here: disk full"])
        child.release()
    }
}

@Suite struct LogSegmentTests {
    private func segment(_ text: String, truncated: Bool = false, limit: Int = 10) -> [String] {
        ServerLog.recentLines(in: Data(text.utf8), truncated: truncated, limit: limit)
    }

    @Test func splitsLinesAndKeepsAnUnterminatedLast() {
        #expect(segment("a\nb\r\nc") == ["a", "b", "c"])
        #expect(segment("a\nb\n") == ["a", "b"])
        #expect(segment("") == [])
    }

    @Test func dropsTheAppsOwnLines() {
        #expect(segment("a\n\(ServerLog.appLinePrefix)2026-11-11T00:00:00Z] stopping\nb\n") == ["a", "b"])
    }

    @Test func aCutSegmentDropsItsPartialFirstLine() {
        #expect(segment("tail of a line\nb\nc\n", truncated: true) == ["b", "c"])
    }

    @Test func keepsTheNewestLines() {
        #expect(segment("1\n2\n3\n4\n", limit: 2) == ["3", "4"])
    }
}
