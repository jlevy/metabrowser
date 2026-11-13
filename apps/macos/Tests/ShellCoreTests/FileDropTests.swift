import Foundation
import Testing
@testable import ShellCore

/// Which drops on a window the app opens, rather than handing them to the page (mb-3h2m).
@Suite struct FileDropTests {
    private let file = URL(filePath: "/tmp/notes/a.md")
    private let folder = URL(filePath: "/tmp/notes", directoryHint: .isDirectory)

    /// The defect: a dropped file reached WebKit, which asked to navigate to its file://
    /// URL, and the navigation policy cancelled that, so nothing happened. Files now open
    /// like folders, through `OpenTarget`.
    @Test func filesAndFoldersFromFinderOpenInTheApp() {
        #expect(FileDrop.opens([file], items: 1) == [file])
        #expect(FileDrop.opens([folder, file], items: 2) == [folder, file])
    }

    /// A drag that also carries something else (text, a web link) is the page's to handle.
    @Test func aDragWithMoreThanFilesIsLeftToThePage() {
        #expect(FileDrop.opens([file], items: 2).isEmpty)
        #expect(FileDrop.opens([], items: 1).isEmpty)
        #expect(FileDrop.opens([URL(string: "https://example.com/a.md")!], items: 1).isEmpty)
    }
}
