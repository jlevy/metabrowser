import Foundation

/// The project's pages that the app opens: on GitHub, the repository from the title bar's
/// mark and the About panel, its README from Help, and the README's installation section
/// from setup; and the author's page, from the About panel's credit.
public nonisolated enum ProjectLinks {
    // Literals that parse, as `ProjectLinksTests` checks.
    public static let repository = URL(string: "https://github.com/jlevy/metabrowser")!
    /// What the title bar's mark says to assistive apps, as a button that opens `repository`.
    public static let repositoryLabel = "Metabrowser on GitHub"
    /// The About panel's credit, "By" and the author's name, which links to `author`.
    public static let authorName = "Joshua Levy"
    public static let author = URL(string: "https://x.com/ojoshe")!

    public static var readme: URL { readmeSection("readme") }
    public static var installationGuide: URL { readmeSection("installation") }

    private static func readmeSection(_ fragment: String) -> URL {
        var components = URLComponents(url: repository, resolvingAgainstBaseURL: false)
        components?.fragment = fragment
        return components?.url ?? repository
    }
}
