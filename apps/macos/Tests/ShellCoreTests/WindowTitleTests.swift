import Foundation
import Testing
@testable import ShellCore

nonisolated private let fduJSON = """
    {"short_name": "fdu", "full_name": "~/wrk/github/fdu", "kind": "folder",
     "kind_label": "Local folder", "title": "fdu • Metabrowser"}
    """

nonisolated private func json(_ text: String) -> Data { Data(text.utf8) }

@Suite struct FolderIdentityTests {
    @Test func decodesTheRoute() {
        #expect(IdentityClient.answer(status: 200, body: json(fduJSON)) == .identity(FolderIdentity(
            shortName: "fdu", fullName: "~/wrk/github/fdu", kind: .folder, kindLabel: "Local folder",
            title: "fdu • Metabrowser")))
    }

    @Test func decodesAMirrorAndIgnoresFieldsItDoesNotUse() {
        let body = json("""
            {"short_name": "metabrowser", "full_name": "github.com/jlevy/metabrowser@main", "kind": "mirror",
             "kind_label": "Cached mirror", "title": "metabrowser • Metabrowser", "added_later": [1, 2]}
            """)
        guard case .identity(let identity) = IdentityClient.answer(status: 200, body: body) else {
            Issue.record("expected an identity")
            return
        }
        #expect(identity.kind == .mirror)
        #expect(identity.fullName == "github.com/jlevy/metabrowser@main")
    }

    /// A 404 is a failure like any other: every `metab` the app runs has the route
    /// (`MetabRequirement`), so the app keeps no separate path for one without it.
    @Test func anythingElseFailsAndFallsBack() {
        let cases: [(Int, String)] = [
            (404, #"{"detail": "Not Found"}"#),
            (500, fduJSON),
            (200, "not json"),
            (200, #"{"short_name": "fdu"}"#),
            (200, fduJSON.replacingOccurrences(of: "\"folder\"", with: "\"remote\"")),
            (200, fduJSON.replacingOccurrences(of: "\"short_name\": \"fdu\"", with: "\"short_name\": \"\"")),
        ]
        for (status, body) in cases {
            let answer = IdentityClient.answer(status: status, body: json(body))
            guard case .failed = answer else {
                Issue.record("\(status) \(body) gave \(answer)")
                continue
            }
            let fallback = FolderIdentity.localFolder(URL(filePath: "/tmp/x"), home: "/Volumes/Home")
            #expect(answer.identity(or: fallback) == fallback)
        }
    }

    @Test func aBodyPastTheLimitIsNotRead() {
        let padding = String(repeating: " ", count: IdentityClient.byteLimit)
        guard case .failed(let reason) = IdentityClient.answer(status: 200, body: json(fduJSON + padding)) else {
            Issue.record("expected a failure")
            return
        }
        #expect(reason.contains("bytes"))
    }

    @Test func theFallbackMatchesWhatTheRouteSaysForTheSameFolder() {
        // So the title does not change when the server answers.
        let derived = FolderIdentity.localFolder(URL(filePath: "/Volumes/Home/wrk/github/fdu/"), home: "/Volumes/Home")
        #expect(IdentityClient.answer(status: 200, body: json(fduJSON)) == .identity(derived))
    }

    @Test func theFallbackNamesHomeAndRootAsMetabDoes() {
        let home = "/Volumes/Home/"
        let homeFolder = FolderIdentity.localFolder(URL(filePath: "/Volumes/Home"), home: home)
        #expect(homeFolder.shortName == "~")
        #expect(homeFolder.fullName == "~")
        #expect(homeFolder.title == "~ • Metabrowser")
        #expect(FolderIdentity.localFolder(URL(filePath: "/Volumes/Home/notes"), home: home).shortName == "notes")
        #expect(FolderIdentity.localFolder(URL(filePath: "/Volumes/Homeless/notes"), home: home).fullName == "/Volumes/Homeless/notes")
        #expect(FolderIdentity.localFolder(URL(filePath: "/private/tmp/a b"), home: home).fullName == "/private/tmp/a b")
        #expect(FolderIdentity.localFolder(URL(filePath: "/private/tmp/a b"), home: home).shortName == "a b")
        let root = FolderIdentity.localFolder(URL(filePath: "/"), home: home)
        #expect(root.shortName == "/")
        #expect(root.fullName == "/")
        #expect(root.title == "/ • Metabrowser")
        #expect(FolderIdentity.abbreviatingHome("/x", home: "/") == "/x")
    }

    @Test func fetchAsksTheServersOriginAndForwardsItsCookie() async {
        let origin = URL(string: "http://127.0.0.1:8411")!
        let plain = IdentityClient.request(origin: origin, authorization: .none)
        #expect(plain.url?.absoluteString == "http://127.0.0.1:8411/api/identity")
        #expect(plain.value(forHTTPHeaderField: "Accept") == "application/json")
        #expect(plain.value(forHTTPHeaderField: "Cookie") == nil)
        let token = IdentityClient.request(origin: origin, authorization: .cookie(name: "mb_8411", value: "s3cret"))
        #expect(token.value(forHTTPHeaderField: "Cookie") == "mb_8411=s3cret")

        let answered = await IdentityClient.fetch(origin: origin, authorization: .none) { request in
            #expect(request.url?.path() == "/api/identity")
            return (200, json(fduJSON))
        }
        guard case .identity(let identity) = answered else {
            Issue.record("expected an identity, got \(answered)")
            return
        }
        #expect(identity.shortName == "fdu")
        let refused = await IdentityClient.fetch(origin: origin, authorization: .none) { _ in
            throw URLError(.cannotConnectToHost)
        }
        guard case .failed = refused else {
            Issue.record("expected a failure, got \(refused)")
            return
        }
    }
}

@Suite struct WindowTitleTests {
    private let fdu = WindowTitle(FolderIdentity(
        shortName: "fdu", fullName: "~/wrk/github/fdu", kind: .folder, kindLabel: "Local folder",
        title: "fdu • Metabrowser"))

    @Test func namesTheWindowForEachPlaceThatShowsIt() {
        // The folder's name alone: the mark at the title bar's end carries the app's.
        #expect(fdu.text == "fdu")
        #expect(fdu.tabTitle == "fdu")
        #expect(fdu.tabToolTip == "~/wrk/github/fdu")
        #expect(fdu.subtitle == "~/wrk/github/fdu · Local folder")
        #expect(fdu.hasPathMenu)
        #expect(WindowTitle.windowTitles([fdu]) == ["fdu"])
    }

    @Test func theTitleIsNotThePagesTitle() {
        // The served page keeps "My Notes • Metabrowser" for a browser's tab.
        let title = WindowTitle(.localFolder(URL(filePath: "/Volumes/Home/My Notes"), home: "/Volumes/Home"))
        #expect(title.identity.title == "My Notes • Metabrowser")
        #expect(title.text == "My Notes")
    }

    @Test func foldersThatShareAShortNameAreTitledByTheirFullNames() {
        func folder(_ path: String) -> WindowTitle {
            WindowTitle(.localFolder(URL(filePath: path), home: "/Users/me"))
        }
        let titles = [folder("/Users/me/a/notes"), folder("/Users/me/fdu"), folder("/Users/me/b/notes")]
        #expect(WindowTitle.windowTitles(titles) == ["~/a/notes", "fdu", "~/b/notes"])
        // Once one of them closes, the other is its short name again.
        #expect(WindowTitle.windowTitles([titles[0], titles[1]]) == ["notes", "fdu"])
        #expect(WindowTitle.windowTitles([]) == [])
        // A mirror sharing a local folder's short name is told apart the same way.
        let mirror = WindowTitle(FolderIdentity(
            shortName: "fdu", fullName: "github.com/jlevy/fdu@main", kind: .mirror, kindLabel: "Cached mirror",
            title: "fdu • Metabrowser"))
        #expect(WindowTitle.windowTitles([titles[1], mirror]) == ["~/fdu", "github.com/jlevy/fdu@main"])
    }

    @Test func aMirrorHasNoPathMenu() {
        let mirror = WindowTitle(FolderIdentity(
            shortName: "metabrowser", fullName: "github.com/jlevy/metabrowser@main", kind: .mirror,
            kindLabel: "Cached mirror", title: "metabrowser • Metabrowser"))
        #expect(!mirror.hasPathMenu)
        #expect(mirror.subtitle == "github.com/jlevy/metabrowser@main · Cached mirror")
    }

    @Test func thePathMenuListsTheFolderThenEachContainingFolder() {
        let isRoot: (String) -> Bool = { $0 == "/" || $0 == "/Volumes/Backup" }
        #expect(WindowTitle.pathMenuFolders(for: "/Volumes/Home/wrk/fdu/", isVolumeRoot: isRoot) == [
            "/Volumes/Home/wrk/fdu", "/Volumes/Home/wrk", "/Volumes/Home", "/Volumes", "/",
        ])
        #expect(WindowTitle.pathMenuFolders(for: "/Volumes/Backup/notes", isVolumeRoot: isRoot) == [
            "/Volumes/Backup/notes", "/Volumes/Backup",
        ])
        #expect(WindowTitle.pathMenuFolders(for: "/", isVolumeRoot: isRoot) == ["/"])
    }

    @Test func theStartupVolumeIsAVolumeRoot() {
        #expect(FileChecks.isVolumeRoot("/"))
        #expect(!FileChecks.isVolumeRoot(NSTemporaryDirectory()))
    }
}
