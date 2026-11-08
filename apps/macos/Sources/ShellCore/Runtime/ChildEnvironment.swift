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
