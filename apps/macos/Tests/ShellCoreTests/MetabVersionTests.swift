import Foundation
import Testing
@testable import ShellCore

/// The version policy (mb-895s): which `metab --version` outputs the app runs, and what
/// it tells a user whose `metab` is older.
@Suite struct MetabVersionTests {
    @Test(arguments: [
        ("0.12.0", [0, 12, 0]),
        ("0.12.1rc1", [0, 12, 1]),
        ("0.12.0.post2", [0, 12, 0]),
        ("1.0", [1, 0]),
        // A checkout prints its commit distance and hash after the version.
        ("0.12.1.dev214+8b0603f7 (+214 commits, 8b0603f78)", [0, 12, 1]),
    ])
    func readsTheFormsThisProjectsBuildsPrint(printed: String, release: [Int]) throws {
        let version = try #require(MetabVersion(printed))
        #expect(version.release == release)
        #expect(!version.text.contains(" "))
    }

    @Test(arguments: ["", "dev", "0.12.x", "v0.12.0", "0.12.0-beta", "1!0.12.0", "0..12", "99999999999999999999.0"])
    func refusesWhatIsNotAVersion(printed: String) {
        #expect(MetabVersion(printed) == nil)
    }

    @Test func theMinimumIsTheFirstReleaseWithTheIdentityRoute() throws {
        #expect(MetabRequirement.minimum == "0.12.1")
        // 0.12.0, the release before the route, and anything older is refused.
        #expect(!MetabRequirement.accepts(try #require(MetabVersion("0.12.0"))))
        #expect(!MetabRequirement.accepts(try #require(MetabVersion("0.12.0.post3"))))
        #expect(!MetabRequirement.accepts(try #require(MetabVersion("0.9.9"))))
        #expect(MetabRequirement.accepts(try #require(MetabVersion("0.12.1"))))
        #expect(MetabRequirement.accepts(try #require(MetabVersion("0.13.0"))))
        #expect(MetabRequirement.accepts(try #require(MetabVersion("1"))))
    }

    /// A source checkout reports the next release with `.devN`, which PEP 440 orders
    /// before that release; it still runs, or no development build would.
    @Test func aDevelopmentBuildOfTheMinimumCountsAsIt() throws {
        #expect(MetabRequirement.accepts(try #require(MetabVersion("0.12.1.dev214+8b0603f7 (+214 commits, 8b0603f78)"))))
        #expect(MetabRequirement.accepts(try #require(MetabVersion("0.12.1rc1"))))
        #expect(!MetabRequirement.accepts(try #require(MetabVersion("0.12.0.post1.dev2"))))
    }

    /// A floor rather than an exact pin: uv keeps the requirement in the tool's receipt,
    /// so a pin would stop every later `uv tool upgrade`.
    @Test func theUpgradeCommandAsksForTheMinimumAsAFloor() {
        #expect(MetabRequirement.upgradeCommand == "uv tool install --upgrade 'metabrowser>=0.12.1'")
    }

    @Test func validationRefusesAnOlderMetabAndAnUnreadableVersion() async {
        func validate(_ printed: String) async -> CandidateResult {
            let env = DiscoveryEnvironment(
                home: "/Volumes/Home", environment: [:], saved: nil, shell: nil,
                isExecutable: { _ in true }, canonicalPath: { $0 },
                run: { _, _ in CommandResult(status: 0, output: [printed]) }, refusal: { _ in nil })
            return await RuntimeDiscovery.validate("/opt/metab", env)
        }
        #expect(await validate("metab 0.12.0") == .tooOld(version: "0.12.0"))
        #expect(await validate("metab 0.12.1") == .valid(version: "0.12.1"))
        #expect(await validate("metab soon") == .rejected("--version printed a version this app cannot read: soon"))
    }
}
