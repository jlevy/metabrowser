import Foundation

/// The project's pages on GitHub that the app opens: the repository from the title bar's
/// mark, its README from Help, and the installation guide from the setup steps.
public nonisolated enum ProjectLinks {
    // A literal that parses, as `ProjectLinksTests` checks.
    public static let repository = URL(string: "https://github.com/jlevy/metabrowser")!
    /// What the title bar's mark says to assistive apps, as a button that opens `repository`.
    public static let repositoryLabel = "Metabrowser on GitHub"

    public static var readme: URL {
        var components = URLComponents(url: repository, resolvingAgainstBaseURL: false)
        components?.fragment = "readme"
        return components?.url ?? repository
    }

    public static var installationGuide: URL { repository.appending(path: "blob/main/docs/installation.md") }
}
