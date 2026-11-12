import Darwin
import Foundation
import Testing
@testable import ShellCore

/// Load tests that spawn thousands of real children. They run on their own, after the
/// rest of the suite (the `test` target in the app's Makefile skips this suite, then
/// runs only it): with every suite running in parallel, 3,600 spawns at once starved
/// the other suites' 2-second deadlines on a three-core CI runner.
@Suite struct ExitObservationStressTests {
    /// NOTE_EXIT can arrive before the exited child is waitable. The exit handler once
    /// looked for the exit without waiting and, finding none, never looked again:
    /// `waitForExit()` never returned and the zombie was never reaped. Before the fix,
    /// 5 to 11 of every 7,200 children exiting at once were lost that way, so this run of
    /// 3,600 is likely, not certain, to catch the defect; with the fix it always passes.
    @Test func everyExitIsObservedWhileManyChildrenExit() async {
        let lanes = 24
        let childrenPerLane = 150
        let lost = await withTaskGroup(of: [String].self) { group in
            for _ in 0..<lanes {
                group.addTask {
                    var lost: [String] = []
                    for _ in 0..<childrenPerLane {
                        let child: SpawnedProcess
                        do {
                            child = try SpawnedProcess(LaunchSpec(executable: "/usr/bin/true"))
                        } catch {
                            lost.append("spawn: \(error)")
                            continue
                        }
                        let exit = await firstResult(
                            within: .seconds(10), of: [{ @Sendable in await child.waitForExit() }])
                        if exit == nil { lost.append("pid \(child.pid)") }
                        child.release()
                    }
                    return lost
                }
            }
            var all: [String] = []
            for await lane in group { all += lane }
            return all
        }
        #expect(lost.isEmpty, "exits never observed: \(lost)")
    }
}
