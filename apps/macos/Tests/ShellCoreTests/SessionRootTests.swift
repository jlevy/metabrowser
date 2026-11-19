import Foundation
import Testing
@testable import ShellCore

private let repository = URL(string: "https://github.com/jlevy/tbd")!

@Suite struct SessionRootTests {
    /// A folder is keyed by its path as the saved session and `OpenTarget` spell it, without
    /// a trailing slash, so a root read from either finds its session; a repository's is its
    /// URL, which no path can equal.
    @Test func aFolderIsKeyedByItsPathAndARepositoryByItsURL() {
        let folder = URL(filePath: "/tmp/notes", directoryHint: .isDirectory)
        #expect(SessionRoot.folder(folder).key == "/tmp/notes")
        #expect(SessionRoot.folder(URL(filePath: "/tmp/notes/")).key == "/tmp/notes")
        #expect(SessionRoot.folder(URL(filePath: "/", directoryHint: .isDirectory)).key == "/")
        #expect(SessionRoot.repository(repository).key == "https://github.com/jlevy/tbd")
        #expect(SessionRoot.folder(URL(filePath: "/jlevy/tbd", directoryHint: .isDirectory)).key != SessionRoot.repository(repository).key)
    }

    /// Every link into one repository resolves to its canonical root, whatever it selects,
    /// so they share one key and one session.
    @Test func everyLinkIntoARepositoryFindsItsOneSession() throws {
        let answers = [
            #"{"kind": "pull_request", "root": "https://github.com/jlevy/tbd", "page": "/pull/12", "handoff": ["https://github.com/jlevy/tbd/pull/12"], "refusal": null}"#,
            #"{"kind": "file", "root": "https://github.com/jlevy/tbd", "page": null, "handoff": ["https://github.com/jlevy/tbd/blob/a/b/README.md"], "refusal": null}"#,
            #"{"kind": "tree", "root": "https://github.com/jlevy/tbd", "page": "/view/", "handoff": ["https://github.com/jlevy/tbd/tree/main"], "refusal": null}"#,
        ]
        var keys = Set<String>()
        for json in answers {
            guard case .plan(let plan) = PresentDryRun.answer(CommandResult(status: 0, output: [json])) else {
                Issue.record("expected a repository plan for \(json)")
                continue
            }
            keys.insert(SessionRoot.repository(plan.repository).key)
        }
        #expect(keys == ["https://github.com/jlevy/tbd"])
    }

    @Test func aRepositoryIsNamedByItsRepositoryUntilItsServerAnswers() {
        let identity = SessionRoot.repository(repository).identity()
        #expect(identity == FolderIdentity(
            shortName: "tbd", fullName: "github.com/jlevy/tbd", kind: .mirror, kindLabel: "Cached mirror",
            title: "tbd • Metabrowser"))
        // A mirror's title opens no path menu.
        #expect(!WindowTitle(identity).hasPathMenu)
        #expect(SessionRoot.folder(URL(filePath: "/tmp/notes")).identity(home: "/tmp/account").kind == .folder)
    }

    /// One value gives a session its gate and its port walk (A12), and the lanes' walks
    /// never meet, nor does the repositories' reach 8443 (B7).
    @Test func aRepositoryWalksPortsNoFolderWalks() {
        #expect(!LaunchLane.folders.ports.overlaps(LaunchLane.repositories.ports))
        #expect(LaunchLane.folders.ports == 8411..<8443)
        #expect(LaunchLane.repositories.ports == 8475..<8507)
        #expect(!LaunchLane.repositories.ports.contains(8443))
        #expect(SessionRoot.folder(URL(filePath: "/tmp/notes")).lane == .folders)
        #expect(SessionRoot.repository(repository).lane == .repositories)
        #expect(LaunchLane.folders.basePort == CLIServeLaunch.defaultBasePort)
        #expect(LaunchLane.repositories.basePort == CLIServeLaunch.repositoryBasePort)
    }

    @Test func aRepositoryLogNeverSharesAFoldersName() {
        let repositoryLog = ServerLog.fileName(for: repository)
        #expect(repositoryLog.hasPrefix("tbd-"))
        #expect(repositoryLog != ServerLog.fileName(for: URL(filePath: "/jlevy/tbd")))
        // A folder's log keeps the name it had before repositories had logs: the digest of
        // its path, pinned by value.
        #expect(ServerLog.fileName(for: URL(filePath: "/tmp/notes")) == "notes-8fcb83ec.log")
    }
}

@Suite struct RepositoryLaunchTests {
    private let setup = RuntimeSetup(
        runtime: Runtime(executable: "/opt/metab", version: "0.12.1", source: .localBin), tools: ToolPaths())

    /// The server is started with the link `metab` handed back, not the cache's path for it
    /// nor the URL's path (`/jlevy/tbd/pull/12`, which `root.path` would give), and runs in
    /// the home folder.
    @Test func aRepositoryServerIsStartedWithTheLinkInTheHomeFolder() {
        let link = URL(string: "https://github.com/jlevy/tbd/pull/12")!
        let launch = CLIServeLaunch(basePort: SessionRoot.repository(repository).lane.basePort)
        let spec = launch.spec(serving: link, with: setup, inherited: [:], logURL: nil, home: "/tmp/account")
        #expect(spec.arguments == [
            "https://github.com/jlevy/tbd/pull/12", "--no-open", "--exit-on-eof", "--host", "127.0.0.1",
            "--port", String(CLIServeLaunch.repositoryBasePort),
        ])
        #expect(spec.workingDirectory == "/tmp/account")
    }

    @Test func aFolderServerIsUnchanged() {
        let spec = CLIServeLaunch().spec(
            serving: URL(filePath: "/tmp/notes/"), with: setup, inherited: [:], logURL: nil, home: "/tmp/account")
        #expect(spec.arguments.first == "/tmp/notes/")
        #expect(spec.workingDirectory == "/tmp/notes/")
    }

    /// `metab URL` prints its normalized root, which the announcement parser reads past.
    @Test func aRepositoryServersAnnouncementIsRead() {
        let found = CLIServeLaunch.parseServingLine(
            "Serving https://github.com/jlevy/metabrowser at http://127.0.0.1:8443/pull/517  [dev build: +1656 commits, dcf2bcfa8]")
        #expect(found?.origin.absoluteString == "http://127.0.0.1:8443")
        #expect(found?.entryURL.absoluteString == "http://127.0.0.1:8443/pull/517")
        #expect(CLIServeLaunch.unservableReason(repository) == nil)
    }
}
