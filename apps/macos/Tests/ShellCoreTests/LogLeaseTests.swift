import Darwin
import Foundation
import os
import Testing
@testable import ShellCore

/// Two copies of the app running at once (a development build and a release, which share
/// `~/Library/Logs/Metabrowser/`, or development builds from two checkouts) can serve the
/// same folder at once. Each claims the folder's log for as long as it serves the folder,
/// and a copy that finds it claimed writes a log of its own, so neither error view shows
/// the other server's output. The claim is a `flock` on a file in that folder, so it
/// holds between copies whatever their bundles.
@Suite struct LogLeaseTests {
    private let root = URL(filePath: "/tmp/notes", directoryHint: .isDirectory)

    @Test func theFirstClaimGetsTheFoldersLogAndASecondGetsItsOwn() throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let shared = ServerLog.url(for: root, in: folder)
        var first: ServerLogLease? = try ServerLogLease.claim(for: root, in: folder, owner: 100)
        #expect(first?.url == shared)
        let second = try ServerLogLease.claim(for: root, in: folder, owner: 200)
        #expect(second.url != shared)
        #expect(second.url.lastPathComponent == shared.deletingPathExtension().lastPathComponent + ".app-200.log")
        #expect(second.url.deletingLastPathComponent() == shared.deletingLastPathComponent())
        first = nil  // that copy stopped serving the folder
        let third = try ServerLogLease.claim(for: root, in: folder, owner: 300)
        #expect(third.url == shared)
        withExtendedLifetime(second) {}
    }

    /// Review E2 on #363: one copy can hold several claims on a folder's log at once, since
    /// a session whose last window closed keeps its claim until its server has stopped,
    /// and the folder can be opened again before then. The claim tried only the folder's
    /// log and one named for the copy, so a third failed. Each claim now gets a log of its
    /// own, and a name let go is used again.
    @Test func overlappingClaimsOfOneCopyEachGetALogOfTheirOwn() throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let shared = ServerLog.url(for: root, in: folder)
        let stem = shared.deletingPathExtension().lastPathComponent
        var claims: [ServerLogLease?] = try (0..<3).map { _ in
            try ServerLogLease.claim(for: root, in: folder, owner: 100)
        }
        #expect(
            claims.map { $0?.url.lastPathComponent }
                == [shared.lastPathComponent, "\(stem).app-100.log", "\(stem).app-100-2.log"])
        #expect(Set(claims.map { $0?.url.deletingLastPathComponent() }) == [shared.deletingLastPathComponent()])
        claims[1] = nil  // that session's server stopped
        let next = try ServerLogLease.claim(for: root, in: folder, owner: 100)
        #expect(next.url.lastPathComponent == "\(stem).app-100.log")
        withExtendedLifetime(claims) {}
    }

    /// mb-kaps: a lease that only closed its lock file left the lock held while any child
    /// was between `posix_spawn` copying this process's descriptors and its exec closing
    /// them, since a `flock` lasts until the last descriptor on its open file closes. A
    /// claim made in that window found the log of a session that had gone still held. In
    /// CI the children were other suites', running in parallel; here they are this test's
    /// own, and enough of them that a lease closing without unlocking fails it: in three
    /// runs without the unlock, 9, 32, and 38 claims found the log held.
    @Test func spawningAChildDoesNotKeepAReleasedClaimHeld() throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let shared = ServerLog.url(for: root, in: folder)
        let spawned = OSAllocatedUnfairLock(initialState: 0)
        let stop = OSAllocatedUnfairLock(initialState: false)
        let spawners = (0..<4).map { _ in
            let thread = Thread {
                while !stop.withLock({ $0 }) {
                    var attr: posix_spawnattr_t?
                    posix_spawnattr_init(&attr)
                    posix_spawnattr_setflags(&attr, Int16(POSIX_SPAWN_CLOEXEC_DEFAULT))
                    let argv = [strdup("/usr/bin/true"), nil]
                    var pid: pid_t = 0
                    if posix_spawn(&pid, "/usr/bin/true", nil, &attr, argv, nil) == 0 {
                        var status: Int32 = 0
                        waitpid(pid, &status, 0)
                    }
                    free(argv[0])
                    posix_spawnattr_destroy(&attr)
                    spawned.withLock { $0 += 1 }
                }
            }
            thread.start()
            return thread
        }
        defer {
            stop.withLock { $0 = true }
            while spawners.contains(where: { !$0.isFinished }) { usleep(1000) }
        }
        var heldAfterRelease = 0
        while spawned.withLock({ $0 }) < 600 {
            var lease: ServerLogLease? = try ServerLogLease.claim(for: root, in: folder, owner: 100)
            #expect(lease?.url == shared)
            lease = nil  // that session stopped serving the folder
            if try ServerLogLease.claim(for: root, in: folder, owner: 200).url != shared { heldAfterRelease += 1 }
        }
        #expect(heldAfterRelease == 0)
    }

    /// The names one copy tries are bounded: with every one held, the claim fails, and the
    /// launch with it, rather than search on.
    @Test func aCopyHoldingEveryNameItMayUseIsRefused() throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let held = try (0...ServerLogLease.ownLogLimit).map { _ in
            try ServerLogLease.claim(for: root, in: folder, owner: 100)
        }
        #expect(Set(held.map(\.url)).count == held.count)
        #expect(throws: ServerLogError.self) {
            try ServerLogLease.claim(for: root, in: folder, owner: 100)
        }
        withExtendedLifetime(held) {}
    }

    @Test func eachCopysRecentOutputIsItsOwn() async throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let leases = try [100, 200].map { try ServerLogLease.claim(for: root, in: folder, owner: pid_t($0)) }
        let children = try leases.enumerated().map { index, lease in
            try ServerLog.prepare(lease.url)
            return try SpawnedProcess(LaunchSpec(
                executable: "/bin/sh", arguments: ["-c", "echo up; echo 'Traceback from copy \(index)' >&2; read wait"],
                logURL: lease.url))
        }
        for child in children {
            for await line in child.lines where line == "up" { break }
        }
        for (index, child) in children.enumerated() {
            #expect(await eventually { child.recentOutput().count == 2 })
            #expect(Set(child.recentOutput()) == ["up", "Traceback from copy \(index)"])
            child.closeLifeline()
            _ = await child.waitForExit()
            child.release()
        }
    }

    @Test func aFolderThatCannotHoldTheLogIsReported() throws {
        let folder = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: folder) }
        let blocker = folder.appending(path: "Logs")
        try Data().write(to: blocker)
        #expect(throws: ServerLogError.self) {
            try ServerLogLease.claim(for: root, in: blocker, owner: 100)
        }
    }
}
