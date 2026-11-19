import Foundation
import Testing
@testable import ShellCore

/// Which open checkout's window a link's new mirror window joins as a tab.
@Suite struct CheckoutWindowTests {
    private let demo = URL(string: "https://github.com/octo/demo")!
    private let other = URL(string: "https://github.com/octo/other")!

    private func folder(_ path: String, _ repository: URL?, shown: Bool = true) -> CheckoutWindow.Candidate {
        let root = SessionRoot.folder(URL(filePath: path, directoryHint: .isDirectory))
        return CheckoutWindow.Candidate(key: root.key, root: root, repository: repository, isShown: shown)
    }

    @Test func aCheckoutOfTheLinksRepositoryTakesItsMirrorAsATab() {
        let open = [folder("/work/notes", nil), folder("/work/demo", demo), folder("/work/other", other)]
        #expect(CheckoutWindow.host(for: demo, among: open) == "/work/demo")
    }

    /// Matched by the repository `origin` names, never by the folder's name.
    @Test func noCheckoutOfTheRepositoryLeavesThePlacementAsItWas() {
        let open = [folder("/work/demo", other), folder("/work/notes", nil)]
        #expect(CheckoutWindow.host(for: demo, among: open) == nil)
        #expect(CheckoutWindow.host(for: demo, among: []) == nil)
    }

    /// `open` is most recently shown first (`OpenFolders.byRecency`): the checkout the
    /// reader was last working in wins.
    @Test func ofSeveralCheckoutsTheOneShownMostRecentlyTakesIt() {
        let open = [folder("/work/notes", nil), folder("/work/demo-worktree", demo), folder("/work/demo", demo)]
        #expect(CheckoutWindow.host(for: demo, among: open) == "/work/demo-worktree")
        #expect(CheckoutWindow.host(for: demo, among: Array(open.reversed())) == "/work/demo")
    }

    /// A checkout in the background, or only in a minimized window, has no window on
    /// screen to join; one that is shown is passed to instead.
    @Test func aCheckoutWithNoWindowOnScreenIsPassedOver() {
        let open = [folder("/work/demo", demo, shown: false), folder("/work/demo-worktree", demo)]
        #expect(CheckoutWindow.host(for: demo, among: open) == "/work/demo-worktree")
        #expect(CheckoutWindow.host(for: demo, among: [folder("/work/demo", demo, shown: false)]) == nil)
    }

    /// A mirror is never a checkout: a mirror of the repository would have been given
    /// the link itself (`AppDelegate.open(_:with:)`).
    @Test func onlyALocalFolderIsACheckout() {
        let mirror = SessionRoot.repository(demo)
        let open = [CheckoutWindow.Candidate(key: mirror.key, root: mirror, repository: demo, isShown: true)]
        #expect(CheckoutWindow.host(for: demo, among: open) == nil)
    }

    @Test func letterCaseNamesNoOtherRepository() {
        let open = [folder("/work/demo", URL(string: "https://github.com/Octo/Demo")!)]
        #expect(CheckoutWindow.host(for: demo, among: open) == "/work/demo")
    }

    /// The route's `repository`, which the app reads from every folder's server.
    @Test func theIdentityRouteNamesTheRepository() {
        let body = Data("""
            {"short_name": "demo", "full_name": "~/work/demo", "kind": "folder",
             "kind_label": "Local folder", "title": "demo • Metabrowser",
             "repository": "https://github.com/octo/demo"}
            """.utf8)
        guard case .identity(let identity) = IdentityClient.answer(status: 200, body: body) else {
            Issue.record("expected an identity")
            return
        }
        #expect(identity.repository == demo)
        let none = Data("""
            {"short_name": "notes", "full_name": "~/notes", "kind": "folder",
             "kind_label": "Local folder", "title": "notes • Metabrowser", "repository": null}
            """.utf8)
        guard case .identity(let plain) = IdentityClient.answer(status: 200, body: none) else {
            Issue.record("expected an identity")
            return
        }
        #expect(plain.repository == nil)
    }
}
