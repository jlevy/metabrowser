/// Which page a folder window loads next, and which it saves for the next launch.
///
/// A requested page (a file opened in the window, or a restored tab's page) is kept
/// apart from the page the window last showed, which a server restart or a discarded tab
/// remembers from the old web view. The request wins until it is loaded: the old view
/// still holds the page shown before, and remembering it must not undo a newer request.
/// A request can also be for the server's entry page, as when a repository's server
/// starts again on a new link, whose entry page is the link's page: it wins over the
/// page the old server showed in the same way.
public nonisolated struct NextPage: Equatable, Sendable {
    /// Asked for and not loaded yet.
    public private(set) var requested: PageAddress?
    /// The server's entry page was asked for and not loaded yet.
    public private(set) var entryRequested = false
    /// Shown before a restart or a discard.
    public private(set) var shown: PageAddress?

    public init(requested: PageAddress? = nil) {
        self.requested = requested
    }

    public mutating func request(_ page: PageAddress) {
        requested = page
        entryRequested = false
    }

    /// Asks for the entry page of the server the window attaches to next.
    public mutating func requestEntry() {
        requested = nil
        entryRequested = true
    }

    /// The page the web view showed, as a restart or a discard finds it.
    public mutating func remember(shown page: PageAddress) {
        shown = page
    }

    /// The page to save, given the one the web view shows now, if any; nil, the entry
    /// page, while one was asked for.
    public func saved(showing current: PageAddress?) -> PageAddress? {
        entryRequested ? nil : requested ?? current ?? shown
    }

    /// The page to load now, nil for the entry page, which forgets what was asked for and
    /// shown.
    public mutating func take() -> PageAddress? {
        defer {
            requested = nil
            entryRequested = false
            shown = nil
        }
        return entryRequested ? nil : requested ?? shown
    }
}
