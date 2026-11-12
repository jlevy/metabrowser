import Darwin
import Foundation
import Testing
@testable import ShellCore

/// Which executables the app runs without being asked (mb-2i0h): only one that no
/// other account can change, nor any directory or link on the way to it.
@Suite struct ExecutableTrustTests {
    private let me: uid_t = 501
    private typealias Node = ExecutableTrust.Node

    private func dir(_ owner: uid_t = 501, _ mode: mode_t = 0o755) -> Node {
        Node(kind: .directory, owner: owner, mode: mode, acl: .harmless)
    }

    private func file(_ owner: uid_t = 501, _ mode: mode_t = 0o755) -> Node {
        Node(kind: .file, owner: owner, mode: mode, acl: .harmless)
    }

    private func link(_ target: String, _ owner: uid_t = 501) -> Node {
        Node(kind: .link(target), owner: owner, mode: 0o755, acl: .harmless)
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
        repointed["/opt/homebrew/bin/uv"] = link("/Volumes/Other/uv", 502)
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
        acl["/opt/homebrew/Cellar"] = Node(kind: .directory, owner: 501, mode: 0o755, acl: .grantsWrite)
        #expect(refusal("/opt/homebrew/bin/uv", in: acl)
            == "/opt/homebrew/Cellar has an access control entry that grants a right to change it")
    }

    /// A shared, writable directory on the login shell's `PATH`, as B1 describes.
    /// mb-f1tu: an access control list that could not be read counted as one that grants
    /// nothing, so a file another account could change through it was run.
    @Test func anAccessControlListThatCannotBeReadIsRefused() {
        var unreadable = tree()
        unreadable["/opt/homebrew/Cellar/uv/0.9.0/bin/uv"] = Node(
            kind: .file, owner: 0, mode: 0o755, acl: .unreadable(EACCES))
        #expect(refusal("/opt/homebrew/bin/uv", in: unreadable)
            == "/opt/homebrew/Cellar/uv/0.9.0/bin/uv has an access control list that could not be read (Permission denied)")
        var directory = tree()
        directory["/opt/homebrew/bin"] = Node(kind: .directory, owner: 501, mode: 0o755, acl: .unreadable(ENOMEM))
        #expect(refusal("/opt/homebrew/bin/uv", in: directory)
            == "/opt/homebrew/bin has an access control list that could not be read (Cannot allocate memory)")
    }

    /// The probe never runs a uv whose list could not be read.
    @Test func aUvWhoseAccessControlListCannotBeReadIsNeverRun() async {
        var nodes = tree()
        nodes["/opt/homebrew/Cellar/uv/0.9.0/bin/uv"] = Node(kind: .file, owner: 0, mode: 0o755, acl: .unreadable(EACCES))
        let ran = Recorder<String>()
        let env = DiscoveryEnvironment(
            home: "/Volumes/Home", environment: [:], saved: nil, shell: nil,
            isExecutable: { $0 == "/opt/homebrew/bin/uv" }, canonicalPath: { $0 },
            run: { spec, _ in
                ran.append(spec.executable)
                return CommandResult(status: 0, output: ["/elsewhere"])
            })
        let frozen = nodes
        let survey = await UvToolDirectory.survey(
            ["/opt/homebrew/bin/uv"], env: env,
            refusal: { ExecutableTrust.refusal($0, uid: 501, inspect: { frozen[$0] }) })
        #expect(survey.run == nil)
        #expect(survey.refused.map(\.path) == ["/opt/homebrew/bin/uv"])
        #expect(ran.all == [])
    }

    @Test func theLiveCheckTellsNoListFromAListItCannotRead() throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let file = directory.appending(path: "uv").path
        try "#!/bin/sh\n".write(toFile: file, atomically: false, encoding: .utf8)
        #expect(ExecutableTrust.live(file)?.acl == .harmless)  // none at all
        #expect(ExecutableTrust.live(directory.appending(path: "missing").path) == nil)
    }

    /// An entry that denies reading security information, even to the owner, makes the
    /// file one the app cannot examine: macOS then refuses `lstat` itself, and the check
    /// refuses the file rather than calling it missing.
    @Test func aListTheAppMayNotReadIsRefusedLive() async throws {
        let directory = try temporaryDirectory()
        defer { try? FileManager.default.removeItem(at: directory) }
        let file = directory.appending(path: "uv").path
        try "#!/bin/sh\n".write(toFile: file, atomically: false, encoding: .utf8)
        #expect(chmod(file, 0o755) == 0)
        let denied = await CommandRunner.live(
            LaunchSpec(executable: "/bin/chmod", arguments: ["+a", "everyone deny readsecurity", file]), .seconds(10))
        #expect(denied.succeeded)
        #expect(ExecutableTrust.live(file)?.kind == .unreadable(EACCES))
        #expect(ExecutableTrust.refusal(file) == "\(file) could not be examined (Permission denied)")
    }

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
