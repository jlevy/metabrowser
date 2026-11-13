/// The page zoom View > Zoom In and Zoom Out step through, saved across launches.
public nonisolated enum PageZoom {
    /// Each Zoom In multiplies by this, and each Zoom Out divides by it, as Safari does.
    public static let step = 1.1
    /// Half size: smaller makes Metabrowser's text unreadable.
    public static let minimum = 0.5
    /// Triple size: larger leaves too little of a page in a window to be useful.
    public static let maximum = 3.0

    public static func zoomedIn(_ zoom: Double) -> Double { clamped(zoom * step) }
    public static func zoomedOut(_ zoom: Double) -> Double { clamped(zoom / step) }

    /// The zoom to start a window with, from the saved value: 1 when none is saved
    /// (user defaults answer 0) or it is not a usable number, else the saved value
    /// within the limits.
    public static func restored(_ saved: Double) -> Double {
        saved.isFinite && saved > 0 ? clamped(saved) : 1
    }

    static func clamped(_ zoom: Double) -> Double { min(maximum, max(minimum, zoom)) }
}
