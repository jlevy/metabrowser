import CoreGraphics
import Testing
@testable import ShellCore

@Suite struct NewWindowFrameTests {
    /// The window's `minSize`, as `BrowserWindowController` sets it.
    private let minimum = CGSize(width: 480, height: 320)

    /// Visible frames, as `NSScreen.visibleFrame` reports them: without the menu bar, and
    /// without the Dock where it shows.
    /// A 13-inch laptop at its default 1470 by 956, with the Dock along the bottom.
    private let laptop = CGRect(x: 0, y: 75, width: 1470, height: 844)
    /// A 16-inch laptop at More Space, 2056 by 1329, with the Dock hidden.
    private let largeLaptop = CGRect(x: 0, y: 0, width: 2056, height: 1290)
    /// A 27-inch display at 2560 by 1440, to the right of the laptop.
    private let external = CGRect(x: 1470, y: -200, width: 2560, height: 1415)
    /// A 1080 by 1920 display turned on its side, to the left.
    private let portrait = CGRect(x: -1080, y: 0, width: 1080, height: 1895)

    @Test func theHeightIsFourFifthsOfTheScreenAndTheWidthALittleMoreThanBefore() {
        #expect(NewWindowFrame.size(visible: laptop, minimum: minimum) == CGSize(width: 1323, height: 675))
        #expect(NewWindowFrame.size(visible: largeLaptop, minimum: minimum) == CGSize(width: 1440, height: 1032))
        #expect(NewWindowFrame.size(visible: external, minimum: minimum) == CGSize(width: 1440, height: 1132))
        // Taller than wide, as the screen is.
        #expect(NewWindowFrame.size(visible: portrait, minimum: minimum) == CGSize(width: 972, height: 1516))
    }

    @Test func aWindowFitsOnEveryScreenLargeEnoughForItsMinimum() {
        for visible in [laptop, largeLaptop, external, portrait, CGRect(x: 0, y: 0, width: 500, height: 400)] {
            let size = NewWindowFrame.size(visible: visible, minimum: minimum)
            #expect(size.width <= visible.width && size.height <= visible.height)
            #expect(size.width >= minimum.width && size.height >= minimum.height)
            #expect(visible.contains(NewWindowFrame.first(size: size, visible: visible)))
        }
    }

    @Test func aScreenTooSmallForTheMinimumGetsTheMinimumWithItsTitleBarOnScreen() {
        let tiny = CGRect(x: 100, y: 50, width: 400, height: 300)
        let size = NewWindowFrame.size(visible: tiny, minimum: minimum)
        #expect(size == minimum)
        let frame = NewWindowFrame.first(size: size, visible: tiny)
        // The top left corner, where the title bar starts, is the screen's.
        #expect(frame.minX == tiny.minX && frame.maxY == tiny.maxY)
        #expect(NewWindowFrame.next(size: size, visible: tiny, after: frame) == frame)
        // Too narrow only: centered top to bottom as usual, pinned to the left edge.
        let narrow = CGRect(x: 0, y: 0, width: 400, height: 900)
        let tall = NewWindowFrame.first(size: NewWindowFrame.size(visible: narrow, minimum: minimum), visible: narrow)
        #expect(tall.minX == 0 && tall.maxY < narrow.maxY && tall.minY > narrow.minY)
    }

    @Test func theFirstWindowIsCenteredAcrossWithAQuarterOfTheFreeHeightAbove() {
        let size = NewWindowFrame.size(visible: largeLaptop, minimum: minimum)
        let frame = NewWindowFrame.first(size: size, visible: largeLaptop)
        #expect(frame == CGRect(x: 308, y: 193, width: 1440, height: 1032))
        // On a screen whose origin is not zero, measured from that screen's edges.
        let onExternal = NewWindowFrame.first(size: CGSize(width: 1440, height: 1132), visible: external)
        #expect(onExternal == CGRect(x: 1470 + 560, y: -200 + 212, width: 1440, height: 1132))
        #expect(external.maxY - onExternal.maxY == 71)
    }

    @Test func eachNextWindowStepsDownAndRightAndStartsOverBeforeLeavingTheScreen() {
        let size = NewWindowFrame.size(visible: laptop, minimum: minimum)
        var frames: [CGRect] = []
        for _ in 0..<7 {
            frames.append(NewWindowFrame.next(size: size, visible: laptop, after: frames.last))
        }
        // 147 points of free width allow two steps right before a third would leave the
        // screen; the free height would allow four.
        let first = CGRect(x: 73, y: 201, width: 1323, height: 675)
        #expect(frames[0] == first)
        #expect(frames[1] == first.offsetBy(dx: 29, dy: -29))
        #expect(frames[2] == first.offsetBy(dx: 58, dy: -58))
        #expect(frames[3] == first)
        #expect(frames[6] == first)
        #expect(frames.allSatisfy { laptop.contains($0) })
    }

    @Test func noCascadedWindowEverRunsOffAnyScreen() {
        for visible in [laptop, largeLaptop, external, portrait] {
            let size = NewWindowFrame.size(visible: visible, minimum: minimum)
            var previous: CGRect?
            var startedOver = 0
            for _ in 0..<60 {
                let frame = NewWindowFrame.next(size: size, visible: visible, after: previous)
                #expect(visible.contains(frame))
                if frame == NewWindowFrame.first(size: size, visible: visible) { startedOver += 1 }
                previous = frame
            }
            #expect(startedOver > 1)  // the bottom or right edge was reached and the cascade began again
        }
    }

    @Test func aWindowAfterOneElsewhereStartsAtTheFirstPosition() {
        let size = NewWindowFrame.size(visible: external, minimum: minimum)
        let first = NewWindowFrame.first(size: size, visible: external)
        // The window placed last is on the laptop's screen.
        let laptopSize = NewWindowFrame.size(visible: laptop, minimum: minimum)
        let onLaptop = NewWindowFrame.first(size: laptopSize, visible: laptop)
        #expect(NewWindowFrame.next(size: size, visible: external, after: onLaptop) == first)
        // The window placed last was dragged to the bottom of this screen.
        let dragged = CGRect(x: 2000, y: -150, width: 1440, height: 900)
        #expect(NewWindowFrame.next(size: size, visible: external, after: dragged) == first)
        // And one a step away from the first position still cascades from where it is.
        let moved = first.offsetBy(dx: -100, dy: 0)
        #expect(NewWindowFrame.next(size: size, visible: external, after: moved) == moved.offsetBy(dx: 29, dy: -29))
    }
}

@Suite struct LastPlacedWindowTests {
    /// Stands in for an `NSWindow`: a window is an object, held by whatever still uses it.
    private final class Window {}

    @Test func aWindowClosedWhileSomethingStillHoldsItIsNoLongerTheOneToStepFrom() {
        var last = LastPlacedWindow<Window>()
        let first = Window(), second = Window()
        last.place(first)
        last.place(second)
        #expect(last.window === second)
        // Closed while a task waiting on it still holds it: the review's case, which a
        // weak reference alone kept as the window to step from.
        last.close(second)
        #expect(last.window == nil)
        withExtendedLifetime(second) {}
    }

    @Test func anotherWindowsClosingKeepsTheWindowPlacedLast() {
        var last = LastPlacedWindow<Window>()
        let earlier = Window(), latest = Window()
        last.place(earlier)
        last.place(latest)
        last.close(earlier)
        #expect(last.window === latest)
    }

    @Test func aFreedWindowIsForgottenWithoutClosing() {
        var last = LastPlacedWindow<Window>()
        do {
            let window = Window()
            last.place(window)
            #expect(last.window === window)
        }
        #expect(last.window == nil)
    }
}
