import Darwin
import Foundation

/// The app's last resort as it exits, for any server child still running then, which
/// an orderly quit never leaves: SIGTERM to every child's group, one short wait for them
/// all, then SIGKILL to every group.
///
/// Each pid is an unreaped child of this app, so it is still its group's id. The caller
/// is exiting, so the wait blocks.
public nonisolated enum ExitSweep {
    /// Short, since an orderly quit already gave each server its full shutdown grace.
    public static let grace: Duration = .seconds(1)
    static let pollInterval: Duration = .milliseconds(50)

    /// What the sweep does to processes and time; tests substitute every field.
    public struct System: Sendable {
        public var isRunning: @Sendable (pid_t) -> Bool
        public var signalGroup: @Sendable (pid_t, Int32) -> Void
        public var sleep: @Sendable (Duration) -> Void
        public var now: @Sendable () -> ContinuousClock.Instant

        public static let live = System(
            isRunning: isRunningChild, signalGroup: { kill(-$0, $1) },
            sleep: { Thread.sleep(forTimeInterval: $0 / .seconds(1)) }, now: { ContinuousClock.now })
    }

    /// Returns the children still running when it sent SIGKILL.
    @discardableResult
    public static func end(_ pids: [pid_t], grace: Duration = grace, system: System = .live) -> [pid_t] {
        guard !pids.isEmpty else { return [] }
        pids.forEach { system.signalGroup($0, SIGTERM) }
        let deadline = system.now().advanced(by: grace)
        var running = pids.filter(system.isRunning)
        while !running.isEmpty, system.now() < deadline {
            system.sleep(pollInterval)
            running = running.filter(system.isRunning)
        }
        pids.forEach { system.signalGroup($0, SIGKILL) }
        return running
    }

    /// A child of this app that has not exited. `kill(pid, 0)` alone would count an
    /// exited, unreaped child as running, since its zombie keeps the pid.
    static func isRunningChild(_ pid: pid_t) -> Bool {
        var info = siginfo_t()
        let exited = waitid(P_PID, id_t(pid), &info, WEXITED | WNOHANG | WNOWAIT) == 0 && info.si_pid == pid
        return !exited && kill(pid, 0) == 0
    }
}
