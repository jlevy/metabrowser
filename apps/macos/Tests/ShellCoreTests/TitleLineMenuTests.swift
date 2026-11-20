import AppKit
import Testing
@testable import ShellCore

/// What `RootMark.TitleLineLayout` and `FolderChooser.oneLine` rely on in `NSMenu`'s own
/// layout, measured as AppKit sizes a menu: the raised mark's taller image fits a subtitled
/// item without making it taller, and no taller; an empty subtitle adds no line, so the
/// app gives that item the plain mark; and a long subtitle, which AppKit wraps, is cut to
/// one line. The app measures a subtitle the same way (`NSMenuItem.setMark`).
@Suite struct TitleLineMenuTests {
    private let layout = RootMark.TitleLineLayout(mark: CGSize(width: 16, height: 16))

    private func menuHeight(title: String = "notes", subtitle: String?, imageHeight: CGFloat) -> CGFloat {
        let menu = NSMenu()
        let item = NSMenuItem(title: title, action: nil, keyEquivalent: "")
        item.subtitle = subtitle
        item.image = NSImage(size: NSSize(width: 16, height: imageHeight), flipped: false) { _ in true }
        menu.addItem(item)
        return menu.size.height
    }

    @Test func theRaisedMarkLeavesASubtitledItemAsTallAsTheMarkDoes() {
        let raised = menuHeight(subtitle: "~/Documents/notes", imageHeight: layout.size.height)
        #expect(raised == menuHeight(subtitle: "~/Documents/notes", imageHeight: 16))
        // The second line is there to fit in: the subtitle makes the item taller.
        #expect(raised > menuHeight(subtitle: nil, imageHeight: 16))
        // And the raised image is as tall as fits: a point more makes the item taller.
        #expect(menuHeight(subtitle: "~/Documents/notes", imageHeight: layout.size.height + 1) > raised)
    }

    @Test func anEmptySubtitleAddsNoLine() {
        #expect(menuHeight(subtitle: "", imageHeight: 16) == menuHeight(subtitle: nil, imageHeight: 16))
    }

    @Test func aLongLocationIsCutToOneLine() {
        let location = "~/Documents/projects/2026/clients/northwind/archive/quarterly-reports/drafts"
        #expect(location.count > 70)
        let oneLine = menuHeight(subtitle: "~", imageHeight: layout.size.height)
        // AppKit wraps it: the item is taller than with a one-line subtitle.
        #expect(menuHeight(subtitle: location, imageHeight: layout.size.height) > oneLine)
        let shown = FolderChooser.oneLine(location) {
            menuHeight(subtitle: $0, imageHeight: layout.size.height) == oneLine
        }
        #expect(menuHeight(subtitle: shown, imageHeight: layout.size.height) == oneLine)
        #expect(shown.contains("…") && shown.hasPrefix("~/Documents/") && shown.hasSuffix("drafts"))
        // The longest cut that fits: one more character wraps.
        let kept = shown.count - 1
        let longer = FolderChooser.middleTruncated(location, keeping: kept + 1)
        #expect(menuHeight(subtitle: longer, imageHeight: layout.size.height) > oneLine)
    }
}
