import Darwin
import Foundation

/// What a short command printed and how it ended.
public nonisolated struct CommandResult: Equatable, Sendable {
    /// The wait status, or nil if the command could not start or was killed at its
    /// deadline.
    public var status: Int32?
    public var output: [String]
    public var timedOut: Bool
    public var launchError: String?

    public init(status: Int32?, output: [String], timedOut: Bool = false, launchError: String? = nil) {
        self.status = status
        self.output = output
        self.timedOut = timedOut
        self.launchError = launchError
    }

    public var succeeded: Bool { status.map { ExitStatus(waitStatus: $0) == .exited(0) } ?? false }
}

/// Runs short commands (`metab --version`, `metab --doctor`, a login shell) with a
/// deadline, through the same `posix_spawn` path as servers: stdin at EOF, its own
/// process group, and that whole group killed when it ends or times out.
public nonisolated enum CommandRunner {
    public typealias Run = @Sendable (LaunchSpec, Duration) async -> CommandResult

    public static let live: Run = { spec, limit in await run(spec, timeout: limit) }

    public static func run(_ spec: LaunchSpec, timeout: Duration) async -> CommandResult {
        var spec = spec
        spec.closesStdin = true
        spec.tailLimit = max(spec.tailLimit, 5_000)
        let child: SpawnedProcess
        do {
            child = try SpawnedProcess(spec)
        } catch {
            return CommandResult(status: nil, output: [], launchError: error.description)
        }
        var status = await firstResult(within: timeout, of: [{ @Sendable in await child.waitForExit() }])
        let timedOut = status == nil
        if timedOut {
            child.signalGroup(SIGKILL)
            status = await child.waitForExit()
        }
        // A background job the command started can hold the pipe open; take what has
        // arrived, then end the job with the rest of the group.
        _ = await firstResult(within: .milliseconds(300), of: [{ @Sendable in await child.waitForOutputEnd() }])
        child.signalGroup(SIGKILL)
        return CommandResult(status: timedOut ? nil : status, output: child.recentOutput(), timedOut: timedOut)
    }
}
