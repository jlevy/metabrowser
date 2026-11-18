import CoreGraphics
import Foundation
import Testing
@testable import ShellCore

@Suite struct ProjectLinksTests {
    @Test func theMarkLeadsToTheRepositoryOnGitHub() {
        #expect(ProjectLinks.repository.absoluteString == "https://github.com/jlevy/metabrowser")
        #expect(ProjectLinks.repository.scheme == "https")
        #expect(ProjectLinks.repository.host() == "github.com")
        #expect(ProjectLinks.repositoryLabel == "Metabrowser on GitHub")
    }

    @Test func theOtherLinksAreUnderTheRepository() {
        #expect(ProjectLinks.readme.absoluteString == "https://github.com/jlevy/metabrowser#readme")
        #expect(ProjectLinks.installationGuide.absoluteString
            == "https://github.com/jlevy/metabrowser/blob/main/docs/installation.md")
    }
}

@Suite struct TitleBarMarkLayoutTests {
    private let aspectRatio = AppIconMark.ink.width / AppIconMark.ink.height
    /// The title bar's height, measured on macOS 26.5.
    private let barHeight: CGFloat = 32

    @Test func theMarkIsThirteenPointsTallAndCenteredOnTheButtons() {
        let layout = TitleBarMarkLayout(markAspectRatio: aspectRatio, barHeight: barHeight)
        #expect(layout.mark.height == 13)
        // 9.5 to 22.5 points below the top, about the buttons' center at 16, on a Retina pixel.
        #expect(layout.mark.minY == 9.5 && layout.mark.maxY == 22.5)
        #expect(abs(layout.mark.width - 18.814) < 0.001)
    }

    @Test func itsInkEndsAboutFourteenPointsFromTheWindowsTrailingEdge() {
        let layout = TitleBarMarkLayout(markAspectRatio: aspectRatio, barHeight: barHeight)
        // A whole-point accessory and a whole-point stem: 14.19 points from the edge.
        #expect(TitleBarMarkLayout.edgeGap == 14)
        #expect(layout.width == 36)
        #expect(layout.mark.minX == 3)
        #expect(layout.trailingGap >= TitleBarMarkLayout.edgeGap && layout.trailingGap < TitleBarMarkLayout.edgeGap + 0.5)
        #expect(abs(layout.trailingGap - 14.186) < 0.001)
    }

    @Test func theSquareHighlightSurroundsTheMarkClearOfTheEdge() {
        let layout = TitleBarMarkLayout(markAspectRatio: aspectRatio, barHeight: barHeight)
        #expect(layout.highlight.contains(layout.mark))
        // Three points past the ink on every side, with square corners, as the web page's
        // hover on the folder's heading.
        #expect(layout.highlight == layout.mark.insetBy(dx: -3, dy: -3))
        #expect(TitleBarMarkLayout.highlightCornerRadius == 0)
        // It never reaches the window's trailing edge: 11.19 points short of it.
        #expect(abs(layout.highlightTrailingGap - 11.186) < 0.001)
        #expect(layout.highlight.minX >= 0 && layout.highlight.maxX <= layout.width)
        #expect(layout.highlight.minY >= 0 && layout.highlight.maxY <= barHeight)
    }

    @Test func rightToLeftMirrorsIt() {
        let ltr = TitleBarMarkLayout(markAspectRatio: aspectRatio, barHeight: barHeight)
        let rtl = TitleBarMarkLayout(markAspectRatio: aspectRatio, barHeight: barHeight, rightToLeft: true)
        #expect(rtl.width == ltr.width)
        #expect(abs(rtl.mark.minX - (ltr.width - ltr.mark.maxX)) < 0.001)
        #expect(abs(rtl.trailingGap - ltr.trailingGap) < 0.001)
        #expect(rtl.mark.minY == ltr.mark.minY)
    }
}

@Suite struct TitleBarMarkInteractionTests {
    private let inside = CGPoint(x: 680, y: 16)

    @Test func aPressReleasedInsideOpensThePageOnce() {
        var mark = TitleBarMarkInteraction()
        mark.pointerEntered()
        mark.pressed(at: inside)
        #expect(mark.isPressed)
        #expect(mark.moved(to: CGPoint(x: inside.x + 1, y: inside.y + 1)) == nil)  // a tremor is still a click
        #expect(mark.released(inside: true) == .open)
        #expect(!mark.isPressed && !mark.isHovered)
        // A second release, with no press, opens nothing more.
        #expect(mark.released(inside: true) == nil)
    }

    @Test func anAccessibilityPressOpensThePageOnce() {
        var mark = TitleBarMarkInteraction()
        #expect(mark.accessibilityPressed() == .open)
        #expect(mark.released(inside: true) == nil)
    }

    @Test func aReleaseOutsideTheHighlightOpensNothing() {
        var mark = TitleBarMarkInteraction()
        mark.pressed(at: inside)
        #expect(mark.released(inside: false) == nil)
        #expect(!mark.isPressed)
    }

    @Test func aPressThatMovesThreePointsDragsAndNeverOpens() {
        var mark = TitleBarMarkInteraction()
        mark.pressed(at: inside)
        #expect(mark.moved(to: CGPoint(x: inside.x + 2.9, y: inside.y)) == nil)
        #expect(mark.moved(to: CGPoint(x: inside.x + 3, y: inside.y)) == .drag)
        // The drag is reported once, and its release opens nothing, back inside or not.
        #expect(mark.moved(to: CGPoint(x: inside.x + 20, y: inside.y)) == nil)
        #expect(mark.released(inside: true) == nil)
        // Diagonally, the distance counts, not either axis alone.
        mark.pressed(at: inside)
        #expect(mark.moved(to: CGPoint(x: inside.x + 2.2, y: inside.y - 2.2)) == .drag)
    }

    @Test func deactivationMidPressOpensNothing() {
        var mark = TitleBarMarkInteraction()
        mark.pointerEntered()
        mark.pressed(at: inside)
        mark.deactivated()
        #expect(!mark.isPressed && !mark.isHovered)
        #expect(mark.released(inside: true) == nil)
    }

    @Test func aFirstClickInAWindowThatIsNotKeyOpensOnce() {
        // The key-window tracking area reports no hover there: the press comes unlit.
        var mark = TitleBarMarkInteraction()
        #expect(!mark.isHovered)
        mark.pressed(at: inside)
        #expect(mark.released(inside: true) == .open)
        #expect(mark.released(inside: true) == nil)
    }

    @Test func theHoverGoesOutOnExitAndOnDeactivation() {
        var mark = TitleBarMarkInteraction()
        mark.pointerEntered()
        #expect(mark.isHovered)
        mark.pointerExited()
        #expect(!mark.isHovered)
        // Resigning key and resigning active both reach `deactivated`.
        mark.pointerEntered()
        mark.deactivated()
        #expect(!mark.isHovered)
    }
}
