import Darwin

/// A server the app supervises, as quitting sees it.
public protocol ManagedServer: AnyObject {
    /// Stops every child, waiting until each has exited or been given up on.
    func stop() async
    /// Every child not yet reaped; each pid is also its process group id.
    var childPIDs: [pid_t] { get }
}

extension ServerSupervisor: ManagedServer {}

/// Every server the app started, open or still stopping, keyed by folder.
///
/// Closing a folder's last window retires its server, which keeps stopping in the
/// background. Quitting stops the open servers and also waits for the retired ones, so
/// the app never exits ahead of a server it started; `childPIDs` covers both for the
/// last-resort kill at exit. The app delegate owns one fleet, which is what makes its
/// quit ordering testable here.
///
/// It stores `any ManagedServer` rather than being generic: the generic version crashed
/// Swift 6.3.3's optimizer (signal 11 in EarlyPerfInliner on its deinit) in release
/// builds. Callers cast back to their own server type.
public final class ServerFleet {
    private var open: [String: any ManagedServer] = [:]
    private var stopping: [ObjectIdentifier: Stopping] = [:]

    private struct Stopping {
        let server: any ManagedServer
        let task: Task<Void, Never>
    }

    public init() {}

    public subscript(key: String) -> (any ManagedServer)? { open[key] }

    public var openServers: [any ManagedServer] { Array(open.values) }
    public var stoppingCount: Int { stopping.count }
    public var isEmpty: Bool { open.isEmpty && stopping.isEmpty }

    /// Every unreaped child of every server, open or stopping.
    public var childPIDs: [pid_t] {
        (Array(open.values) + stopping.values.map(\.server)).flatMap(\.childPIDs)
    }

    /// Adds `server` for `key`, retiring any server already there.
    public func insert(_ server: any ManagedServer, for key: String) {
        if let previous = open[key], previous !== server { retire(previous) }
        open[key] = server
    }

    /// Moves `server` from open to stopping and stops it in the background. A server
    /// that is not open (already retired, or replaced) is left alone.
    public func retire(_ server: any ManagedServer) {
        guard let key = open.first(where: { $0.value === server })?.key else { return }
        open[key] = nil
        let id = ObjectIdentifier(server)
        let task = Task {
            await server.stop()
            self.stopping[id] = nil
        }
        stopping[id] = Stopping(server: server, task: task)
    }

    /// Stops every open server and waits for every stopping one, all concurrently.
    public func stopAll() async {
        openServers.forEach(retire)
        while let next = stopping.values.first {
            await next.task.value
        }
    }
}
