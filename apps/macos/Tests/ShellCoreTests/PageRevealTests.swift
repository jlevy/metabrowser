import Foundation
import Testing
@testable import ShellCore

/// A window covers its page with the status view until the navigation its `load`
/// submitted commits, and shows that navigation's provisional failure in place of the
/// page (`PageReveal`).
///
/// Review E1 on #363: one Boolean said whether the next commit would reveal the page, and
/// the server starting or failing left it set. So a navigation submitted before the
/// server failed could commit afterward and hide the failure and Retry, though the window
/// had no server, or fail late and replace the server's diagnostic with a page error.
@Suite struct PageRevealTests {
    private final class Navigation {}

    /// What happens to a window, in order.
    private enum Step {
        /// `load` submitted this navigation.
        case submitted(Navigation?)
        /// Server state replaced the page: the server started, failed, or waits.
        case supersede
        /// A reload after the content process died.
        case reloaded(Navigation)
        case commit(Navigation?)
        case failure(Navigation?, cancelled: Bool)
    }

    /// Runs `steps` against a fresh `PageReveal` and says what each did: a supersede
    /// "stopped" a load or found "none", a commit "revealed" the page, a failure
    /// "reported" itself, and a callback that changes nothing is "ignored".
    private func run(_ steps: [Step]) -> [String] {
        var reveal = PageReveal<Navigation>()
        return steps.map { step in
            switch step {
            case .submitted(let navigation):
                reveal.submitted(navigation)
                return "submitted"
            case .supersede:
                return reveal.supersede() ? "stopped" : "none"
            case .reloaded(let navigation):
                reveal.reloaded(navigation)
                return "reloaded"
            case .commit(let navigation):
                return reveal.reveals(onCommit: navigation) ? "revealed" : "ignored"
            case .failure(let navigation, let cancelled):
                return reveal.reports(failureOf: navigation, cancelled: cancelled) ? "reported" : "ignored"
            }
        }
    }

    private let load = Navigation()
    private let replacement = Navigation()

    @Test func theSubmittedNavigationsCommitRevealsThePageOnce() {
        #expect(
            run([.submitted(load), .commit(load), .commit(load), .supersede])
                == ["submitted", "revealed", "ignored", "none"])
    }

    /// The review's ordering: `load` submits, the server answers and exits, the window
    /// shows the failure, and then the load's commit, or its provisional failure, arrives.
    @Test func aLoadsCallbacksAfterTheServerFailedChangeNothing() {
        #expect(run([.submitted(load), .supersede, .commit(load)]) == ["submitted", "stopped", "ignored"])
        #expect(
            run([.submitted(load), .supersede, .failure(load, cancelled: false)])
                == ["submitted", "stopped", "ignored"])
    }

    /// After a replacement load starts, the old load's commit and failure change nothing,
    /// whether the server restarted between them or not, and the replacement's commit
    /// reveals the page.
    @Test func anOldLoadsCallbacksAfterAReplacementLoadChangeNothing() {
        #expect(
            run([
                .submitted(load), .supersede, .submitted(replacement), .commit(load),
                .failure(load, cancelled: false), .commit(replacement),
            ]) == ["submitted", "stopped", "submitted", "ignored", "ignored", "revealed"])
        #expect(
            run([
                .submitted(load), .submitted(replacement), .commit(load), .failure(load, cancelled: false),
                .failure(load, cancelled: true), .commit(replacement),
            ]) == ["submitted", "submitted", "ignored", "ignored", "ignored", "revealed"])
    }

    /// The replacement load's own provisional failure is the window's to report, once.
    @Test func aReplacementLoadsFailureIsReported() {
        #expect(
            run([
                .submitted(load), .supersede, .submitted(replacement), .failure(replacement, cancelled: false),
                .commit(replacement),
            ]) == ["submitted", "stopped", "submitted", "reported", "ignored"])
    }

    /// A navigation the window did not submit, such as the page's own, changes nothing
    /// while the window's load is on its way.
    @Test func aNavigationTheWindowDidNotSubmitChangesNothing() {
        let pages = Navigation()
        #expect(
            run([
                .submitted(load), .commit(pages), .failure(pages, cancelled: false), .commit(nil), .commit(load),
            ]) == ["submitted", "ignored", "ignored", "ignored", "revealed"])
    }

    /// The window's load cancelled by a navigation it did not start: the next commit
    /// reveals the page, as the Boolean let it, until server state supersedes that.
    @Test func aLoadCancelledByAnotherNavigationPassesTheRevealOn() {
        #expect(
            run([.submitted(load), .failure(load, cancelled: true), .commit(Navigation())])
                == ["submitted", "ignored", "revealed"])
        #expect(
            run([
                .submitted(load), .failure(load, cancelled: true), .supersede, .commit(Navigation()),
                .failure(Navigation(), cancelled: false),
            ]) == ["submitted", "ignored", "stopped", "ignored", "ignored"])
    }

    /// WebKit may return no navigation from `load`; the next commit then reveals the page.
    @Test func aLoadWebKitDidNotNameRevealsOnTheNextCommit() {
        #expect(run([.submitted(nil), .commit(Navigation())]) == ["submitted", "revealed"])
    }

    /// A reload after the content process died stands in for a load still on its way;
    /// a reload of a page already shown reveals nothing, since nothing covers it.
    @Test func aRecoveryReloadRevealsInPlaceOfTheLoad() {
        let reload = Navigation()
        #expect(
            run([.submitted(load), .reloaded(reload), .commit(load), .commit(reload)])
                == ["submitted", "reloaded", "ignored", "revealed"])
        #expect(run([.reloaded(reload), .commit(reload)]) == ["reloaded", "ignored"])
    }
}
