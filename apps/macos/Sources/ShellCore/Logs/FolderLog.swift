import Foundation

/// A folder's server log for one session of the folder: claimed with a `ServerLogLease` so
/// that a second running copy of the app serving the same folder, or an earlier session of
/// it whose server is still stopping, writes a log of its own.
///
/// No server launches into a log this app has not claimed. Each launch claims the log
/// if no claim holds yet, and a claim that fails fails the launch, so the window shows
/// why and Retry claims again. Falling back to the shared log instead would let two
/// copies mix their servers' output there, and each error view show the other's lines.
public final class FolderLog {
    public typealias Claim = (_ root: URL, _ directory: URL) throws -> ServerLogLease

    public let root: URL
    public let directory: URL
    private let claim: Claim
    /// Held from the first claim that succeeds until the folder's session ends.
    private var lease: ServerLogLease?

    public init(
        root: URL, directory: URL,
        claim: @escaping Claim = { root, directory in try ServerLogLease.claim(for: root, in: directory) }
    ) {
        self.root = root
        self.directory = directory
        self.claim = claim
    }

    /// Where this folder's server writes and its lifecycle events go: the claimed log, or
    /// before any claim has held, the folder's shared log, which only events reach.
    public var url: URL { lease?.url ?? ServerLog.url(for: root, in: directory) }

    /// Each launch's process factory: claims the log unless a claim holds, points the
    /// child's log at the claim whatever the spec said, prepares the log, and spawns.
    public func processFactory(
        _ spawn: @escaping ServerSupervisor.ProcessFactory = { try SpawnedProcess($0) }
    ) -> ServerSupervisor.ProcessFactory {
        { [self] spec in
            let lease = try self.lease ?? claim(root, directory)
            self.lease = lease
            var spec = spec
            spec.logURL = lease.url
            try ServerLog.prepare(lease.url)
            return try spawn(spec)
        }
    }
}
