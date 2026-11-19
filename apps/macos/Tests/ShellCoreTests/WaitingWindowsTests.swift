import Foundation
import Testing

@testable import ShellCore

@Suite struct WaitingWindowsTests {
    private final class Window {}

    private let notes = URL(filePath: "/folders/notes")
    private let fdu = URL(filePath: "/folders/src/fdu")

    @Test func aFolderChosenInAWindowOpensThereOnceReleased() {
        let window = Window()
        var waiting = WaitingWindows<Window>()
        waiting.wait(notes, in: window)
        let released = waiting.release([fdu, notes])
        // In the order the runtime selection released them; a folder asked for with no
        // window opens as a new folder does.
        #expect(released.map(\.folder) == [fdu, notes])
        #expect(released[0].window == nil)
        #expect(released[1].window === window)
    }

    @Test func aWindowClosedWhileItsFolderWaitsLeavesItToANewWindow() {
        var waiting = WaitingWindows<Window>()
        do {
            let window = Window()
            waiting.wait(notes, in: window)
        }
        #expect(waiting.release([notes]).map(\.window).allSatisfy { $0 == nil })
    }

    @Test func theLaterRequestNamesTheWindow() {
        let first = Window()
        let second = Window()
        var waiting = WaitingWindows<Window>()
        waiting.wait(notes, in: first)
        waiting.wait(notes, in: second)
        #expect(waiting.release([notes]).first?.window === second)
    }

    @Test func releasingForgetsEveryWindow() {
        let window = Window()
        var waiting = WaitingWindows<Window>()
        waiting.wait(notes, in: window)
        waiting.wait(fdu, in: window)
        _ = waiting.release([notes])
        // A folder asked for again later, without a window, opens in a new one.
        #expect(waiting.release([fdu]).first?.window == nil)
    }
}
