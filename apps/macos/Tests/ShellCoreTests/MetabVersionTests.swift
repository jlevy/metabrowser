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
        #expect(MetabRequirement.minimum == "0.13.0")
        // 0.12.0, the release before the route, a patch of it, and anything older is refused.
        #expect(!MetabRequirement.accepts(try #require(MetabVersion("0.12.0"))))
        #expect(!MetabRequirement.accepts(try #require(MetabVersion("0.12.1"))))
        #expect(!MetabRequirement.accepts(try #require(MetabVersion("0.12.0.post3"))))
        #expect(!MetabRequirement.accepts(try #require(MetabVersion("0.9.9"))))
        #expect(MetabRequirement.accepts(try #require(MetabVersion("0.13.0"))))
        #expect(MetabRequirement.accepts(try #require(MetabVersion("0.13.1"))))
        #expect(MetabRequirement.accepts(try #require(MetabVersion("1"))))
    }

    /// The contract is at the minor release (`docs/publishing.md`), so the minimum is
    /// `X.Y.0`. `tests/test_macos_app_pins.py` checks this too, in every CI run, with the
    /// bounds, the bump, and the cache keys this test cannot see.
    @Test func theMinimumIsAMinorRelease() {
        #expect(MetabRequirement.minimumRelease.count == 3)
        #expect(MetabRequirement.minimumRelease.last == 0)
    }

    /// A source checkout reports the next minor release with `.devN`, which PEP 440 orders
    /// before that release; it still runs, or no development build would.
    @Test func aDevelopmentBuildOfTheMinimumCountsAsIt() throws {
        #expect(MetabRequirement.accepts(try #require(MetabVersion("0.13.0.dev214+8b0603f7 (+214 commits, 8b0603f78)"))))
        #expect(MetabRequirement.accepts(try #require(MetabVersion("0.13.0rc1"))))
        // A checkout built before the minor bump reported the next patch, which is too old.
        #expect(!MetabRequirement.accepts(try #require(MetabVersion("0.12.1.dev1833+69420ed8a"))))
        #expect(!MetabRequirement.accepts(try #require(MetabVersion("0.12.0.post1.dev2"))))
    }

    /// mb-sugi: validation finds a build whose number meets the minimum too old only for
    /// rejecting one of its flags, and a build without any of them predates the newest,
    /// `--recent`, so that is what the screens say about it.
    @Test func aTooOldBuildThatMeetsTheNumberLacksTheFlag() {
        #expect(MetabRequirement.requiredFlags == ["--exit-on-eof", "--present", "--recent"])
        #expect(MetabRequirement.flagShortfall("0.13.0.dev38+5f0c2a1 (+38 commits, 5f0c2a1)")
            == "built before --recent")
        #expect(MetabRequirement.flagShortfall("0.13.0") == "built before --recent")
        #expect(MetabRequirement.flagShortfall("0.12.0") == nil)
        #expect(MetabRequirement.flagShortfall("0.12.1.dev38+5f0c2a1 (+38 commits, 5f0c2a1)") == nil)
        #expect(MetabRequirement.flagShortfall("0.12.0.post1.dev2") == nil)
        #expect(MetabRequirement.flagShortfall("soon") == nil)
    }

    /// A floor rather than an exact pin: uv keeps the requirement in the tool's receipt,
    /// so a pin would stop every later `uv tool upgrade`.
    @Test func theUpgradeCommandAsksForTheMinimumAsAFloor() {
        #expect(MetabRequirement.upgradeCommand(for: .uvTool) == "uv tool install --upgrade 'metabrowser>=0.13.0'")
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
        #expect(await validate("metab 0.12.1") == .tooOld(version: "0.12.1"))
        #expect(await validate("metab 0.13.0") == .valid(version: "0.13.0"))
        #expect(await validate("metab soon") == .rejected("--version printed a version this app cannot read: soon"))
    }

    /// How a `metab` was installed, from the files beside its canonical executable.
    @Test func theInstallIsReadFromBesideTheExecutable() {
        func install(_ executable: String, real: String? = nil, files: Set<String>) -> MetabInstall {
            MetabInstall.of(
                executable: executable, canonicalPath: { _ in real ?? executable }, fileExists: { files.contains($0) })
        }
        let tool = "/Volumes/Home/.local/share/uv/tools/metabrowser"
        #expect(install("/Volumes/Home/.local/bin/metab", real: tool + "/bin/metab", files: [tool + "/uv-receipt.toml"])
            == .uvTool)
        let pipx = "/Volumes/Home/.local/pipx/venvs/metabrowser"
        #expect(install(pipx + "/bin/metab", files: [pipx + "/pipx_metadata.json"]) == .pipx)
        let checkout = "/Volumes/Home/src/metabrowser"
        #expect(install(checkout + "/.venv/bin/metab", files: [checkout + "/pyproject.toml"])
            == .checkout(root: checkout))
        // An editable uv tool install has a receipt too, and uv upgrades it.
        #expect(install(checkout + "/.venv/bin/metab", files: [checkout + "/pyproject.toml", checkout + "/.venv/uv-receipt.toml"])
            == .uvTool)
        // A `.venv` with no project beside it, and anything else, is replaced by uv's.
        #expect(install("/opt/venv/.venv/bin/metab", files: []) == .other)
        #expect(install("/metab", files: []) == .other)
        #expect(MetabInstall.pipx.upgradeCommand(minimum: "0.13.0") == "pipx install --force 'metabrowser>=0.13.0'")
        #expect(MetabInstall.checkout(root: checkout).upgradeCommand(minimum: "0.13.0") == "git pull && make install")
    }
}
