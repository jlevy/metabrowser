/// The environment every child gets: built from an allowlist, never inherited whole.
///
/// A Finder launch has `PATH=/usr/bin:/bin:/usr/sbin:/sbin`, so `git` would resolve to
/// Apple's shim and `gh` would be missing. A Terminal launch would instead leak that
/// shell's `UV_*`, `VIRTUAL_ENV`, `PYTHONHOME`, and `PYTHONPATH` into the server. So
/// the child gets the directories of the tools resolved at setup, then a fixed system
/// `PATH`, and nothing from the parent beyond the names below.
public nonisolated enum ChildEnvironment {
    public static let systemPath = ["/usr/bin", "/bin", "/usr/sbin", "/sbin"]

    /// Identity, locale, temporary-directory, ssh-agent, and proxy names. Everything
    /// else is dropped. `metab` runs Git over ssh with `BatchMode`, so without the agent
    /// socket an ssh remote fails; Git and `gh` honor the proxy variables.
    public static let passedThrough: Set<String> = [
        "HOME", "USER", "LOGNAME", "TMPDIR", "LANG", "LC_ALL", "LC_CTYPE", "LC_MESSAGES",
        "TZ", "__CF_USER_TEXT_ENCODING", "SSH_AUTH_SOCK",
        "HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "ALL_PROXY",
        "http_proxy", "https_proxy", "no_proxy", "all_proxy",
        // An app started with it, as `make run` starts a development build, records no
        // recent target, and neither does any `metab` it runs.
        RecentTargets.recordVariable,
        // The configuration directory (`configuration_directory` in `metabrowser.home`),
        // which holds the recent targets and `config.yml`. An app started with one, as
        // the hand checks start a development build, keeps its list there: the `metab`
        // that records an open and the one that lists the menu read the same directory,
        // and the user's own list is left alone. The app has one only as it was launched:
        // by `open --env`, or from launchd's environment (`launchctl setenv`), which a
        // launch from Finder or the Dock gets too, never from a terminal's `export`.
        // Unset, as it usually is, every `metab` the app runs uses the default, which a
        // terminal's `metab` uses too.
        "METABROWSER_CONFIG_DIR",
        // The event log's location and off-switch (`metabrowser.event_log`): a server the
        // app starts logs where, and whether, the environment the app started with says.
        "METABROWSER_STATE_DIR", "XDG_STATE_HOME", "METABROWSER_EVENT_LOG",
    ]

    public static func build(inherited: [String: String], toolDirectories: [String]) -> [String: String] {
        var environment = inherited.filter { passedThrough.contains($0.key) }
        var path: [String] = []
        for directory in toolDirectories + systemPath
        where directory.hasPrefix("/") && !directory.contains(":") && !path.contains(directory) {
            path.append(directory)
        }
        environment["PATH"] = path.joined(separator: ":")
        // Packages in ~/.local/lib/python*/site-packages must not shadow the server's own.
        environment["PYTHONNOUSERSITE"] = "1"
        // The log should show what the server printed when it printed it.
        environment["PYTHONUNBUFFERED"] = "1"
        return environment
    }
}
