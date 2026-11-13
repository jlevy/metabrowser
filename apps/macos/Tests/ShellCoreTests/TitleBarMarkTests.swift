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

    @Test func itsInkEndsAboutNinePointsFromTheWindowsTrailingEdge() {
        let layout = TitleBarMarkLayout(markAspectRatio: aspectRatio, barHeight: barHeight)
        // A whole-point accessory and a whole-point stem: 9.19 points from the edge.
        #expect(layout.width == 32)
        #expect(layout.mark.minX == 4)
        #expect(layout.trailingGap >= TitleBarMarkLayout.edgeGap && layout.trailingGap < TitleBarMarkLayout.edgeGap + 0.5)
        #expect(abs(layout.trailingGap - 9.186) < 0.001)
    }

    @Test func theHighlightSurroundsTheMarkInsideTheAccessory() {
        let layout = TitleBarMarkLayout(markAspectRatio: aspectRatio, barHeight: barHeight)
        #expect(layout.highlight.contains(layout.mark))
        #expect(layout.highlight == layout.mark.insetBy(dx: -4, dy: -3))
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
