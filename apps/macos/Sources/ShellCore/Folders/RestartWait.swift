/// Which of a repository's windows say that its restart waits at the launch gate while
/// the ready server serves the others (review D1 on #539).
///
/// A restart of a ready server keeps it serving until the restart has the gate
/// (`ServerSupervisor.restart`), which another repository's first clone can hold for
/// minutes. Meanwhile the window that asked for the restart shows the starting view,
/// which says it waits, instead of the old server's page, and the other windows serve on.
/// The window that asked is the one a link brought forward, the one File > Restart
/// Server or Command-R was chosen in, or, for a restart no window asked for, such as the
/// one an upgrade offers, the session's front window.
///
/// The supervisor says only when its first start or restart begins to wait
/// (`onGateWait`), so a restart asked for while another already waits shows its window
/// at once. Once the server's state changes, the restart has begun or the server has
/// failed, every window follows the state from then on, and the windows that asked are
/// forgotten.
public struct RestartWait<Window: AnyObject> {
    /// Whether a start or restart of the server waits at the gate.
    public private(set) var isWaiting = false
    /// The windows that asked for a restart of the ready server, each once.
    private var askers: [Asker] = []

    private struct Asker {
        weak var window: Window?
    }

    public init() {}

    /// A restart was asked for from `window` while the server is in `state`. Returns the
    /// window to show the starting view now: `window`, when the server is ready and a
    /// restart already waits; otherwise nil, and `gateWait` shows it if its restart comes
    /// to wait.
    public mutating func asked(from window: Window?, state: ServerState) -> Window? {
        guard let window, case .ready = state else { return nil }
        askers.removeAll { $0.window == nil || $0.window === window }
        askers.append(Asker(window: window))
        return isWaiting ? window : nil
    }

    /// The supervisor's `onGateWait`: the windows to show the starting view, which are those
    /// that asked for a restart of a server that is still ready.
    public mutating func gateWait(_ waiting: Bool, state: ServerState) -> [Window] {
        isWaiting = waiting
        guard waiting, case .ready = state else { return [] }
        return askers.compactMap(\.window)
    }

    /// The server's state changed: every window follows it now, so none is kept.
    public mutating func serverChanged() {
        askers.removeAll()
    }
}
