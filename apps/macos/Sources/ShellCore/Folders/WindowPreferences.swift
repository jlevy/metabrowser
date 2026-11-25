import Foundation

/// The window preferences in Settings, saved in the app's user defaults.
///
/// Every folder opens in a window of its own, so where one goes is no preference: a
/// `newFolderPlacement` that an earlier build saved here is no longer read.
public final class WindowPreferences {
    public static let restoreKey = "restoresLastSession"
    public static let defaultRestoresLastSession = true
    private let defaults: UserDefaults

    public init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    /// Whether a launch reopens the folder windows open at the last quit.
    public var restoresLastSession: Bool {
        get { defaults.object(forKey: Self.restoreKey) as? Bool ?? Self.defaultRestoresLastSession }
        set { defaults.set(newValue, forKey: Self.restoreKey) }
    }
}
