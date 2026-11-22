import Foundation

/// The project's pages on GitHub that the app opens: the repository from the title bar's
/// mark, its README from Help, and the README's installation section from setup.
public nonisolated enum ProjectLinks {
    // A literal that parses, as `ProjectLinksTests` checks.
    public static let repository = URL(string: "https://github.com/jlevy/metabrowser")!
    /// What the title bar's mark says to assistive apps, as a button that opens `repository`.
    public static let repositoryLabel = "Metabrowser on GitHub"

    public static var readme: URL { readmeSection("readme") }
    public static var installationGuide: URL { readmeSection("installation") }

    private static func readmeSection(_ fragment: String) -> URL {
        var components = URLComponents(url: repository, resolvingAgainstBaseURL: false)
        components?.fragment = fragment
        return components?.url ?? repository
    }
}
