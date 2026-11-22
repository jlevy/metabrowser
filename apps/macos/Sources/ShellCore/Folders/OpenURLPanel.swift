import Foundation

/// What File > Open URL… takes: a GitHub URL, which the panel hands to `metab` only once
/// `GitHubLink` accepts it, the check every link sent to the app passes first.
///
/// The panel writes GitHub URLs without `https://` and bare `owner/repo` shortcuts in
/// full before checking them (`corrected(_:)`). It passes the full URL to `metab`
/// because `metab TARGET --present --dry-run` reads bare `owner/repo` as a local path.
/// Other text without a scheme is refused. Every other problem here is one `metab`
/// would refuse as well (`insecure_http`,
/// `credentials_in_url`, `unsupported_source`, `control_or_whitespace`, `non_ascii`,
/// `backslash`, `invalid_percent_encoding`); the panel says it first, in its own words,
/// since `metab`'s answer for another site is about the command line's `--present`.
///
/// The path, query, and fragment are encoded as a browser sends them, so the panel opens
/// what `metab URL` opens, a file named with a space or a letter outside ASCII among
/// them: the GitHub reducer, in `src/metabrowser/builtin_plugins/github/urls.py`, takes
/// the same characters raw (`_common_checks`), encodes them (`_browser_encoded`, and its
/// handoff for ASCII), and gives either spelling the same plan, which
/// `LiveMetabTests.thePanelSendsWhatMetabOpensAsTyped` checks.
public nonisolated enum OpenURLEntry {
    public enum Problem: Error, Equatable, Sendable {
        /// Nothing but white space.
        case empty
        /// Longer than `GitHubLink.maximumLength`, as typed or once encoded.
        case tooLong
        /// No scheme and no GitHub URL or repository shortcut that `corrected(_:)` can expand.
        case notAFullURL
        /// A scheme other than `https`.
        case notHTTPS
        /// A user name or a password before the host.
        case credentials
        /// A port, other than 443, after the host.
        case port
        /// A host other than GitHub's.
        case notGitHub
        /// A character after the host that no URL holds raw and the panel does not encode:
        /// a control character, a backslash, or a character outside ASCII that may not
        /// show as itself (`OpenURLEntry.shows`).
        case character(Unicode.Scalar)
        /// A `%` that does not begin an escape such as `%20`.
        case percent
        /// Not a URL the app takes in any other way.
        case notAURL

        /// What the panel says under the field.
        public var message: String {
            switch self {
            case .empty:
                "Enter a GitHub URL."
            case .tooLong:
                "This URL is longer than Metabrowser opens."
            case .notAFullURL:
                "Enter a GitHub URL or an owner/repo shortcut."
            case .notHTTPS:
                "Metabrowser opens only https URLs, such as https://github.com/owner/repo."
            case .credentials:
                "This URL has a user name or password in it. Remove it, and the @ after it."
            case .port:
                "This URL names a port. Remove it: Metabrowser opens GitHub on its usual port."
            case .notGitHub:
                "Metabrowser opens only GitHub URLs: a repository, a pull request, a commit, or a file or folder on github.com."
            case .character("\\"):
                "This URL has a backslash in it. A URL separates its parts with /."
            case .character(let scalar) where scalar.properties.generalCategory == .control:
                "This URL has \(OpenURLEntry.codePoint(scalar)) in it, a control character such as a tab or a line break. Remove it."
            case .character(let scalar):
                "This URL has \(OpenURLEntry.codePoint(scalar)) in it, a character that may not show as itself. If it belongs in the URL, write it as \(OpenURLEntry.escaped(scalar))."
            case .percent:
                "This URL has a % that does not begin an escape such as %20. Write a % that belongs in the URL as %25."
            case .notAURL:
                "This is not a URL Metabrowser can open."
            }
        }
    }

    /// `text` without the white space around it, as a paste brings it.
    public static func trimmed(_ text: String) -> String {
        text.trimmingCharacters(in: .whitespacesAndNewlines)
    }

    /// `text`, trimmed and expanded when it is a GitHub URL or a repository shortcut.
    /// The app checks the result as it would a full URL.
    ///
    /// - `github.com/owner/repo`: no scheme, and a GitHub host (`GitHubLink.hosts`, in any
    ///   letter case) before the first `/`, `?`, or `#`, gets `https://`.
    /// - `http://github.com/owner/repo` becomes `https://`, which is all GitHub serves.
    /// - `//github.com/owner/repo`, a URL with its scheme left out, gets `https:`.
    /// - `owner/repo` gets `https://github.com/` if it matches the repository URL grammar.
    ///
    /// The panel shows the corrected text in its field (`OpenURLPanel.open()`).
    public static func corrected(_ text: String) -> String {
        let text = trimmed(text)
        if let scheme = text.firstMatch(of: schemePattern)?.output.1 {
            guard scheme.lowercased() == "http", startsWithGitHubHost(text.dropFirst(scheme.count + 3)) else {
                return text
            }
            return "https" + text.dropFirst(scheme.count)
        }
        if text.hasPrefix("//") {
            return startsWithGitHubHost(text.dropFirst(2)) ? "https:" + text : text
        }
        if startsWithGitHubHost(text[...]) { return "https://" + text }
        let repository = "https://github.com/" + text
        return PresentPlan.repositoryURL(repository) != nil ? repository : text
    }

    /// Whether `rest`, a URL after its `scheme://`, or text with none, begins with a GitHub
    /// host and nothing else before its path, query, or fragment.
    private static func startsWithGitHubHost(_ rest: Substring) -> Bool {
        GitHubLink.hosts.contains(rest.prefix { !"/?#".contains($0) }.lowercased())
    }

    /// The link `text` names, written in full (`corrected(_:)`), if `GitHubLink` accepts
    /// it, else why not. The scheme and the host are checked as typed; the rest is encoded
    /// as a browser sends it (`encoded(_:)`), and that encoded text is the link `metab` is
    /// given.
    public static func link(_ text: String) -> Result<URL, Problem> {
        let text = corrected(text)
        if text.isEmpty { return .failure(.empty) }
        if text.utf8.count > GitHubLink.maximumLength { return .failure(.tooLong) }
        guard let scheme = text.firstMatch(of: schemePattern)?.output.1 else { return .failure(.notAFullURL) }
        guard scheme.lowercased() == "https" else { return .failure(.notHTTPS) }
        let authority = text.dropFirst(scheme.count + 3).prefix { !"/?#".contains($0) }
        if authority.contains("@") { return .failure(.credentials) }
        var host = authority
        // A bracketed host is an address, whose colons are its own; it is not GitHub's.
        if !authority.hasPrefix("["), let colon = authority.lastIndex(of: ":") {
            if authority[authority.index(after: colon)...] != "443" { return .failure(.port) }
            host = authority[..<colon]
        }
        guard GitHubLink.hosts.contains(host.lowercased()) else { return .failure(.notGitHub) }
        let rest: String
        switch encoded(text[authority.endIndex...]) {
        case .success(let encoded): rest = encoded
        case .failure(let problem): return .failure(problem)
        }
        let link = String(text[..<authority.endIndex]) + rest
        if link.utf8.count > GitHubLink.maximumLength { return .failure(.tooLong) }
        guard let url = URL(string: link, encodingInvalidCharacters: false), GitHubLink.accepts(url) else {
            return .failure(.notAURL)
        }
        return .success(url)
    }

    /// The path, query, and fragment as a browser sends them, which is how `metab`'s GitHub
    /// reducer reads them: a space, an ASCII character a URL cannot hold raw, a second
    /// `#`, and a character outside ASCII that shows as itself, each percent-encoded as
    /// UTF-8. A valid escape such as `%20` is kept as it is. A control character, a
    /// backslash, a stray `%`, and a character that may not show are refused, as `metab`
    /// refuses them.
    static func encoded(_ rest: Substring) -> Result<String, Problem> {
        let scalars = Array(rest.unicodeScalars)
        var result = String.UnicodeScalarView()
        var inFragment = false
        for (index, scalar) in scalars.enumerated() {
            switch scalar {
            case "%":
                let escape = scalars.dropFirst(index + 1).prefix(2)
                guard escape.count == 2, escape.allSatisfy(\.properties.isASCIIHexDigit) else {
                    return .failure(.percent)
                }
                result.append(scalar)
            case "\\":
                return .failure(.character(scalar))
            case "#":
                // A URL has one fragment; a browser sends a later # as part of it.
                if inFragment {
                    result.append(contentsOf: escaped(scalar).unicodeScalars)
                } else {
                    inFragment = true
                    result.append(scalar)
                }
            case _ where scalar.properties.generalCategory == .control:
                return .failure(.character(scalar))
            case _ where scalar.isASCII:
                if rawASCIIEncoded.contains(scalar) {
                    result.append(contentsOf: escaped(scalar).unicodeScalars)
                } else {
                    result.append(scalar)
                }
            case _ where shows(scalars, at: index):
                result.append(contentsOf: escaped(scalar).unicodeScalars)
            default:
                return .failure(.character(scalar))
            }
        }
        return .success(String(result))
    }

    /// The printable ASCII characters a URL cannot hold raw (RFC 3986), and which a browser
    /// and `metab` encode: the space, `"`, `<`, `>`, `[`, `]`, `^`, `` ` ``, `{`, `|`,
    /// and `}`. The backslash, which `metab` refuses, and `%` and `#`, which have their
    /// own rules, are not here.
    private static let rawASCIIEncoded: Set<Unicode.Scalar> = [" ", "\"", "<", ">", "[", "]", "^", "`", "{", "|", "}"]

    /// Whether the character outside ASCII at `index` shows as itself, as `metab`'s
    /// `hidden_at`, in `src/metabrowser/invisible_chars.py`, decides it: a letter, mark,
    /// number, punctuation, or symbol, other than a default-ignorable code point, such as
    /// U+3164 HANGUL FILLER, and U+2800, the blank braille cell. A variation selector shows
    /// only on a base: after such a character, or as an emoji keycap after a digit, `#`,
    /// or `*`, with U+20E3 after it. Swift's own Unicode data decides each property, so a
    /// character newer than the data of one side or the other can be judged apart.
    static func shows(_ scalars: [Unicode.Scalar], at index: Int) -> Bool {
        let scalar = scalars[index]
        guard scalar.properties.isVariationSelector else { return showsAlone(scalar) }
        guard index > 0 else { return false }
        let base = scalars[index - 1]
        if base.isASCII {
            return "#*0123456789".unicodeScalars.contains(base)
                && index + 1 < scalars.count && scalars[index + 1] == "\u{20E3}"
        }
        return showsAlone(base)
    }

    private static func showsAlone(_ scalar: Unicode.Scalar) -> Bool {
        let properties = scalar.properties
        guard !scalar.isASCII, !properties.isVariationSelector, !properties.isDefaultIgnorableCodePoint,
              scalar != "\u{2800}"
        else { return false }
        switch properties.generalCategory {
        case .uppercaseLetter, .lowercaseLetter, .titlecaseLetter, .modifierLetter, .otherLetter,
             .nonspacingMark, .spacingMark, .enclosingMark,
             .decimalNumber, .letterNumber, .otherNumber,
             .connectorPunctuation, .dashPunctuation, .openPunctuation, .closePunctuation,
             .initialPunctuation, .finalPunctuation, .otherPunctuation,
             .mathSymbol, .currencySymbol, .modifierSymbol, .otherSymbol:
            return true
        default:
            return false
        }
    }

    /// `scalar` percent-encoded as UTF-8, as a browser sends it: `%C3%A9` for é.
    static func escaped(_ scalar: Unicode.Scalar) -> String {
        let digits = Array("0123456789ABCDEF")
        return String(scalar).utf8.map { "%\(digits[Int($0 >> 4)])\(digits[Int($0 & 0xF)])" }.joined()
    }

    /// `U+3164`: how `metab`'s refusals name a code point.
    static func codePoint(_ scalar: Unicode.Scalar) -> String {
        let hex = String(scalar.value, radix: 16, uppercase: true)
        return "U+" + String(repeating: "0", count: max(0, 4 - hex.count)) + hex
    }

    /// A scheme, as RFC 3986 spells one, and `://`.
    nonisolated(unsafe) private static let schemePattern = #/^([A-Za-z][A-Za-z0-9+.-]*):\/\//#
}

