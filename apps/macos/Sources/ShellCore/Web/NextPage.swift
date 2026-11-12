/// Which page a folder window loads next, and which it saves for the next launch.
///
/// A requested page (a file opened in the window, or a restored tab's page) is kept
/// apart from the page the window last showed, which a server restart or a discarded tab
/// remembers from the old web view. The request wins until it is loaded: the old view
/// still holds the page shown before, and remembering it must not undo a newer request.
public nonisolated struct NextPage: Equatable, Sendable {
    /// Asked for and not loaded yet.
    public private(set) var requested: PageAddress?
    /// Shown before a restart or a discard.
    public private(set) var shown: PageAddress?

    public init(requested: PageAddress? = nil) {
        self.requested = requested
    }

    public mutating func request(_ page: PageAddress) {
        requested = page
    }

    /// The page the web view showed, as a restart or a discard finds it.
    public mutating func remember(shown page: PageAddress) {
        shown = page
    }

    /// The page to save, given the one the web view shows now, if any.
    public func saved(showing current: PageAddress?) -> PageAddress? {
        requested ?? current ?? shown
    }

    /// The page to load now, which forgets both.
    public mutating func take() -> PageAddress? {
        defer {
            requested = nil
            shown = nil
        }
        return requested ?? shown
    }
}
