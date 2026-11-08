import Foundation

/// The File > Open Recent list: newest first, no duplicates, bounded.
public nonisolated struct RecentFolders: Equatable, Sendable {
    public static let defaultLimit = 10
    public private(set) var paths: [String]
    public let limit: Int

    public init(paths: [String] = [], limit: Int = RecentFolders.defaultLimit) {
        self.limit = max(1, limit)
        self.paths = []
        for path in paths.reversed() { add(path) }
    }

    public mutating func add(_ path: String) {
        paths.removeAll { $0 == path }
        paths.insert(path, at: 0)
        if paths.count > limit { paths.removeLast(paths.count - limit) }
    }

    public mutating func remove(_ path: String) {
        paths.removeAll { $0 == path }
    }

    public mutating func clear() {
        paths.removeAll()
    }

    /// The entries that still exist, for the menu; missing ones stay in the list in
    /// case their volume comes back.
    public func existing(_ exists: (String) -> Bool = FileChecks.isDirectory) -> [String] {
        paths.filter(exists)
    }
}

/// Persists `RecentFolders` in user defaults.
public final class RecentFolderStore {
    static let key = "recentFolders"
    private let defaults: UserDefaults

    public init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    public var folders: RecentFolders {
        get { RecentFolders(paths: defaults.stringArray(forKey: Self.key) ?? []) }
        set { defaults.set(newValue.paths, forKey: Self.key) }
    }
}
