import AppKit
import Testing
@testable import ShellCore

/// What `RootMark.TitleLineLayout` relies on in `NSMenu`'s own layout, measured as AppKit
/// sizes a menu: the raised mark's taller image fits a subtitled item without making it
/// taller, and an empty subtitle adds no line, so the app gives that item the plain mark
/// (`RootMark.image(for:)`).
@Suite struct TitleLineMenuTests {
    private func menuHeight(subtitle: String?, imageHeight: CGFloat) -> CGFloat {
        let menu = NSMenu()
        let item = NSMenuItem(title: "notes", action: nil, keyEquivalent: "")
        item.subtitle = subtitle
        item.image = NSImage(size: NSSize(width: 16, height: imageHeight), flipped: false) { _ in true }
        menu.addItem(item)
        return menu.size.height
    }

    @Test func theRaisedMarkLeavesASubtitledItemAsTallAsTheMarkDoes() {
        let layout = RootMark.TitleLineLayout(mark: CGSize(width: 16, height: 16))
        let raised = menuHeight(subtitle: "~/Documents/notes", imageHeight: layout.size.height)
        #expect(raised == menuHeight(subtitle: "~/Documents/notes", imageHeight: 16))
        // The second line is there to fit in: the subtitle makes the item taller.
        #expect(raised > menuHeight(subtitle: nil, imageHeight: 16))
    }

    @Test func anEmptySubtitleAddsNoLine() {
        #expect(menuHeight(subtitle: "", imageHeight: 16) == menuHeight(subtitle: nil, imageHeight: 16))
    }
}
