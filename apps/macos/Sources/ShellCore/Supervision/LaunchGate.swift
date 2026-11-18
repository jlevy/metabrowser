/// Lets one of the servers that share it start at a time.
///
/// `metab` picks its port by probing for the first free one and binds it later, so two
/// servers starting together can choose the same port, and the second then fails to
/// bind. Holding this gate from spawn until ready (or failed) means each port walk sees
/// the ports bound before it. The app holds one for folders and one for repositories,
/// whose walks cover ports apart (`CLIServeLaunch.repositoryBasePort`), so a first clone
/// holds up no folder. Remove them once host mode binds port 0.
public final class LaunchGate {
    private var held = false
    private var waiters: [CheckedContinuation<Void, Never>] = []

    public init() {}

    public func acquire() async {
        guard held else {
            held = true
            return
        }
        await withCheckedContinuation { waiters.append($0) }
    }

    public func release() {
        if waiters.isEmpty {
            held = false
        } else {
            waiters.removeFirst().resume()  // ownership passes straight to the next waiter
        }
    }
}
