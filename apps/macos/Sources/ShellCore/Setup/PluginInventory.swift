import Foundation

/// The plugins and discovery errors reported by the selected runtime. A discovery
/// error can leave other plugins available, so an exit status of 1 can carry a list.
public nonisolated struct PluginInventory: Decodable, Equatable, Sendable {
    public struct Plugin: Decodable, Equatable, Sendable, Identifiable {
        public var name: String
        public var displayName: String
        public var version: String
        public var source: String
        public var requires: [String]?
        public var id: String { name }

        enum CodingKeys: String, CodingKey {
            case name = "name"
            case displayName = "display_name"
            case version = "version"
            case source = "source"
            case requires = "requires"
        }
    }

    public var plugins: [Plugin]
    public var errors: [String]

    enum CodingKeys: String, CodingKey {
        case plugins = "plugins"
        case errors = "errors"
    }

    public enum Answer: Equatable, Sendable {
        case inventory(PluginInventory)
        case unavailable(String)
    }

    public static let arguments = ["--plugins", "--json"]
    public static let timeout = Duration.seconds(20)

    /// Use the same executable and environment as a new folder server.
    public static func spec(setup: RuntimeSetup, inherited: [String: String]) -> LaunchSpec {
        LaunchSpec(
            executable: setup.runtime.executable, arguments: arguments,
            environment: ChildEnvironment.build(inherited: inherited, toolDirectories: setup.tools.directories))
    }

    public static func answer(_ result: CommandResult) -> Answer {
        if let launchError = result.launchError {
            return .unavailable("Could not run metab: \(launchError)")
        }
        if result.timedOut {
            return .unavailable("Plugin discovery timed out.")
        }
        switch JSONAnswer.object(in: result.output) {
        case .success(let data):
            if let inventory = try? JSONDecoder().decode(Self.self, from: data) {
                return .inventory(inventory)
            }
            return .unavailable("metab returned a plugin list this app cannot read.")
        case .failure(let problem):
            return .unavailable("Could not read the plugin list: \(problem.description).")
        }
    }
}