/// File > Open URL…: one field for a GitHub URL, and what pressing Open, editing, and
/// Cancel do (`OpenURLWindowController` shows it).
///
/// Open checks the text (`OpenURLEntry`) and asks `metab` about the link with the command
/// every link sent to the app is resolved with, `metab LINK --present --dry-run --format
/// json` (`PresentDryRun`). A plan closes the panel, and the app opens it as it opens such
/// a link (`AppDelegate.open(_:with:)`): in the repository's mirror, always, never a
/// checkout of it, as The File Menu in `docs/project/architecture/arch-open-modes.md`
/// designs it. A problem with the text, a refusal, or an answer the app cannot read is
/// said under the field, and the panel stays open so the text can be fixed. An edit
/// while `metab` is asked drops its answer, and so do Cancel and closing the panel:
/// each returns the link it stopped awaiting, whose dry run the app then stops, so the
/// panel's dry runs run one at a time.
public nonisolated struct OpenURLPanel: Equatable, Sendable {
    public enum Phase: Equatable, Sendable {
        /// The field takes text, and Open checks it.
        case editing
        /// `metab` is asked about this link.
        case checking(URL)
        /// It opened a plan, handed its link on, or was cancelled: nothing more happens.
        case closed
    }

    /// The field's text: as typed, until Open writes a GitHub URL in full
    /// (`OpenURLEntry.corrected(_:)`), which the window then shows in the field.
    public private(set) var text = ""
    public private(set) var phase = Phase.editing
    /// Why the text was not opened, said under the field until the next edit.
    public private(set) var message: String?

    public init() {}

    /// Whether Open does anything: some text, and no answer awaited.
    public var canOpen: Bool { phase == .editing && !OpenURLEntry.trimmed(text).isEmpty }

    public var isChecking: Bool { awaited != nil }

    /// The link `metab` is asked about, whose answer the panel awaits.
    public var awaited: URL? {
        if case .checking(let link) = phase { return link }
        return nil
    }

    /// The field now holds `newText`. Any message goes, and an answer awaited is dropped:
    /// the link it was for, whose dry run the app stops, or nil if none was awaited.
    @discardableResult
    public mutating func edit(_ newText: String) -> URL? {
        guard phase != .closed, newText != text else { return nil }
        let dropped = awaited
        text = newText
        message = nil
        phase = .editing
        return dropped
    }

    /// Open was pressed: the link to ask `metab` about, which the panel now awaits, or nil,
    /// with `message` saying why the text is not one. Text that is plainly a GitHub URL is
    /// first written in full, with no message: the field shows the URL that is checked.
    public mutating func open() -> URL? {
        guard canOpen else { return nil }
        let corrected = OpenURLEntry.corrected(text)
        if corrected != OpenURLEntry.trimmed(text) { text = corrected }
        switch OpenURLEntry.link(text) {
        case .success(let link):
            phase = .checking(link)
            message = nil
            return link
        case .failure(let problem):
            message = problem.message
            return nil
        }
    }

    /// `metab` answered about `link`: the plan to open, which closes the panel, or nil.
    /// A refusal or an unreadable answer is said under the field; an answer the panel no
    /// longer awaits changes nothing. `metab` names the `metab` that answered.
    public mutating func answered(_ answer: PresentAnswer, for link: URL, metab: String) -> PresentPlan? {
        guard phase == .checking(link) else { return nil }
        switch answer {
        case .plan(let plan):
            phase = .closed
            return plan
        case .refused(let refusal):
            message = GitHubLink.shortened(refusal.message, to: PresentAnswer.shownLineLength)
        case .unreadable(let reason, _):
            // The output stays in the app's log: it can hold a traceback.
            message = "Metabrowser could not check this URL: \(metab) \(GitHubLink.shortened(reason, to: PresentAnswer.shownLineLength))."
        }
        phase = .editing
        return nil
    }

    /// The link being checked goes to the link queue instead, as when no `metab` can run
    /// now, which closes the panel: the queue waits for one, as it does for a link sent to
    /// the app.
    public mutating func handOff() -> URL? {
        guard case .checking(let link) = phase else { return nil }
        phase = .closed
        return link
    }

    /// Cancel, or the panel closed: nothing more happens. Returns the link whose answer was
    /// awaited, whose dry run the app stops, or nil if none was.
    @discardableResult
    public mutating func cancel() -> URL? {
        let dropped = awaited
        phase = .closed
        return dropped
    }
}
