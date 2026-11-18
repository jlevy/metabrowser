import Foundation

/// The window each folder waiting for a runtime was asked to open in, so it still opens
/// there once one is found. A recent folder chosen in a window's folder chooser shows in
/// that window, and a choice made while `metab` is checked again, as it is after every
/// upgrade, waits like any other request (`RuntimeSelection.setupForOpening`); without
/// its window it would open in a new one.
///
/// Each window is held weakly: one that closes while its folder waits leaves the folder
/// to open as a new folder does.
public struct WaitingWindows<Window: AnyObject> {
    private struct Held {
        weak var window: Window?
    }

    /// By the URL a folder waits under in `RuntimeSelection.waitingFolders`.
    private var windows: [URL: Held] = [:]

    public init() {}

    /// `folder`, which is waiting for a runtime, was asked to open in `window`. A later
    /// request for the same folder names the window it opens in.
    public mutating func wait(_ folder: URL, in window: Window) {
        windows[folder] = Held(window: window)
    }

    /// The waiting folders, released together when a runtime is found, each with the
    /// window it was asked to open in if that window is still open, in the order given.
    /// Every window held is forgotten: no folder waits once they are released.
    public mutating func release(_ folders: [URL]) -> [(folder: URL, window: Window?)] {
        defer { windows.removeAll() }
        return folders.map { ($0, windows[$0]?.window) }
    }
}
