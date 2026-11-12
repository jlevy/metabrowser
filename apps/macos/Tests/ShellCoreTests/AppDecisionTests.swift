import Darwin
import Foundation
import Testing
@testable import ShellCore

/// Decisions the app target makes from what AppKit and WebKit hand it, kept here so
/// they run without a window.
@Suite struct PageZoomTests {
    @Test func stepsMultiplyAndStayWithinTheLimits() {
        #expect(PageZoom.zoomedIn(1) == 1 * PageZoom.step)
        #expect(PageZoom.zoomedOut(1) == 1 / PageZoom.step)
        #expect(PageZoom.zoomedIn(PageZoom.maximum) == PageZoom.maximum)
        #expect(PageZoom.zoomedOut(PageZoom.minimum) == PageZoom.minimum)
    }

    @Test func aSavedZoomIsUsedOnlyWithinTheLimits() {
        #expect(PageZoom.restored(0) == 1)  // nothing saved: UserDefaults answers 0
        #expect(PageZoom.restored(-2) == 1)
        #expect(PageZoom.restored(.nan) == 1)
        #expect(PageZoom.restored(1.5) == 1.5)
        #expect(PageZoom.restored(40) == PageZoom.maximum)
        #expect(PageZoom.restored(0.01) == PageZoom.minimum)
    }
}

@Suite struct ResponsePolicyTests {
    @Test func aPageWebKitCanShowStaysInTheWindow() {
        #expect(ResponsePolicy.decide(canShowMIMEType: true, contentDisposition: nil) == .show)
        #expect(ResponsePolicy.decide(canShowMIMEType: true, contentDisposition: "inline") == .show)
        #expect(ResponsePolicy.decide(canShowMIMEType: true, contentDisposition: #"inline; filename="a.pdf""#) == .show)
    }

    @Test func anAttachmentOrAnUnshowableTypeDownloads() {
        for disposition in ["attachment", "Attachment", #"attachment; filename="a.md""#, " attachment ;filename=a"] {
            #expect(ResponsePolicy.decide(canShowMIMEType: true, contentDisposition: disposition) == .download)
        }
        #expect(ResponsePolicy.decide(canShowMIMEType: false, contentDisposition: nil) == .download)
    }

    @Test func onlyTheDispositionTypeCounts() {
        // RFC 6266: the type is the token before the first parameter.
        #expect(ResponsePolicy.decide(canShowMIMEType: true, contentDisposition: "attachments") == .show)
        #expect(ResponsePolicy.decide(canShowMIMEType: true, contentDisposition: #"inline; filename="attachment""#)
            == .show)
    }
}

@Suite struct CommandTranscriptTests {
    @Test func aFinishedCommandEndsWithItsStatus() {
        let result = CommandResult(status: 3 << 8, output: ["checking", "done"])
        #expect(result.transcript(timeout: .seconds(60)) == ["checking", "done", "(exit status 3)"])
    }

    @Test func aCommandStoppedAtItsDeadlineSaysSo() {
        let result = CommandResult(status: nil, output: ["checking"], timedOut: true)
        #expect(result.transcript(timeout: .seconds(60)) == ["checking", "(stopped after 60 seconds)"])
    }

    @Test func aCommandThatCouldNotStartSaysWhy() {
        let result = CommandResult(status: nil, output: [], launchError: "No such file or directory")
        #expect(result.transcript(timeout: .seconds(60)) == ["could not run: No such file or directory"])
    }
}
