import Foundation

/// Where a folder the user opens appears: as a tab of the front folder window, or in a
/// window of its own. Every folder window shares one tabbing identifier, so macOS's own
/// Merge All Windows and tab dragging combine folders either way.
public nonisolated enum FolderPlacement: String, CaseIterable, Codable, Sendable {
    /// As System Settings > Desktop & Dock > "Prefer tabs when opening documents" says.
    case system
    case tabs
    case windows

    /// - Parameters:
    ///   - system: the System Settings choice, `NSWindow.userTabbingPreference`.
    ///   - front: the folder window the new folder would join, or nil if none is open.
    public func placement(system: SystemTabbing, front: FrontWindow?) -> NewWindowPlacement {
        guard let front else { return .window }
        switch self {
        case .tabs: return .tab
        case .windows: return .window
        case .system:
            switch system {
            case .always: return .tab
            case .inFullScreen: return front == .fullScreen ? .tab : .window
            case .never: return .window
            }
        }
    }
}

/// "Prefer tabs when opening documents" in System Settings.
public nonisolated enum SystemTabbing: Sendable {
    /// "Never" (`NSWindow.UserTabbingPreference.manual`).
    case never
    case always
    case inFullScreen
}

public nonisolated enum FrontWindow: Sendable {
    case window
    case fullScreen
}

public nonisolated enum NewWindowPlacement: Equatable, Sendable {
    case tab
    case window
}

/// The window preferences in Settings, saved in the app's user defaults.
public final class WindowPreferences {
    public static let placementKey = "newFolderPlacement"
    public static let restoreKey = "restoresLastSession"
    public static let defaultPlacement = FolderPlacement.system
    public static let defaultRestoresLastSession = true
    private let defaults: UserDefaults

    public init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    public var placement: FolderPlacement {
        get { defaults.string(forKey: Self.placementKey).flatMap(FolderPlacement.init) ?? Self.defaultPlacement }
        set { defaults.set(newValue.rawValue, forKey: Self.placementKey) }
    }

    /// Whether a launch reopens the folder windows open at the last quit.
    public var restoresLastSession: Bool {
        get { defaults.object(forKey: Self.restoreKey) as? Bool ?? Self.defaultRestoresLastSession }
        set { defaults.set(newValue, forKey: Self.restoreKey) }
    }
}
