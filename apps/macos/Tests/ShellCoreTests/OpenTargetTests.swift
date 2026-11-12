import Foundation
import Testing
@testable import ShellCore

@Suite struct PageAddressTests {
    private let origin = URL(string: "http://127.0.0.1:8415")!

    @Test func viewRouteEncodesEachSegmentAsMetabDoes() {
        // view_routes.format_view_href: every byte but A-Z a-z 0-9 _ . - ~ is escaped, in
        // uppercase hex, one segment at a time.
        #expect(PageAddress.view(of: "docs/plan.md").reference == "/view/docs/plan.md")
        #expect(PageAddress.view(of: "a b/#1?.md").reference == "/view/a%20b/%231%3F.md")
        #expect(PageAddress.view(of: "Café/naïve~_-.txt").reference == "/view/Caf%C3%A9/na%C3%AFve~_-.txt")
        #expect(PageAddress.view(of: "").reference == "/view/")
    }

    @Test func aPageMovesToWhicheverPortTheServerHasNow() {
        let page = PageAddress(URL(string: "http://127.0.0.1:8412/view/docs/a%20b.md?mode=raw#top")!)
        #expect(page?.reference == "/view/docs/a%20b.md?mode=raw#top")
        #expect(page?.url(on: origin)?.absoluteString == "http://127.0.0.1:8415/view/docs/a%20b.md?mode=raw#top")
    }

    @Test func onlyAPathOnTheServerIsAnAddress() {
        // "//host/x" names another host; a scheme or a relative path names no page here.
        for reference in ["//example.com/view/", "http://example.com/view/", "view/a.md", ""] {
            #expect(PageAddress(reference: reference) == nil, "\(reference)")
        }
        #expect(PageAddress(reference: "/view/a.md")?.url(on: origin)?.absoluteString
            == "http://127.0.0.1:8415/view/a.md")
    }

    @Test func aSavedAddressIsCheckedWhenRead() throws {
        let decoder = JSONDecoder()
        #expect(try decoder.decode(PageAddress.self, from: Data(#""/view/a.md""#.utf8)).reference == "/view/a.md")
        #expect(throws: DecodingError.self) {
            try decoder.decode(PageAddress.self, from: Data(#""//example.com/""#.utf8))
        }
        let page = PageAddress.view(of: "a b.md")
        #expect(try decoder.decode(PageAddress.self, from: JSONEncoder().encode(page)) == page)
    }
}

@Suite struct OpenTargetTests {
    @Test func aFolderIsItsOwnRoot() {
        let target = OpenTarget.resolve("/Homes/me/notes", kind: .folder, openRoots: ["/Homes/me"])
        #expect(target == OpenTarget(root: "/Homes/me/notes", page: nil))
    }

    @Test func aFileOpensInItsFolderAtItsViewRoute() {
        let target = OpenTarget.resolve("/Homes/me/notes/plan 2.md", kind: .file, openRoots: [])
        #expect(target == OpenTarget(root: "/Homes/me/notes", page: .view(of: "plan 2.md")))
    }

    @Test func aFileInsideAnOpenFolderOpensThereTheMostSpecificWins() {
        let roots = ["/Homes/me", "/Homes/me/wrk", "/Homes/me/wrk/app/docs", "/Homes/me/wrk-old"]
        #expect(OpenTarget.resolve("/Homes/me/wrk/app/src/main.swift", kind: .file, openRoots: roots)
            == OpenTarget(root: "/Homes/me/wrk", page: .view(of: "app/src/main.swift")))
        // A sibling whose name only starts the same is not a container.
        #expect(OpenTarget.resolve("/Homes/me/wrk-older/a.md", kind: .file, openRoots: ["/Homes/me/wrk"])
            == OpenTarget(root: "/Homes/me/wrk-older", page: .view(of: "a.md")))
        #expect(OpenTarget.resolve("/etc/hosts", kind: .file, openRoots: ["/"])
            == OpenTarget(root: "/", page: .view(of: "etc/hosts")))
    }

    @Test func aFileAtTheTopOfTheDiskOpensTheDisk() {
        #expect(OpenTarget.resolve("/notes.md", kind: .file, openRoots: [])
            == OpenTarget(root: "/", page: .view(of: "notes.md")))
    }

    @Test func nothingElseOpens() {
        #expect(OpenTarget.resolve("/dev/null", kind: .other, openRoots: []) == nil)
        #expect(OpenTarget.resolve("relative/a.md", kind: .file, openRoots: []) == nil)
    }

    @Test func kindReadsTheFilesystem() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let file = directory.appending(path: "a.md")
        try Data("# a\n".utf8).write(to: file)
        #expect(OpenTarget.Kind(of: directory.path(percentEncoded: false)) == .folder)
        #expect(OpenTarget.Kind(of: file.path(percentEncoded: false)) == .file)
        #expect(OpenTarget.Kind(of: directory.appending(path: "missing").path(percentEncoded: false)) == .other)
        #expect(OpenTarget.Kind(of: "/dev/null") == .other)
    }
}
