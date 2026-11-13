import Darwin
import Foundation
import os
import Testing
@testable import ShellCore

/// The last resort at exit: every group gets SIGTERM, the wait is shared and bounded,
/// and every group gets SIGKILL.
@Suite struct ExitSweepTests {
    /// Processes that exit a number of polls after SIGTERM (`never`: not at all), on a
    /// clock that advances only when the sweep sleeps.
    private final class Machine: Sendable {
        private struct State {
            var now = ContinuousClock.now
            var signals: [String] = []
            var pollsLeft: [pid_t: Int]
        }
        private let state: OSAllocatedUnfairLock<State>

        nonisolated static let never = Int.max

        init(_ pollsToExit: [pid_t: Int]) {
            state = OSAllocatedUnfairLock(initialState: State(pollsLeft: pollsToExit))
        }

        var signals: [String] { state.withLock { $0.signals } }

        var system: ExitSweep.System {
            ExitSweep.System(
                isRunning: { pid in self.state.withLock { ($0.pollsLeft[pid] ?? 0) > 0 } },
                signalGroup: { pid, signal in
                    self.state.withLock { $0.signals.append("\(signal == SIGKILL ? "KILL" : "TERM") -\(pid)") }
                },
                sleep: { duration in
                    self.state.withLock { state in
                        state.now = state.now.advanced(by: duration)
                        for (pid, left) in state.pollsLeft where left != Machine.never { state.pollsLeft[pid] = left - 1 }
                    }
                },
                now: { self.state.withLock { $0.now } })
        }
    }

    @Test func everyGroupIsSignaledOnceEachWayAndTheWaitStopsWhenAllHaveExited() {
        let machine = Machine([10: 1, 20: 3])
        let left = ExitSweep.end([10, 20], grace: .seconds(1), system: machine.system)
        #expect(left.isEmpty)
        #expect(machine.signals == ["TERM -10", "TERM -20", "KILL -10", "KILL -20"])
    }

    @Test func aChildThatIgnoresTermIsKilledAtTheDeadline() {
        let machine = Machine([10: 1, 20: Machine.never])
        let left = ExitSweep.end([10, 20], grace: .milliseconds(200), system: machine.system)
        #expect(left == [20])
        #expect(machine.signals.suffix(2) == ["KILL -10", "KILL -20"])
    }

    @Test func nothingToSweepSignalsNothing() {
        let machine = Machine([:])
        #expect(ExitSweep.end([], system: machine.system).isEmpty)
        #expect(machine.signals.isEmpty)
    }

    @Test func aRealChildThatIgnoresTermIsKilled() async throws {
        let child = try SpawnedProcess(LaunchSpec(executable: "/bin/sh", arguments: ["-c", "trap '' TERM; echo up; sleep 30"]))
        for await _ in child.lines { break }  // the trap is set
        #expect(ExitSweep.isRunningChild(child.pid))
        #expect(ExitSweep.end([child.pid], grace: .milliseconds(200)) == [child.pid])
        let status = try #require(await child.waitForExit())
        #expect(ExitStatus(waitStatus: status) == .signaled(SIGKILL))
        #expect(!ExitSweep.isRunningChild(child.pid))  // exited, though not yet reaped
        child.release()
    }
}
