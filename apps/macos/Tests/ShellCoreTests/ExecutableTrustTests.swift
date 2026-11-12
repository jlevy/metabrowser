import Darwin
import Foundation
import Testing
@testable import ShellCore

/// Which executables the app runs without being asked (PR #361 B1): only one that no
/// other account can change, nor any directory or link on the way to it.
@Suite struct ExecutableTrustTests {
    private let me: uid_t = 501
    private typealias Node = ExecutableTrust.Node

    private func dir(_ owner: uid_t = 501, _ mode: mode_t = 0o755) -> Node {
        Node(kind: .directory, owner: owner, mode: mode, aclGrantsWrite: false)
    }

    private func file(_ owner: uid_t = 501, _ mode: mode_t = 0o755) -> Node {
        Node(kind: .file, owner: owner, mode: mode, aclGrantsWrite: false)
    }

    private func link(_ target: String, _ owner: uid_t = 501) -> Node {
        Node(kind: .link(target), owner: owner, mode: 0o755, aclGrantsWrite: false)
    }

    /// A Homebrew-style tree: `/` and `/opt` belong to root, the prefix to the user, and
    /// the command is a relative link into the Cellar.
    private func tree() -> [String: Node] {
        [
            "/": dir(0), "/opt": dir(0), "/opt/homebrew": dir(), "/opt/homebrew/bin": dir(),
            "/opt/homebrew/bin/uv": link("../Cellar/uv/0.9.0/bin/uv"), "/opt/homebrew/Cellar": dir(),
            "/opt/homebrew/Cellar/uv": dir(), "/opt/homebrew/Cellar/uv/0.9.0": dir(),
            "/opt/homebrew/Cellar/uv/0.9.0/bin": dir(), "/opt/homebrew/Cellar/uv/0.9.0/bin/uv": file(),
        ]
    }

    private func refusal(_ path: String, in nodes: [String: Node]) -> String? {
        ExecutableTrust.refusal(path, uid: me, inspect: { nodes[$0] })
    }

    @Test func aChainOwnedByTheUserAndRootIsRun() {
        #expect(refusal("/opt/homebrew/bin/uv", in: tree()) == nil)
        #expect(refusal("/opt/homebrew/Cellar/uv/0.9.0/bin/uv", in: tree()) == nil)
    }

    @Test func anythingOnTheWayThatAnotherAccountOwnsIsRefused() {
        var prefix = tree()
        prefix["/opt/homebrew"] = dir(502)
        #expect(refusal("/opt/homebrew/bin/uv", in: prefix) == "/opt/homebrew belongs to another account (uid 502)")
        var target = tree()
        target["/opt/homebrew/Cellar/uv/0.9.0/bin/uv"] = file(502)
        #expect(refusal("/opt/homebrew/bin/uv", in: target)
            == "/opt/homebrew/Cellar/uv/0.9.0/bin/uv belongs to another account (uid 502)")
        var repointed = tree()
        repointed["/opt/homebrew/bin/uv"] = link("/Users/other/uv", 502)
        #expect(refusal("/opt/homebrew/bin/uv", in: repointed) == "/opt/homebrew/bin/uv belongs to another account (uid 502)")
    }

    @Test func aDirectoryOrFileOthersMayWriteIsRefused() {
        var group = tree()
        group["/opt/homebrew/bin"] = dir(501, 0o775)
        #expect(refusal("/opt/homebrew/bin/uv", in: group) == "/opt/homebrew/bin can be changed by its group")
        var everyone = tree()
        everyone["/opt/homebrew/Cellar/uv/0.9.0/bin/uv"] = file(501, 0o757)
        #expect(refusal("/opt/homebrew/bin/uv", in: everyone)
            == "/opt/homebrew/Cellar/uv/0.9.0/bin/uv can be changed by every account")
        var acl = tree()
        acl["/opt/homebrew/Cellar"] = Node(kind: .directory, owner: 501, mode: 0o755, aclGrantsWrite: true)
        #expect(refusal("/opt/homebrew/bin/uv", in: acl)
            == "/opt/homebrew/Cellar has an access control entry that grants a right to change it")
    }

    /// A shared, writable directory on the login shell's `PATH`, as B1 describes.
    @Test func aStickyWorldWritableDirectoryIsRefusedToo() {
        var nodes = tree()
        nodes["/opt/shared"] = dir(0, 0o1777)
        nodes["/opt/shared/uv"] = file()
        #expect(refusal("/opt/shared/uv", in: nodes) == "/opt/shared can be changed by every account")
    }

    @Test func linksAreFollowedAndBounded() {
        var nodes = tree()
        nodes["/opt/a"] = link("/opt/b", 0)
        nodes["/opt/b"] = link("a", 0)
        #expect(refusal("/opt/a/uv", in: nodes) == "/opt/a/uv passes through too many symbolic links")
        #expect(refusal("/opt/homebrew/missing", in: nodes) == "/opt/homebrew/missing does not exist")
        #expect(refusal("/opt/homebrew/bin", in: nodes) == "/opt/homebrew/bin is not a regular file")
        #expect(refusal("relative/uv", in: nodes) == "relative/uv is not an absolute path")
    }

    @Test func theLiveCheckReadsOwnershipModesAndAccessControlLists() async throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let bin = directory.appending(path: "bin").path
        try FileManager.default.createDirectory(atPath: bin, withIntermediateDirectories: false)
        let uv = bin + "/uv"
        try "#!/bin/sh\n".write(toFile: uv, atomically: false, encoding: .utf8)
        #expect(chmod(uv, 0o755) == 0)
        let alias = directory.appending(path: "uv-link").path
        try FileManager.default.createSymbolicLink(atPath: alias, withDestinationPath: "bin/uv")
        #expect(ExecutableTrust.refusal(uv) == nil)
        #expect(ExecutableTrust.refusal(alias) == nil)
        #expect(chmod(bin, 0o775) == 0)
        #expect(ExecutableTrust.refusal(alias) == "\(bin) can be changed by its group")
        #expect(chmod(bin, 0o755) == 0)
        let granted = await CommandRunner.live(
            LaunchSpec(executable: "/bin/chmod", arguments: ["+a", "everyone allow write", uv]), .seconds(10))
        #expect(granted.succeeded)
        #expect(ExecutableTrust.refusal(uv) == "\(uv) has an access control entry that grants a right to change it")
        // The deny entry every home folder has changes nothing.
        let removed = await CommandRunner.live(LaunchSpec(executable: "/bin/chmod", arguments: ["-N", uv]), .seconds(10))
        #expect(removed.succeeded)
        let denied = await CommandRunner.live(
            LaunchSpec(executable: "/bin/chmod", arguments: ["+a", "group:everyone deny delete", uv]), .seconds(10))
        #expect(denied.succeeded)
        #expect(ExecutableTrust.refusal(uv) == nil)
    }
}
