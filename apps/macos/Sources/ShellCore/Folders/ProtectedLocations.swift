/// Where macOS's privacy system (TCC) asks the user, in the app's name, before the app's
/// server may read: the Desktop, Documents, and Downloads folders, iCloud Drive and other
/// cloud storage, other apps' data, and other volumes, removable and network ones among
/// them. The app's `Info.plist` declares a usage description for each.
public nonisolated enum ProtectedLocations {
    /// Below the home folder.
    static let homeFolders = [
        "Desktop", "Documents", "Downloads", "Library/Mobile Documents", "Library/CloudStorage",
        "Library/Containers", "Library/Group Containers",
    ]
    /// Where other volumes mount. An internal second volume asks nothing but mounts here
    /// too; treating it as protected only delays its server until its tab is selected.
    static let mountPoints = ["/Volumes", "/Network"]

    /// Whether serving `root` reads a protected location: `root` is one, is inside one,
    /// or holds one, as the home folder holds Documents. `root` and `home` are canonical.
    public static func contains(_ root: String, home: String) -> Bool {
        locations(home: home).contains { isWithin(root, $0) || isWithin($0, root) }
    }

    /// Whether `path` is a protected location or inside one, so that looking at it can
    /// raise the prompt. A folder that only holds one, such as the home folder, is not.
    public static func isInside(_ path: String, home: String) -> Bool {
        locations(home: home).contains { isWithin(path, $0) }
    }

    static func locations(home: String) -> [String] {
        homeFolders.map { home + "/" + $0 } + mountPoints
    }

    /// Whether `path` is `ancestor` or inside it.
    static func isWithin(_ path: String, _ ancestor: String) -> Bool {
        path == ancestor || path.hasPrefix(ancestor == "/" ? "/" : ancestor + "/")
    }
}
