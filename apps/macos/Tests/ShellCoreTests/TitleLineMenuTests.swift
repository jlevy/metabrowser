import AppKit
import Testing
@testable import ShellCore
@testable import ShellViews

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

/// What `TitleLineMenuItem` promises of the folder chooser's check mark: it stands on the
/// title's line, in the size and column width AppKit's check has, and the item is still
/// reported as checked to accessibility, as a stock item in the same state is.
@Suite struct TitleLineCheckTests {
    private typealias CheckMark = TitleLineMenuItem.CheckMark
    private let layout = RootMark.TitleLineLayout(mark: CheckMark.slot)

    /// What an accessibility client reads as the item's mark: the "✓" VoiceOver reports as
    /// "checked". The legacy `accessibilityAttributeValue:` is the only way an item says it,
    /// and Swift marks it deprecated, so it is sent by name.
    private func markChar(_ item: NSObject) -> String? {
        let ask = NSSelectorFromString("accessibilityAttributeValue:")
        return item.perform(ask, with: kAXMenuItemMarkCharAttribute as NSString)?.takeUnretainedValue() as? String
    }

    private func item(subtitle: String?, state: NSControl.StateValue) -> TitleLineMenuItem {
        let item = TitleLineMenuItem(title: "notes", action: nil, keyEquivalent: "")
        item.subtitle = subtitle
        item.state = state
        return item
    }

    private func stock(state: NSControl.StateValue) -> NSMenuItem {
        let item = NSMenuItem(title: "notes", action: nil, keyEquivalent: "")
        item.state = state
        return item
    }

    @Test func aCheckedRowIsReportedCheckedAsAStockItemIs() {
        // The oracle is AppKit's own answer, so the test holds what "checked" means on
        // whatever macOS runs it, and it must say something for a checked item.
        #expect(markChar(stock(state: .on)) != nil)
        for state in [NSControl.StateValue.on, .off, .mixed] {
            for subtitle in [nil, "", "~/Documents/notes"] as [String?] {
                #expect(
                    markChar(item(subtitle: subtitle, state: state)) == markChar(stock(state: state)),
                    "state \(state.rawValue), subtitle \(subtitle ?? "nil")")
            }
        }
    }

    @Test func anAccessibilityClientReadsTheCheckFromTheOpenMenu() {
        let checked = item(subtitle: "~/Documents/notes", state: .on)
        let other = item(subtitle: "In another window", state: .off)
        let menu = NSMenu()
        menu.addItem(checked)
        menu.addItem(other)
        // The menu's accessibility children are the items themselves, so a client asks
        // these objects, which answer as a stock menu's items do.
        let children = menu.accessibilityChildren() as? [NSObject] ?? []
        #expect(children.contains { $0 === checked } && children.contains { $0 === other })
        #expect(children.first { $0 === checked }.flatMap(markChar) == markChar(stock(state: .on)))
        #expect(children.first { $0 === other }.flatMap(markChar) == nil)
    }

    @Test func aStockItemWithTheRaisedCheckWouldNotBeReportedChecked() {
        // Why the item answers for itself: AppKit keeps the mark only for its own image.
        // Should this fail, AppKit has stopped dropping it, and the override is not needed.
        let plain = stock(state: .on)
        plain.onStateImage = TitleLineMenuItem.raisedCheck
        #expect(markChar(plain) == nil)
    }

    @Test func theCheckStandsOnTheTitleLineOnlyWithASubtitle() {
        let alone = NSMenuItem(title: "notes", action: nil, keyEquivalent: "")
        let row = item(subtitle: nil, state: .on)
        // One line: AppKit's own check, already on it.
        #expect(row.onStateImage === alone.onStateImage)
        row.subtitle = "~/Documents/notes"
        #expect(row.onStateImage === TitleLineMenuItem.raisedCheck)
        row.subtitle = ""
        #expect(row.onStateImage === alone.onStateImage)
        row.subtitle = "In another window"
        row.subtitle = nil
        #expect(row.onStateImage === alone.onStateImage)
    }

    @Test func theRaisedCheckIsRaisedByTheTitleLineRise() throws {
        let image = TitleLineMenuItem.raisedCheck
        #expect(image.isTemplate)
        #expect(image.size == layout.size)
        // A slot as wide as the column AppKit gives a check, and 2 × rise taller.
        #expect(layout.size.width == CheckMark.slot.width)
        #expect(layout.size.height == CheckMark.slot.height + 2 * RootMark.TitleLineLayout.rise)
        let bitmap = try #require(image.representations.compactMap { $0 as? NSBitmapImageRep }.last)
        let ink = CheckMark.inkBounds(in: bitmap)
        // Unraised, the check's ink is centered `inkCenter` into its slot: half a point
        // under the slot's middle, as AppKit's is on a one-line row. Raised, it is the
        // title line's rise above that, measured from the middle of the item, which is
        // the middle of the image: the check's ink then has the middle of the title's.
        let unraised = CheckMark.inkCenter.y - CheckMark.slot.height / 2
        let raised = ink.midY - image.size.height / 2
        #expect(abs((raised - unraised) - RootMark.TitleLineLayout.rise) < 0.25)
        #expect(abs(ink.midX - CheckMark.inkCenter.x) < 0.25)
        // The size AppKit draws: about nine points of ink, all of it inside the slot.
        #expect(abs(ink.height - 9) < 0.5)
        #expect(layout.mark.contains(ink))
    }

    @Test func theRaisedCheckLeavesTheMenuTheSizeAppKitsCheckMakes() {
        func menuSize(_ check: NSImage?) -> NSSize {
            let menu = NSMenu()
            let row = item(subtitle: "~/Documents/notes", state: .on)
            // As the chooser's rows are, with the mark on the title's line.
            row.image = NSImage(size: NSSize(width: 16, height: 30), flipped: false) { _ in true }
            if let check { row.onStateImage = check }
            menu.addItem(row)
            return menu.size
        }
        let stockCheck = NSMenuItem(title: "", action: nil, keyEquivalent: "").onStateImage
        // The same menu as with AppKit's own check. A state image's width is the state
        // column's (an 18-point one made this menu 5 points wider); its height never changes
        // the item's, as the mark's does (macOS 26.5: 16 to 80 points, the same item).
        #expect(menuSize(TitleLineMenuItem.raisedCheck) == menuSize(stockCheck))
    }
}
