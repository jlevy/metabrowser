import Foundation
import Testing
@testable import ShellCore

/// One command of `tests/golden/app-contract.txt`: what `metab` was run with, how it
/// exited, and what the app reads of what it printed.
nonisolated struct ContractBlock: Sendable {
    /// The variables set before `metab` on the command line.
    var environment: [String: String]
    /// What follows `metab` on the command line.
    var words: [String]
    var exit: Int32
    var stdout: [String]
    var stderr: [String]

    /// What `CommandRunner` hands a reader: one pipe carries both streams.
    var result: CommandResult { CommandResult(status: exit << 8, output: stdout + stderr) }

    /// The JSON object in stdout, from its first line to the end.
    var json: Data {
        let start = stdout.firstIndex(of: "{") ?? stdout.endIndex
        return Data(stdout[start...].joined(separator: "\n").utf8)
    }

    /// The status a route answered with, which `--api` prints above the answer.
    var httpStatus: Int? {
        stdout.lazy.compactMap { line in line.hasPrefix("status: ") ? Int(line.dropFirst("status: ".count)) : nil }.first
    }
}

/// The golden that `tests/test_app_contract_golden.py` writes: every command the app runs
/// and every route it asks, as `apps/macos/metab-contract.toml` declares them, with what
/// the app reads of each answer and nothing else. A command's JSON answer is in the lines
/// `metab` printed it in, which is what the app's readers search.
nonisolated enum ContractGolden {
    /// Where the golden's sandbox and the folder it serves are, here.
    static let sandbox = "/ROOT"
    static let served = "/ROOT/served"
    /// What stands for output the app shows a person and reads nothing of.
    static let shown = "<shown as written, not read>"
    /// What the golden holds for text the app shows and never reads: a message, or the
    /// rest of a line after the part the app parses. The words are `metab`'s to change.
    static let text = "<text>"
    /// What a value the app keeps or hands back unread is here: the golden says only that
    /// there is one, as `<opaque>`, and a cursor must survive being put in a query.
    static let opaque = "opaque-value"

    static var url: URL {
        var root = URL(filePath: #filePath)
        for _ in 0..<5 { root.deleteLastPathComponent() }
        return root.appending(path: "tests/golden/app-contract.txt")
    }

    /// The blocks by scenario, with each label of the golden replaced by a value the app's
    /// readers take: the sandbox's paths, and for the version the oldest the app runs.
    static func load() throws -> [String: ContractBlock] {
        let text = try String(contentsOf: url, encoding: .utf8)
            .replacingOccurrences(of: "<SERVED>", with: served)
            .replacingOccurrences(of: "<ROOT>", with: sandbox)
            .replacingOccurrences(of: "<opaque>", with: opaque)
            .replacingOccurrences(of: "<VERSION>", with: MetabRequirement.minimum)
        var blocks: [String: ContractBlock] = [:]
        var lines = text.split(separator: "\n", omittingEmptySubsequences: false).map(String.init)[...]
        if lines.last == "" { lines.removeLast() }
        while let header = lines.first {
            guard header.hasPrefix("# "), lines.count >= 3, lines.dropFirst().first?.hasPrefix("exit: ") == true,
                  lines.dropFirst(2).first == "--- stdout ---"
            else { throw Malformed(line: header) }
            let exit = Int32(lines[lines.startIndex + 1].dropFirst("exit: ".count))
            lines = lines.dropFirst(3)
            let stdout = Array(lines.prefix { $0 != "--- stderr ---" })
            lines = lines.dropFirst(stdout.count + 1)
            let stderr = Array(lines.prefix { $0 != "--- contract ---" })
            lines = lines.dropFirst(stderr.count + 1)
            guard let exit, let scenario = lines.first, blocks[scenario] == nil else { throw Malformed(line: header) }
            lines = lines.dropFirst()
            let (environment, words) = try command(String(header.dropFirst(2)))
            blocks[scenario] = ContractBlock(
                environment: environment, words: words, exit: exit, stdout: stdout, stderr: stderr)
        }
        return blocks
    }

    struct Malformed: Error { var line: String }

    /// A command line as the golden writes one: words separated by spaces, a word that
    /// holds a space or a shell character in single quotes, and `NAME=value` before `metab`.
    static func command(_ line: String) throws -> (environment: [String: String], words: [String]) {
        var words: [String] = []
        var word = ""
        var quoted = false
        for character in line {
            if character == "'" {
                quoted.toggle()
            } else if character == " ", !quoted {
                words.append(word)
                word = ""
            } else {
                word.append(character)
            }
        }
        words.append(word)
        var environment: [String: String] = [:]
        while let first = words.first, first != "metab", let equals = first.firstIndex(of: "=") {
            environment[String(first[..<equals])] = String(first[first.index(after: equals)...])
            words.removeFirst()
        }
        guard words.first == "metab" else { throw Malformed(line: line) }
        return (environment, Array(words.dropFirst()))
    }
}

/// The app's half of its contract with `metab`.
///
/// The golden holds what `metab` answers; these hold the app to it. Every command line in
/// it must be the one the app's own builder writes, and every answer must read, through
/// the app's own reader, as what the scenario is. The answers hold only the keys and lines
/// the contract declares, so a reader that began to read another finds it missing here.
/// Python's tests fail when `metab` changes an answer, and a change to the golden runs
/// this suite, so neither side moves alone (`docs/project/architecture/arch-app-contract.md`).
@Suite struct AppContractTests {
    private let blocks: [String: ContractBlock]
    private let served = URL(filePath: ContractGolden.served, directoryHint: .notDirectory)
    private let demo = URL(string: "https://github.com/octo/demo")!

    init() throws {
        blocks = try ContractGolden.load()
    }

    private func block(_ scenario: String) throws -> ContractBlock {
        try #require(blocks[scenario], "tests/golden/app-contract.txt has no scenario \(scenario)")
    }

    /// Every scenario a test below reads. A scenario the golden gains must be read here,
    /// and one it loses must be taken out, so the two lists cannot drift.
    private static let read: Set<String> = [
        "version-probe", "version", "unknown-option",
        "serve/folder", "serve/not-an-open", "serve/repository-cloned", "serve/repository-cached",
        "serve-path/file",
        "recent-list/empty", "recent-list/after-an-open", "recent-list/listed", "recent-list/problem",
        "recent-add/repository", "recent-forget/folder", "recent-clear",
        "identity/folder", "identity/under-home", "identity/checkout", "identity/mirror",
        "source-status/folder", "source-status/mirror",
        "present-dry-run/repository", "present-dry-run/pull-request", "present-dry-run/commit",
        "present-dry-run/tree", "present-dry-run/file", "present-dry-run/refused",
        "cache-sources/none", "cache-sources/held", "cache-sources/first-page", "cache-sources/next-page",
        "event-log/found", "event-log/empty",
        "doctor/clean", "doctor/as-the-app", "acquire/in-terminal",
    ]

    @Test func everyScenarioOfTheGoldenIsReadHere() {
        #expect(Set(blocks.keys) == Self.read)
    }

    // MARK: - Setup

    /// Validates `/opt/metab`, whose answers `answer` gives, and records what it was run with.
    private func validate(
        _ ran: Recorder<[String]>, _ answer: @escaping @Sendable ([String]) -> CommandResult
    ) async -> CandidateResult {
        let env = DiscoveryEnvironment(
            home: "/Volumes/Home", environment: [:], saved: nil, shell: nil,
            isExecutable: { _ in true }, canonicalPath: { $0 },
            run: { spec, _ in
                ran.append(spec.arguments)
                return answer(spec.arguments)
            },
            refusal: { _ in nil })
        return await RuntimeDiscovery.validate("/opt/metab", env, source: .localBin)
    }

    /// Setup probes with every flag the app needs and reads the version; a `metab` that
    /// rejects one, as this build rejects an option it does not know, is too old.
    @Test func setupProbesAMetabAndReadsItsVersion() async throws {
        let probe = try block("version-probe")
        let plain = try block("version")
        let unknown = try block("unknown-option")
        #expect(probe.words == RuntimeDiscovery.probeArguments)
        #expect(probe.words == MetabRequirement.requiredFlags + ["--version"])
        #expect(RuntimeDiscovery.parseVersion(probe.stdout) == MetabRequirement.minimum)

        let ran = Recorder<[String]>()
        let current = await validate(ran) { _ in probe.result }
        #expect(current == .valid(version: MetabRequirement.minimum))
        #expect(ran.all == [probe.words])

        // The golden's rejection names an option no build knows; a build from before the
        // newest flag names that flag, in the same words and with the same status.
        let option = try #require(unknown.words.first)
        let newest = try #require(MetabRequirement.requiredFlags.last)
        let rejection = CommandResult(
            status: unknown.exit << 8,
            output: unknown.result.output.map { $0.replacingOccurrences(of: option, with: newest) })
        #expect(unknown.exit == 2)
        #expect(unknown.result.output.contains { $0.contains(option) })
        #expect(RuntimeDiscovery.rejectsServeFlag(rejection))
        let asked = Recorder<[String]>()
        let older = await validate(asked) { $0 == plain.words ? plain.result : rejection }
        #expect(older == .tooOld(version: MetabRequirement.minimum))
        #expect(asked.all == [probe.words, plain.words])
    }

    // MARK: - Servers

    @Test func aFoldersServerIsStartedAndFoundAsRecorded() throws {
        let launch = CLIServeLaunch(basePort: LaunchLane.folders.basePort)
        let folder = try block("serve/folder")
        #expect(folder.words == launch.arguments(serving: served))
        #expect(folder.environment.isEmpty)
        #expect(folder.stdout.count == 1)
        let origin = try #require(URL(string: "http://127.0.0.1:\(LaunchLane.folders.basePort)"))
        #expect(launch.endpoint(announcedBy: folder.stdout[0])
            == ServerEndpoint(origin: origin, entryURL: origin.appending(path: "view/")))

        // A server that is not the start of something the user opened is told not to record.
        let quiet = try block("serve/not-an-open")
        let other = URL(filePath: ContractGolden.sandbox + "/other", directoryHint: .notDirectory)
        #expect(quiet.words == launch.arguments(serving: other))
        #expect(quiet.environment == [RecentTargets.recordVariable: "0"])
        #expect(launch.endpoint(announcedBy: quiet.stdout[0]) != nil)
    }

    @Test func aRepositorysStartSaysWhatItsCloneReportSays() throws {
        let launch = CLIServeLaunch(basePort: LaunchLane.repositories.basePort)
        let origin = try #require(URL(string: "http://127.0.0.1:\(LaunchLane.repositories.basePort)"))
        // The golden's repository is a file:// origin; the app's is a GitHub URL, which it
        // passes whole. Everything after the root is the same.
        #expect(launch.arguments(serving: demo).first == demo.absoluteString)
        for scenario in ["serve/repository-cloned", "serve/repository-cached"] {
            let block = try block(scenario)
            #expect(Array(block.words.dropFirst()) == Array(launch.arguments(serving: demo).dropFirst()))
            #expect(block.words.first?.contains("://") == true)
            #expect(launch.endpoint(announcedBy: block.stdout[0])?.origin == origin)
        }
        // The app parses the start of each line and shows the rest as `metab` wrote it,
        // which the golden holds as `<text>`.
        let rest = ContractGolden.text
        let cloned = try block("serve/repository-cloned")
        let finished = StartProgress.cloned("in \(rest)")
        #expect(cloned.stderr.map(StartProgress.parse) == [.cloning(into: rest), finished])
        #expect(launch.startProgress(in: cloned.result.output) == finished)
        let cached = try block("serve/repository-cached")
        #expect(cached.stderr.map(StartProgress.parse) == [.cached("cached in \(rest)")])
    }

    /// The page the app opens for a file is the address `metab` announces for it.
    @Test func aFilesPageIsTheAddressMetabAnnounces() throws {
        let launch = CLIServeLaunch(basePort: LaunchLane.folders.basePort)
        let block = try block("serve-path/file")
        let relative = try #require(block.words.last)
        #expect(block.words == launch.arguments(serving: served) + ["--path", relative])
        let endpoint = try #require(launch.endpoint(announcedBy: block.stdout[0]))
        let page = PageAddress.view(of: relative)
        #expect(PageAddress(endpoint.entryURL) == page)
        #expect(page.url(on: endpoint.origin) == endpoint.entryURL)
    }

    // MARK: - Recent targets

    @Test func openRecentListsWhatMetabRecorded() throws {
        let opened = ContractGolden.opaque
        let folder = RecentTarget(mode: .folder, root: ContractGolden.served, openedAt: opened)
        let mirror = RecentTarget(mode: .mirror, root: demo.absoluteString, openedAt: opened)
        let listings: [(String, [RecentTarget])] = [
            ("recent-list/empty", []), ("recent-list/after-an-open", [folder]), ("recent-list/listed", [mirror, folder]),
        ]
        for (scenario, targets) in listings {
            let block = try block(scenario)
            #expect(block.words == RecentTargets.listArguments)
            #expect(RecentTargets.answer(block.result) == .listing(.init(targets: targets)))
        }
        let rows = RecentTargets.items([mirror, folder], opensURLs: true, home: "/Volumes/Home")
        #expect(rows.map(\.url) == [demo, URL(filePath: ContractGolden.served, directoryHint: .isDirectory)])

        // A list this `metab` cannot read lists as empty, and says why.
        guard case .listing(let unread) = RecentTargets.answer(try block("recent-list/problem").result) else {
            Issue.record("a list with a problem was not read")
            return
        }
        #expect(unread.targets.isEmpty)
        #expect(unread.problem == ContractGolden.text)
    }

    @Test func theListIsChangedWithTheRecordedCommands() throws {
        let add = try block("recent-add/repository")
        let target = try #require(add.words.first)
        #expect(add.words == RecentTargets.addArguments(target))
        let forget = try block("recent-forget/folder")
        #expect(forget.words == RecentTargets.forgetArguments(ContractGolden.served))
        let clear = try block("recent-clear")
        #expect(clear.words == RecentTargets.clearArguments)
        for block in [add, forget, clear] { #expect(block.result.succeeded) }
    }

    // MARK: - Routes

    private func identity(_ scenario: String) throws -> IdentityAnswer {
        let block = try block(scenario)
        #expect(Array(block.words.dropFirst()) == ["--api", "/" + IdentityClient.path])
        return IdentityClient.answer(status: try #require(block.httpStatus), body: block.json)
    }

    /// A window is named by the server, as the app names it from the path until then.
    @Test func aWindowIsNamedAsTheServerNamesIt() throws {
        #expect(try identity("identity/folder") == .identity(.localFolder(served, home: "/Volumes/Home")))
        #expect(try block("identity/under-home").environment == ["HOME": ContractGolden.sandbox])
        #expect(try identity("identity/under-home") == .identity(.localFolder(served, home: ContractGolden.sandbox)))

        // A checkout names its GitHub repository as a link's dry run names the link's.
        guard case .identity(let checkout) = try identity("identity/checkout") else {
            Issue.record("a checkout's identity was not read")
            return
        }
        #expect(checkout.kind == .folder)
        #expect(checkout.repository == demo)
        guard case .plan(let plan) = PresentDryRun.answer(try block("present-dry-run/repository").result) else {
            Issue.record("a repository link was not resolved")
            return
        }
        #expect(CheckoutWindow.same(try #require(checkout.repository), plan.repository))
        #expect(checkout.repository == plan.repository)

        guard case .identity(let mirror) = try identity("identity/mirror") else {
            Issue.record("a mirror's identity was not read")
            return
        }
        let named = FolderIdentity.repository(demo)
        #expect(mirror.kind == .mirror)
        #expect(mirror.kindLabel == named.kindLabel)
        #expect(mirror.title == FolderIdentity.title(for: mirror.shortName))
    }

    @Test func aSourceWithNothingToFetchHasNothingToSay() throws {
        for scenario in ["source-status/folder", "source-status/mirror"] {
            let block = try block(scenario)
            #expect(Array(block.words.dropFirst()) == ["--api", "/" + LinkSelection.route])
            let status = try #require(block.httpStatus)
            #expect(LinkSelection.read(status: status, body: block.json) == .settled(.shown))
        }
    }

    // MARK: - Links

    @Test func aLinkResolvesToEachKindTheAppKnows() throws {
        let plans: [(String, PresentPlan.Kind, String)] = [
            ("repository", .repository, "https://github.com/octo/demo"),
            ("pull-request", .pullRequest, "https://github.com/octo/demo/pull/12/files"),
            ("commit", .commit, "https://github.com/octo/demo/commit/523f476b"),
            ("tree", .tree, "https://github.com/octo/demo/tree/main/docs"),
            // Sent with a token in its query, which the handoff drops.
            ("file", .file, "https://github.com/octo/demo/blob/main/README.md"),
        ]
        #expect(Set(plans.map(\.1)) == Set(PresentPlan.Kind.allCases))
        for (name, kind, handoff) in plans {
            let block = try block("present-dry-run/\(name)")
            let sent = try #require(block.words.first)
            let link = try #require(URL(string: sent))
            #expect(GitHubLink.accepts(link))
            #expect(block.words == PresentDryRun.arguments(for: link))
            let opened = try #require(URL(string: handoff))
            #expect(PresentDryRun.answer(block.result) == .plan(PresentPlan(kind: kind, repository: demo, link: opened)))
        }
    }

    @Test func aRefusalIsReadWithItsStatus() throws {
        let block = try block("present-dry-run/refused")
        #expect(block.exit != 0)
        // The code is `metab`'s name for the refusal; the message is shown as written.
        #expect(PresentDryRun.answer(block.result) == .refused(PresentRefusal(
            code: "unsupported_github_url", message: ContractGolden.text)))
    }

    // MARK: - The cache

    @Test func theCacheIsAskedPageByPage() throws {
        let folder = ContractGolden.sandbox + "/support"
        // The golden's cache holds `demo`, under two addresses, and lists `alpha`, which
        // it never published.
        let listedOnly = try #require(URL(string: "https://github.com/octo/alpha"))
        let none = try block("cache-sources/none")
        #expect(none.words == RepositoryCache.arguments(folder: folder, after: nil))
        #expect(RepositoryCache.read(none.result, looking: demo) == .end)

        let held = try block("cache-sources/held")
        #expect(held.words == RepositoryCache.arguments(folder: folder, after: nil))
        #expect(RepositoryCache.read(held.result, looking: demo) == .found)
        // Listed, and not published: a link to it still asks before it clones.
        #expect(RepositoryCache.read(held.result, looking: listedOnly) == .end)

        // The golden asks for a page shorter than the app's, to show a cursor.
        func short(_ arguments: [String]) -> [String] {
            arguments.map { $0.replacingOccurrences(of: "limit=\(RepositoryCache.pageLimit)", with: "limit=2") }
        }
        let first = try block("cache-sources/first-page")
        #expect(first.words == short(RepositoryCache.arguments(folder: folder, after: nil)))
        guard case .next(let cursor) = RepositoryCache.read(first.result, looking: demo) else {
            Issue.record("a short page gave no cursor")
            return
        }
        #expect(cursor == ContractGolden.opaque)
        let next = try block("cache-sources/next-page")
        #expect(next.words == short(RepositoryCache.arguments(folder: folder, after: cursor)))
        #expect(RepositoryCache.read(next.result, looking: demo) == .found)
    }

    // MARK: - The event log

    @Test func theEventLogIsFoundByItsNewestSegment() throws {
        let folder = ContractGolden.sandbox + "/support"
        // The golden's state directory holds two segments, listed newest first.
        let found = try block("event-log/found")
        #expect(found.words == EventLogLocation.arguments(folder: folder))
        let directory = ContractGolden.sandbox + "/events-state/events"
        #expect(EventLogLocation.read(found.result) == .found(
            URL(filePath: directory + "/events-20261119T210201Z-p4242-000.jsonl")))

        // A log directory with no segment is an answer, and the app says there is none yet.
        let empty = try block("event-log/empty")
        #expect(empty.words == EventLogLocation.arguments(folder: folder))
        #expect(EventLogLocation.read(empty.result) == .empty(
            URL(filePath: ContractGolden.sandbox + "/quiet-state/events", directoryHint: .isDirectory)))
    }

    // MARK: - Check Setup

    /// Help > Check Setup… runs the doctor as `DoctorRun.spec` writes it, naming this
    /// app's bundle, and reads one row per check and one for GitHub CLI, with the step
    /// that fixes each. A report with a problem exits 1 and is still a report.
    @Test func checkSetupReadsEachCheckOfTheDoctorsReport() throws {
        let bundle = "\(ContractGolden.sandbox)/Metabrowser.app"
        let spec = DoctorRun.spec(
            setup: RuntimeSetup(
                runtime: Runtime(executable: "/opt/metab", version: MetabRequirement.minimum, source: .chosen),
                tools: ToolPaths()),
            inherited: [:], appBundle: bundle)
        let ids = ["plugins", "open_in", "metab", "git", "config", "cache", "github"]

        let clean = try block("doctor/clean")
        #expect(clean.words == spec.arguments)
        guard case .report(let report) = DoctorRun.answer(clean.result) else {
            Issue.record("a report with nothing to fix was not read")
            return
        }
        #expect(report.ok && report.hasChecks)
        #expect(report.rows.map(\.id) == ids)
        #expect(report.rows.allSatisfy { $0.state == .ok && $0.remedy == nil })

        let app = try block("doctor/as-the-app")
        #expect(app.words == spec.arguments)
        #expect(app.environment[DoctorRun.appVariable] == spec.environment[DoctorRun.appVariable])
        guard case .report(let found) = DoctorRun.answer(app.result) else {
            Issue.record("a report with a problem was not read")
            return
        }
        #expect(!found.ok && found.hasChecks)
        #expect(found.rows.map(\.id) == ids)
        #expect(found.rows.map(\.state) == [.ok, .ok, .warning, .ok, .warning, .problem, .warning])
        let fixes = Dictionary(uniqueKeysWithValues: found.rows.map { ($0.id, $0.remedy) })
        let step = DoctorReport.Remedy(text: ContractGolden.text, command: ContractGolden.text)
        #expect(fixes["metab"] == step, "the upgrade the app's minimum calls for")
        #expect(fixes["github"] == step, "signing in to GitHub CLI")
        #expect(fixes["config"] == DoctorReport.Remedy(text: ContractGolden.text))
    }

    // MARK: - Shown, not read

    /// The app reads nothing of this: the status view shows the clone command for a person
    /// to run.
    @Test func whatTheAppOnlyShowsIsNotRecorded() throws {
        let acquire = try block("acquire/in-terminal")
        #expect(acquire.stdout == [ContractGolden.shown])
        let failure = GitHubFailure(kind: .network, state: "timed_out", message: "", repository: demo)
        #expect(failure.steps.map(\.command)
            == ["metab " + ([demo.absoluteString] + acquire.words.dropFirst()).joined(separator: " ")])
    }
}
