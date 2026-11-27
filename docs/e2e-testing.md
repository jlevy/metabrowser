# End-to-End Testing

Metabrowser uses layered tests so server routes, browser contracts, plugins, and built
artifacts can fail independently and report a useful cause.

## Test Layers

### Python Unit and Route Tests

Pytest covers safe path resolution, inventory state, kind classification, manifest
validation, data-hook routing, log parsing, and HTTP response envelopes.
Lightweight request doubles exercise handlers directly when a network client would add
no value.

### Application Lifespan Tests

The lifespan suite starts the real Starlette application wiring, waits for the initial
inventory, and verifies tree, recent, capabilities, events, and watcher behavior.
These tests prove that startup and teardown tasks cooperate; individual route tests do
not.

### JavaScript Contract Tests

Node `vm` shims load the real SDK and every built-in `index.js` with small browser
stubs. They verify:

- every declared view has a matching registration;
- plugins do not read unloaded built-in namespaces at module-load time;
- KPress assets load once and failure paths remain visible;
- renderers can mount with their documented context shape.

These are contract tests, not visual browser tests.
Keep the shims small instead of growing an incomplete DOM implementation.

### Browserless Functional Sessions

Deterministic view behavior runs from a command line against the same production
JavaScript the shell loads.
A session composes the relevant modules and prints the observable request and state
transitions as a golden transcript.
It does not duplicate the behavior in Python and does not invent a general fake browser.
Platform fallbacks that change interaction remain interaction behavior rather than a
paint exemption. Pin the native-capability path, fallback path, scheduling bound, and
disposal against the exact production modules.

`cli-ui-navigation.tryscript.md` is the reference case.
It combines the production filter-control transition, request launch, Recent tree model,
and bounded expansion planner over several collapsed matching folders.
The transcript records the exact API request, selected leaves, folder counts, and
bounded expansion plan.
It also records the exact live-change batch, deep-change and reconnect repair decisions,
capped-page backfill, retained-map bound, and fixed-window event coalescing.
A focused source invariant ensures the Recent path cannot apply DOM-row membership after
that model is rendered; focused Node assertions remain beside the golden so a failure
identifies the responsible transform.

`cli-ui-markdown-scrollspy.tryscript.md` applies the same pattern to rendered Markdown
in one composed command.
It enters through the production rendered-Markdown mount, which runs the link enhancer
over authored same-document TOC anchors before passing them to the installed KPress TOC,
in a runtime without `IntersectionObserver` so KPress’s own scroll fallback runs.
The transcript records the delegated target and active section through a long document,
including frame coalescing and lifecycle disposal.

### Golden CLI Transcripts

`tests/golden/*.tryscript.md` are markdown files holding shell commands and their exact
expected output. [tryscript](https://github.com/jlevy/tryscript) runs each command in a
fresh sandbox and diffs the result, so a transcript is both a test and a readable record
of what the command does.

This is the layer that proves **routes**, because `metab --api <route>` issues a real
request through the real application: the same middleware, routing, and serialization
the browser reaches.
Fixtures pin mtimes with `touch -t` and Git identity and dates, so commit revisions are
byte-identical on every machine and transcripts assert real values.
Regenerate with `make golden-update` only to record an intended change, then read the
diff line by line.
[CLI and Functional UI Parity](development.md#cli-and-functional-ui-parity) gives the
reasons: why `--walk` and `--diff` prove a model and not the wire, what counts as
evidence for a route, and why only what no fixture can pin is normalized.

tryscript runs its files one after another, so `make test` runs them through
`devtools/run_goldens.py`, `GOLDEN_JOBS` files at a time; the `Makefile` holds the value
and the measurement that chose it.
The runner prints each file’s output whole when the file finishes, then a `golden:` line
with its verdict and time, and fails unless every file the pattern matches printed its
own `PASS` verdict. A file that printed no verdict fails the run, and so does a pattern
that matches nothing.
`make test GOLDEN_JOBS=1` runs them one at a time, and
`make test-goldens GOLDENS='<file or pattern>...'` runs only those.
`make test-goldens SHARD=I/N` runs the Ith of N parts, which CI uses to split the
goldens across jobs; the runner’s docstring says how the files are dealt and why by
size.

### One Harness and One Update Command

`tests/golden_harness.py` is the one place an expectation is compared or rewritten, and
the only reader of `GOLDEN_UPDATE`. It serves the two kinds of expectation pytest owns:

- **In-process transcripts**, `tests/golden/*.txt`, for commands a subprocess cannot
  run: serve mode, and acquisition, which a Git below the acquisition floor refuses.
  A driver runs `metab` through the console script’s entry point and renders each
  command’s line, exit status, and both streams in full, except a payload it shows once
  ([What a Transcript May Replace](#what-a-transcript-may-replace)).
- **Recorded response fixtures**, `tests/fixtures/*.json`, which a browserless session
  replays so that it runs on what the server answered and not on envelopes a test wrote
  by hand. The recorder replays the story against the real application and fails when the
  committed recording no longer matches.

`make golden-update` runs in dependency order: the recorders, then tryscript and
`devtools/golden_fixup.py`, then the in-process drivers.
A session’s transcript is built from its recording, so recording first is what stops a
transcript being rewritten from a stale input.
The recorders and drivers run through `devtools/golden_update.py`, under which no test
may skip (see [Skips](#skips)): a host without Node, or with a Git below the acquisition
floor, cannot report that it regenerated what it skipped.

`make golden-update ONLY='<file>...'` runs the same steps on only the transcripts and
modules it names, and stops before writing anything when a name is neither a transcript
nor a module of either list; the `Makefile` says how a name is matched.
Naming only what an intended change touches keeps a regeneration from also recording
what this machine gets wrong, such as a test that fails here and passes in CI.

`devtools/check_goldens.py`, part of `make lint-check`, keeps that true and keeps a
transcript from passing while wrong:

- every module that calls the harness is in the Makefile list `golden-update` runs, the
  recipe keeps the order above, and every committed `.txt` transcript is named by a
  driver;
- a `metab` or `node` invocation in a transcript is the last command of its block, or
  the line prints its status with `; echo "exit: $?"` directly after it.
  A block has one exit status, the last command’s, so a pipe, a `;`, or an `||` after
  the command under test records another command’s status.
  Redirect the command to a file, record its own `? N`, and filter the file in the next
  block;
- no transcript is empty, holds a command outside the blocks tryscript runs, or
  annotates a test `skip` or `only`. tryscript runs a block that opens on an unindented
  line of backticks and `console` or `bash`, and nothing else;
  `devtools/tryscript_blocks.py` reads transcripts the way tryscript does, and
  `check_parity.py` uses the same reading;
- no golden or recording is over the review budget.
  The limit, the measurement it was chosen from, and the files excepted until a named
  bead shrinks them are beside `MAX_GOLDEN_LINES`. An excepted file has its line count
  as a ceiling, so it can shrink and cannot grow.
  `uv --config-file uv.toml run --frozen python -m devtools.check_goldens --report`
  prints the current distribution.

### What a Transcript May Replace

A value is replaced only when no fixture can pin it, and by a pattern as narrow as the
value: a time is `[TIMESTAMP]` and a counter `[COUNT]`, not `[..]`. In-process
transcripts fix the clock and build every origin with pinned identities and dates, so
times and commit IDs are literal; the placeholders that remain, each with the reason no
fixture can pin it, are listed at the top of `tests/golden_harness.py`. For tryscript,
`devtools/golden_fixup.py` is that list.

A payload that repeats is shown once, and a marker stands where it repeats.
Each marker is written after comparing, so what stopped repeating is printed.

- **A record a story reads many times.** A pull envelope carries the whole record, so
  `cli-github-pull-refresh.txt` prints a record in full the first time and as
  `<RECORD n>` while a later read equals it, and
  `tests/fixtures/github-pull-page-responses.json` holds a record in the first answer
  that carried it and names that answer, `{"same_as": "current"}`, in the later ones,
  which the session reads back as that record.
  A record that differs is written in full, so a read that changed it shows as a whole
  record where the reference was.
- **A run of lines a later command repeats.** Every `/api/tree` answer carries the whole
  pin’s tallies, so `cli-git-pin-tree.txt` prints them in its first block, and each
  later block says how many lines it repeats and where they begin:
  `<157 lines, from … on, are the same as in '/api/tree?depth=0' above>`. The driver
  finds the run by comparing the two outputs, so the lines that stopped repeating print,
  and the marker’s count changes.

A transcript must not depend on how busy the machine is.
The server logs a request slower than `SLOW_OPERATION_LOG_SECONDS` (`settings.py`) to
stderr, which a transcript captures, so the Make targets run tryscript with
`METABROWSER_SLOW_SERVER_MS` set past tryscript’s own command timeout.
Run tryscript through `devtools/tryscript.sh`, the `Makefile`’s `TRYSCRIPT`, which sets
that variable and the rest of the goldens’ environment and says why, so a command typed
in a shell runs a golden as `make test` does.

### Distribution Tests

`make build` inspects the wheel for required static assets and rejects repository-only
files. It then creates an isolated uv environment from the wheel and imports the package
and CLI. This catches missing package data and source-checkout assumptions.

## Running Tests

[Everyday Commands](development.md#everyday-commands) lists the commands.
Node, Git, and jq are prerequisites; jq runs the CI workflow’s `plan` and `ci-ok`
scripts, which their tests run too.
The first test that needs one and finds it missing stops the run, with one message that
names the tool and the way to opt out.
It does so in CI and locally alike: a run that skipped those tests would pass without
checking any of the browser contracts under `tests/dom`. A run that selects no test
needing the tool is not affected.
A developer who has no Node names it in `METABROWSER_ALLOW_MISSING_TOOLS`, and the tests
that need it skip with that reason:

```shell
METABROWSER_ALLOW_MISSING_TOOLS=node uv --config-file uv.toml run --frozen pytest -rs
```

The variable takes `node`, `git`, or `jq`, or several of them separated by commas.
`tests/required_tools.py` is the gate, and a test asks it rather than looking the tool
up itself; a test in `tests/test_suite_gates.py` fails when one does.

The tryscript goldens need jq too: `tests/golden/cli-skill-recipes.tryscript.md` reads
the answers of the agent skill’s recipes with it, as an agent does.
That transcript names it under `requires`, so tryscript stops before it runs any golden
when jq is missing and names the directories it searched;
`METABROWSER_ALLOW_MISSING_TOOLS` does not reach tryscript.
No CI step installs jq: the GitHub-hosted Ubuntu runner image provides it.

### Transient Output

A pytest session writes under `pytest-of-$USER/pytest-<N>` in the system temporary
directory (`$TMPDIR` on macOS), one directory per test and, under pytest-xdist, one
`popen-gw<N>` per worker.
pytest keeps them all (`tmp_path_retention_policy = "all"` in `pyproject.toml`), and
`tests/conftest.py` removes what no one reads.
After a test’s teardown it empties the test’s `tmp_path`, unless the test failed or
errored in its setup, its call, or its teardown.
It keeps the empty directory, so that no later test in the session is handed the same
path: a process-wide cache keyed by path would carry the earlier test’s state into it.
As a passing session ends it removes the session’s whole directory.
So what stays is the `tmp_path` of each test that failed or errored, beside the
directories that session-scoped fixtures made, until pytest prunes the session among the
oldest beyond `tmp_path_retention_count`. A session killed before it ended leaves its
lock, which would hold the directory for days; the next session to end releases such a
lock once its process has gone, so pytest prunes the directory too.
`tests/transient_output.py` has the measurements, and `tests/test_transient_output.py`
holds the policy and the pruning.

Nothing in that directory outlives a session to save a later one time: what saves time,
such as the stand-in GitHub origin (`tests/conftest.py`), is a session-scoped fixture,
built once per session and removed with it.
A Chrome test’s profile is a directory of its own in the system temporary directory,
removed after the test (`tests/process_group.py`), and Chrome starts with
`--disable-default-apps`, without which a session that ran past a few seconds left two
CRX files there (`tests/dom/chrome-session.mjs`).

## Test Tiers

`make test` is the default tier.
Three outer tiers hold evidence that the default tier cannot produce on every machine.
Each has one command, one way its tests are selected, and a stated time when it runs.

| Tier | Command | Selected by | When it runs |
| --- | --- | --- | --- |
| Default | `make test` | everything that does not skip | Every pull request in CI, as the [CI Jobs](#ci-jobs) on Ubuntu; the pre-push hook |
| Admitted Git | `make test-admitted-git` | `ADMITTED_GIT_TESTS` in the `Makefile` | Every pull request in CI, on the lowest admitted Git release, the newest patched one, and the release that reads file ages |
| macOS | `make test-macos` | the `macos_tier` marker | Never in CI. Part of `make test` on a Mac; run it there before a release |
| Live GitHub | `make test-live-github` | the `live_github` marker | Never in CI. By hand, before a release and after a change to GitHub URL or pull request reading |

**Admitted Git** runs acquisition, refresh, and store reads on Git releases the
production floor admits.
A test that asks for the floor through `require_admitted_git` or `_allow_installed_git`
meets the real one there, unpatched.
The same files also run in the default tier, where `_allow_installed_git` substitutes
the floor so they pass on any Git.
CI sets `METABROWSER_REQUIRE_ADMITTED_GIT`, which turns a below-floor skip into a
failure; `tests/admitted_git.py` is that gate.
The list is kept by hand, so a test that asks for the floor from a module the list
leaves out fails, wherever the helper it asked through lives.

**macOS** covers what only that platform has: extended ACLs on the application home
(`tests/test_cache_permissions.py`), ref names that fold together on a case-insensitive
file system (`tests/test_cache_update.py`, `tests/test_github_pulls.py`), and Apple’s
`/usr/bin/git`, a shim whose hand-over to the developer tools’ Git a stop has to follow
(`tests/test_git_process_group.py`). CI runs on Ubuntu, so no CI job runs these tests.
`make test-macos` sets `METABROWSER_REQUIRE_MACOS_TIER`, which turns a skip of one of
them into a failure, so the target cannot pass on Linux or on a case-sensitive volume.

**Live GitHub** covers what a fixture cannot: an anonymous HTTPS clone of a public
repository, and `gh` reads of public pull requests.
It is read-only and writes nothing to GitHub.
It needs the network, an admitted Git, and a `gh` signed in to github.com.
With the tier selected, a live test that skips for any of those fails; it may skip only
for what github.com holds that day.
Every other test runs with a failing stand-in `gh` first on `PATH`.

### Serial and Chrome Tests

Within the default tier, two markers say what a test needs from the machine it runs on,
and `tests/suite_tiers.py` holds what each means:

- `chrome`: the test drives headless Chrome.
  Every test that uses the `chrome_profile` fixture, directly or through another
  fixture, gets it, and nothing else sets it.
- `serial`: the test measures wall-clock time and needs the machine to itself.
  A module sets it by hand, as `pytest.mark.serial(reason=...)` with the measurement
  that forced it as the reason, the way a module raises its timeout.
  `tests/test_process_group.py` is one; its one Chrome test is `chrome` as well.

The three `-m` expressions in `TIERS` there, the parallel, serial, and Chrome tiers,
cover each combination of the two markers once, so they partition the suite whatever is
marked. `--shard=I/N` keeps the Ith of N disjoint parts of what a selection leaves, so
that one tier can be split across machines.
The parts are dealt by the seconds CI measured for each test, heaviest first, each to
the part with the least so far, so they take about the same time
(`devtools/shard_weights.py`). `--shard-by=file` deals whole files instead, by each
file’s measured seconds, so that a module runs in one part, its tests in order;
`make test-parallel` passes it, since its files run that way on their workers
(`tests/suite_tiers.py`). A tier or a shard that selects no test passes, with a line
that says so; a `-m` that is not one of `TIERS`, or a run that collected nothing, still
fails when nothing is left.

`make test` runs the default tier as four targets, in this order, and each also runs
alone, as a CI job can call it:

| Target | Runs | How |
| --- | --- | --- |
| `make test-parallel` | every test in neither marker’s tier | under pytest-xdist, `PYTEST_WORKERS` workers, each test file on one worker, its tests in order |
| `make test-serial` | the tests marked `serial` and not `chrome` | one at a time, after the parallel tier, so never beside its workers |
| `make test-chrome` | the tests marked `chrome` | one at a time, after the serial tier |
| `make test-goldens` | `tests/golden/*.tryscript.md` | `devtools/run_goldens.py`, `GOLDEN_JOBS` files at a time |

A run that selects a `chrome` test starts Chrome once per pytest process (each xdist
worker) and closes it before the first test, under a bound of its own, because a CI
runner’s first Chrome start is cold and a start cut off before it finishes leaves the
next one cold too. It writes how the warm-up went to the terminal at once.
`tests/chrome_starts.py` has the measurements and the bound, `WARM_UP_BOUND_S`. Each
test’s start then has `START_BOUND_MS` (`tests/dom/chrome-session.mjs`); a start that
fails is logged with the end of Chrome’s stderr, and one whose Chrome exited is made
again, up to `START_ATTEMPTS` tries.
The run’s terminal summary prints a `chrome starts:` line for every start made through
`tests/dom/chrome-session.mjs`: how many, the slowest, and each that failed, so a run
that a second start kept green still shows it.

`PYTEST_WORKERS` defaults to one worker per logical processor, and a shared or loaded
machine lowers it: `make test PYTEST_WORKERS=2`. `make test-chrome SHARD=2/4` runs the
second of four parts of a tier, and `SHARD` works with each pytest target.
`make test-admitted-git` runs its list under pytest-xdist too.
The `Makefile` documents each variable beside its default.

`tests/suite_gates.py` holds each marker to its meaning.
A test fails when:

- it asks for Chrome through `require_chrome` and is not `chrome`;
- it is marked `chrome` and does not use `chrome_profile`;
- it is marked `serial` without a reason;
- it is `serial` or `chrome` in a module that `ADMITTED_GIT_TESTS` lists.
  `make test-admitted-git` runs that list with no marker filter, so a module there that
  fails beside other tests is fixed, not marked.

The markers are two because the properties are: a test that needs the machine to itself
says nothing by that about the interpreters it has to pass on.

### CI Jobs

`.github/workflows/ci.yml` runs the default tier’s four targets as separate jobs side by
side, so a run takes as long as its slowest job rather than their sum.
[Plan for Fast CI](project/specs/active/plan-2026-11-16-fast-ci.md) is the design and
says why each check runs where it does.

| Job | Runs | On |
| --- | --- | --- |
| `plan` | `devtools/ci_plan.sh`: reads `main`’s state, and decides the run’s path, each tier’s interpreters and parts, whether the Chrome tier runs, the admitted Gits, and whether `stack-integration` has anything to check | every run; its summary says what it decided and from what |
| `unit` | `make test-parallel`, in parts by `SHARD` | the plan’s interpreters and parts |
| `goldens and serial` | `make test-goldens`, then `make test-serial`, each in parts by `SHARD` | the same |
| `chrome` | `make test-chrome`, in parts by `SHARD`; on the pull-request path, nothing when the change touches no browser path | the same |
| `admitted-git` | `make test-admitted-git`, in parts by `SHARD` | the plan’s Git releases: all three on the main path, the lowest on the pull-request path |
| `stack-integration` | `make lint-check` and the four tiers, on the head merged with `main` | a stacked pull request whose tested commit lacks `main`’s head and whose merge with `main` changes the tree: in practice an informal chain, since a formal GitHub stack’s merge commit already holds `main` |
| `ci-ok` | `devtools/ci_verdict.sh`: fails unless every other job succeeded, and says why it accepted a skipped `stack-integration` | every run |

**The two paths.** A push to `main`, and a pull request while `main` is red, take the
*main path*: every tier whole, on each supported Python and the free-threaded build, and
`admitted-git` on all three releases.
A pull request while `main` is green takes the *pull-request path*, which the owner
asked on 2026-11-22 to finish in about three minutes:

- one interpreter, `PR_CHROME_PYTHON`, for every tier, in more and shorter parts;
- the whole Chrome tier, slow tests included, when the change touches a path a Chrome
  test can observe, and no Chrome job at all when it touches none.
  Until 2026-11-25 a pull request left out the slowest Chrome tests, and three pull
  requests in one week merged green and broke one of them on `main`, which blocked every
  merge until it was fixed.
  No narrower choice was safe: one of the three changed a key in the shell’s scripts and
  broke a test of another view that pressed it.
  `BROWSER_PATHS` in `devtools/ci_plan.sh` is the list, each entry with its reason, and
  the `plan` job’s summary names the paths that decided it.
  A change to the backend alone can still break a Chrome test, since each drives a real
  server: the push to `main` that follows runs the whole tier and is where that shows;
- `admitted-git` on the lowest admitted release, which is the security floor.

Every Chrome test also runs on every push to `main`, in the nightly soak, and in
`make test` and `make verify`. `devtools/ci_plan.sh` holds the parts each path deals a
tier into, with the measurements that set them, and `tests/test_ci_plan.py` holds that
the main path narrows nothing.

`ci-ok` is the one check to require.
It accepts a skipped `chrome` only when the `plan` job decided `chrome=none`, and says
so. While `main` is red it also writes a `main-red` verdict line, which
[Git](../AGENTS.md#git) merges by, read from the `ci-ok` job’s own log.
The `plan` job reads `main`’s state for a pull request to `main` and for any pull
request whose tested commit contains `main`’s head, a formal stack’s layers among them.
A newer push to a pull request cancels its running jobs, and a push to `main` is never
cancelled. No leg cancels its siblings, so “Re-run failed jobs” reruns only the one that
failed, and the legs that passed stay as evidence.

**Time limits and shards.** Each job’s `timeout-minutes` is about 1.5 times its measured
90th percentile, with the measurement in a comment beside it.
A limit that trips means a tier grew by half: split its job further, or make its slowest
tests cheaper. The limit covers the job’s setup too, so each setup download that has
stalled is bounded: `devtools/install_uv.sh` and `devtools/install_node.sh` fetch the
pinned uv and Node with retries that end a stalled transfer, and put them where their
setup actions look first, and `SEGMENT_DOWNLOAD_TIMEOUT_MINS` in a workflow’s `env`
gives a cache restore a deadline, after which the job goes on as on a miss.
A job that nears its limit while its sibling parts do not is uneven, not grown: the
parts are dealt by the measured seconds in `devtools/shard_weights.json`, and
`make shard-weights` rewrites that file from the newest green run of `main` as `gh`
reads its job logs. Run it when `make ci-report CI_REPORT_FLAGS=--check` names a sharded
job, and after a change that moves a tier’s time between tests, such as a new slow test;
commit the result, whose diff is the units whose time changed.
A test, file, or golden the file does not list is dealt as a typical one, so nothing has
to be refreshed for a new test to run.
`devtools/refresh_shard_weights.py` says what it reads and how it combines interpreters.

To add a shard, raise the tier’s count for its path in `devtools/ci_plan.sh`, and on the
main path deal the matching `stack-integration` parts the same way.
A job’s limit is set by its longer path, the main one.
`devtools/check_ci.py`, part of `make lint-check`, fails an edit that drops a check and
still goes green: a tier whose interpreters or parts are not the `plan` job’s, a fixed
`SHARD`, a Chrome job with another target or condition, a matrix `include` or `exclude`,
a tier or required job no step runs, a step or job skipped or allowed to fail, a `make`
option or variable on a tier, a `ci-ok` step other than `devtools/ci_verdict.sh` on
every job’s result, an interpreter list that differs from `pyproject.toml`’s classifiers
and the free-threaded build, and a lost trigger.
It also fails a permission, trigger, or expression that widens what a pull request can
reach. Its docstring lists every rule.

**The nightly soak.** `.github/workflows/nightly.yml` repeats the serial and Chrome
tiers on the interpreter a pull request draws the Chrome tier on, so that a flake is
found away from a pull request, then runs `make ci-report` with `--check`
([Measuring CI](#measuring-ci)). It finds flakes; the runs on each commit of `main` are
the coverage.

### Skips

`make test` runs pytest with `-rs`, which prints each skipped test with its reason, and
with `--durations` and `--file-durations`, which list the slowest tests and every test
file; the serial and Chrome tiers list every test, since `make shard-weights` reads
them.
In CI it also sets `METABROWSER_STRICT_SKIPS`, and a skip has to belong to an outer
tier or the test fails:

- macOS tier: a test with the `macos_tier` marker.
  Its reasons are `extended ACLs are inspected only on macOS`,
  `the file system is case-sensitive`, `the store's filesystem tells letter case apart`,
  `Apple's git shim is macOS's, and needs Xcode or its Command Line Tools`, and
  `Linux answers a zombie like a live process`;
- Live GitHub tier: a test with the `live_github` marker, with
  `set METABROWSER_LIVE_GITHUB=1 to run`;
- Admitted-Git tier: `needs a Git the acquisition floor admits`, where the runner’s own
  Git is below the floor.
  The admitted-git job runs those tests.
- File ages: `needs a Git that reads file ages`, where the installed Git is below
  `FILE_AGES_GIT_MINIMUM`. The admitted-git job that builds a release at or above it
  fails instead of skipping (`tests/file_ages_git.py`).

Any other reason in a CI run means a test the suite is believed to run did not, so it
fails there. `tests/suite_gates.py` holds these rules.

`make golden-update` sets `METABROWSER_STRICT_SKIPS=all`, the same switch at the level
where no skip stands, tier or not: a recorder or driver that skipped regenerated
nothing.

When the live tier is selected, two of its tests may still skip for the data on
github.com that day: `has no branch with a slash today` and
`has no open pull request today`.

Strict mode is off on a developer machine, which can add these:

- `needs a Git the acquisition floor admits`, where the installed Git is below the
  floor;
- `reftable repositories need Git 2.45 or later`, for the reftable cases of
  `tests/test_git_route_memo.py`, where the installed Git is older; the default CI job’s
  Git is newer, so CI runs them and strict mode fails them if they skip, and the
  admitted-git job does not select that module;
- `the macOS filesystem rejects undecodable byte names`, on a Mac; CI runs that test;
- `root is never denied by modes`, when the suite runs as root, for the tests that stage
  a refusal by a file’s mode (`tests/mode_denials.py`);
- `this machine has no IPv6 loopback`, where `::1` cannot be bound, for the tests that
  serve on an IPv6 host (`tests/ipv6_loopback.py`); CI’s runners have one and run them;
- `symlinks are unavailable`, where the platform or the account cannot create one;
- a POSIX-only reason, on a platform without POSIX modes, locks, signals, or FIFOs, and
  `could not import 'fcntl'` for the lock and atomic-write modules there;
- `is not on PATH, and METABROWSER_ALLOW_MISSING_TOOLS allows that`, after the opt-out
  above;
- `bind mounts are a Linux mount namespace's`, off Linux, and
  `no private mount namespace could be made`, on Linux, for
  `test_a_read_only_bind_mount_over_a_held_directory_is_honored` in
  `tests/test_cache_permissions.py`, which bind-mounts a directory read-only in a mount
  namespace of its own.
  It runs there as root of an unprivileged user namespace where the kernel lets one
  mount. Otherwise it runs as host root through `sudo -n unshare --mount`, and that runs
  this project’s interpreter, its startup hooks, and everything it imports as root: a
  private mount namespace confines mounts, not root.
  So it takes that route only on a machine thrown away after the run: a GitHub-hosted
  runner, which GitHub marks with `GITHUB_ACTIONS=true` and
  `RUNNER_ENVIRONMENT=github-hosted`, or one whose owner sets
  `METABROWSER_TEST_PRIVILEGED_MOUNT=1`. `sudo -n` never asks for a password.
  CI’s Ubuntu runners cannot mount from an unprivileged user namespace, so CI runs it as
  root, and a self-hosted runner without the variable fails it under strict mode;
- `Chrome is not installed`, for the checks that need a real headless Chrome: the
  transition recorder’s in `tests/test_transitions_instrument.py`, which measure paint
  and the frame clock; `tests/test_folder_overview_alignment.py`, which measures where
  the Folder Overview’s labels start at several window widths; the layout checks in
  `tests/test_git_commit_summary_chrome.py`, `tests/test_github_pull_header_chrome.py`,
  `tests/test_github_pull_text_chrome.py`, `tests/test_github_pulls_stacks_chrome.py`,
  `tests/test_nav_metadata_chrome.py`, `tests/test_page_header_chrome.py`, and
  `tests/test_staged_fonts_chrome.py`; `tests/test_files_totals_stable_chrome.py`, which
  records every frame of the Files navigation from the document’s start to settled and
  holds that nothing in it moves; `tests/test_github_pull_timeline_chrome.py`, which
  reads a pull request’s Conversation timeline’s type, spacing, and line from the boxes
  Chrome lays out and the pixels it paints; `tests/test_prose_faces_chrome.py`, which
  reads the face documents and chrome prose are drawn in under each reading font and
  font set; `tests/test_raw_profile_cache_chrome.py`, which follows a `/raw` answer
  Chrome kept under the trusted profile after the folder is served `--untrusted`;
  `tests/test_inert_render_refusal_chrome.py`, which reads the notice and the source an
  untrusted document past its render deadline shows in its Document tab and in the
  folder Overview’s README panel; `tests/test_overview_readme_toc_chrome.py`, which
  measures a folder Overview’s README table of contents against the same README opened
  as a file; `tests/test_document_print_chrome.py`, which measures a document’s print
  button in its card’s corner, that nothing moves when it arrives, the table of contents
  toggle and rail beside it, a click and Command-P, and print output;
  `tests/test_diff_markdown_fold_chrome.py`, which measures a rendered Markdown diff’s
  fold of unchanged blocks closed, open, and under the pointer, and its quote and code
  against a document’s in the light and the dark theme;
  `tests/test_diff_markdown_spacing_chrome.py`, which measures the space between a
  rendered Markdown diff’s blocks against the Document view of the same text, in the
  serif and the sans reading font; `tests/test_checkout_ref_selector_chrome.py`, which
  serves a checkout with `metab` and switches it between its working tree and its
  branches and tags from the page, reading each document’s policy and the selector’s
  panel, and then compares every file under the checkout with what it was;
  `tests/test_ref_selector_long_list_chrome.py`, which serves a checkout of thousands of
  branches and reads which of the branch chooser’s rows are drawn, and where, when it
  opens, scrolls, takes End and Home, has the Files toolbar drawn again around it, and
  is filtered; `tests/test_ref_selector_pulls_chrome.py`, which serves a checkout whose
  branches are the heads of cached pull requests and reads the two heights of the
  chooser’s rows, that each sits where the rows before it put it, a pull request’s icon,
  number, and title, and what its filter finds; `tests/test_control_chords_chrome.py`,
  which presses Control-N and Control-P through Chrome’s input under a navigator
  overridden to name a Mac and then Linux, on every host, and reads that only the Mac’s
  binds them; `tests/test_overview_label_column_chrome.py`, which serves a folder of
  eleven file-type families and reads, at five window widths in both font sets, where
  every File Overview row’s label column ends and its bar starts, with Details closed
  and open and Files and Bytes, whether the labels the column is sized for fit it, what
  a longer label does to the bars, and how the legend’s ten entries wrap;
  `tests/test_overview_legend_hover_chrome.py`, which moves Chrome’s pointer onto a File
  Overview legend entry and a bar segment and reads which bars and entry are marked,
  what they compute to, where the tooltip lands, and that nothing moves;
  `tests/test_treemap_legend_hover_chrome.py`, which moves Chrome’s pointer onto the
  Treemap’s legend entry and one of its cells and reads which cells, bars, and entry are
  marked, what they compute to, and that the view does not move;
  `tests/test_treemap_containment_chrome.py`, which serves a wide, deep folder and reads
  that every cell the Treemap draws lies inside its parent folder’s cell and the map’s
  border, at a wide and a narrow window;
  `tests/test_github_pull_core_markdown_chrome.py`, which reads every frame of a pull
  request’s description as it opens on its prepared core and as its record follows, and
  holds that its Markdown source is never on screen; and
  `tests/test_title_prefix_chrome.py`, which reads a title prefix’s and the rest’s
  computed weight, face, size, and ink on every title surface.
  Any other check that calls `require_chrome` in `tests/required_tools.py` skips for the
  same reason. The CI runners have Chrome, so CI runs them.
  Each runs its Node script in a process group of its own and stops that whole group,
  Chrome included, however the run ends, with the group’s leader kept unreaped until
  then so the group ID cannot pass to another process.
  Chrome keeps every process it starts for a session in that group, which
  `tests/test_process_group.py` measures for both ways the tests launch it, so stopping
  the group is the whole mechanism: nothing outside it is signalled.
  Afterwards a process still naming the profile is reported, failing the test, and left
  running; the profile is removed even if that look failed.
  Each test’s bounds, stops, and teardown together fit under its timeout.
  `tests/process_group.py` does this, and `tests/test_process_group.py` holds it.

### Timeouts

A test’s budget is `timeout` in `pyproject.toml`’s pytest options.
When it fires it ends the whole run, not one test, so a bound inside a test must be
shorter to do any good: a child process’s `timeout`, or a polling deadline, is at most
`MAX_INNER_BOUND_S` in `tests/test_suite_gates.py`. A test that needs longer carries its
own `pytest.mark.timeout` with the measurement that forced it written beside it.
A test in `tests/test_suite_gates.py` fails on a longer bound in a module that has not
raised its budget.

### Held Steps

A stub held until the test opens a `threading.Event` or `threading.Semaphore` waits on
its event loop with `held_until` from `tests/loop_gate.py`, never in a worker thread.
So does a test’s own coroutine that waits for a signal from work in the pool.
A wait handed to `asyncio.to_thread` keeps a pool thread for the whole hold, and the
server’s next step can queue behind it until the bound; `tests/loop_gate.py` says how.
A test in `tests/test_suite_gates.py` fails on a gate’s `wait` or `acquire` passed to
`asyncio.to_thread` or `run_in_executor`.

## Measuring the Suite

A change to the tests is reviewed on numbers taken the same way before and after it.
`devtools/suite_report.py` prints them, so nobody counts by hand and the next person
gets the figures the last one did:

```shell
# The working tree: files, lines, and test functions by area, then the totals.
make test-report

# Commits side by side, with the change from the first to the last.
# `.` is the working tree.
make test-report REFS="origin/main ."

# What one run cost: the time of each test file and each golden, and what it skipped.
gh run view <run> --job <job> --log > run.log
make test-report LOG=run.log
```

- An **area** is the first word of a test module’s name: `tests/test_cache_update.py` is
  in `cache`.

- **Lines** are counted from the files of the tree or commit alone, so they are the same
  on every machine. An image is a file with no lines.

- **Test functions** are the ones pytest collects, read from each module’s syntax tree:
  `test_` functions at module level and `test_` methods of a `Test` class.
  A parametrized function is one function, so this is lower than the number of cases a
  run reports.

- **Time** is read from a CI job log, or a run’s own output, and belongs to that one
  run, so quote the run and the job with it.
  Every pytest session and golden run in the job is read.
  - A test file’s time is the one the run listed under `--file-durations`
    (`tests/suite_timing.py`): the sum of its tests’ setup, call, and teardown, which a
    run under pytest-xdist needs, since its progress lines name no file.
    The section lists the slowest files and counts every one, so the report gives the
    count and the total beside the files it names.
  - A golden’s time is the one on its `golden:` line from `devtools/run_goldens.py`.
  - A log from before those lines existed is read by its timestamps instead: a file’s
    time is the gap between consecutive progress lines, and a golden’s the gap before
    tryscript printed its verdict.

  A developer machine under load gives other times; compare a CI job with itself.

- **Skips** are the cases `-rs` listed in the log, counted by reason.
  [Skips](#skips) says which reason belongs to which tier.

`uv --config-file uv.toml run --frozen python -m devtools.check_goldens --report` gives
the size distribution of the goldens and recordings against their review budget.

### Measuring CI

`make ci-report` takes the same kind of numbers for CI itself, from the run data `gh`
reads: each job’s median and 90th percentile, the push to green of each kind of run, and
the runs that needed another attempt.
`devtools/ci_report.py` says how each is taken.

```shell
# The newest runs of ci.yml.
make ci-report

# More runs, on main only, with each job's steps, keeping the data it read.
make ci-report CI_REPORT_FLAGS="--runs 300 --branch main --steps --save attic/ci-runs"

# The kept data again, without the network.
make ci-report CI_REPORT_FLAGS="--from attic/ci-runs"
```

With `--check` it fails when a job’s 90th percentile passes `CHECK_FRACTION` of the
`timeout-minutes` the workflow gives that job, before the limit itself trips.
`--containing` keeps only the runs whose head contains a commit, and the nightly soak
runs `--check` over `main`’s push runs since `ci.yml` last changed, since an older run
may have done other work under a job’s name.
Quote the runs a number came from, as for a suite run.

## Adding Coverage

Choose the narrowest layer that proves the behavior:

- pure transforms and classifiers: unit test;
- response shape, ETag, path validation, or middleware: route test;
- background tasks and live changes: lifespan test;
- SDK registration or renderer lifecycle: Node contract test;
- deterministic browser-owned state or composition: browserless production-module
  session with a golden transcript;
- package-data or import-boundary behavior: distribution test;
- a new `/api/` route, or the envelope a view draws from: golden transcript.

The last two are not preferences.
`devtools/check_parity.py` fails the build when a registered route has no transcript or
a listed functional aspect lacks the command-line evidence it claims.
A data aspect must run through `metab`; an interaction aspect must name an executable
browserless session; only paint or platform behavior may carry a specific browser-only
exemption. See [CLI and functional UI parity](../AGENTS.md#cli-and-functional-ui-parity)
for the rule and the [parity registry](project/architecture/arch-parity-registry.md) for
the tables it checks.

For regressions, make the test fail for the original defect before applying the fix.
Assert behavior and public contracts instead of copying implementation structure into
the test.

## Plugin Test Matrix

A plugin should cover:

1. manifest parsing and classifier matches, including near misses;
2. registry diagnostics through `metab --doctor`;
3. default-view mount and lazy-view mount;
4. data-hook success, validation errors, and unsafe paths;
5. disposal of requests, streams, listeners, timers, and charts;
6. wheel contents in a clean installation;
7. graceful fallback when the plugin is not installed.

Keep consumer plugin fixtures in the consumer repository.
The Metabrowser suite should use generic sample plugins so it cannot pass only because
an unrelated workspace package happens to be installed.

## Manual Browser Checks

Do not make a manual check the only coverage for a deterministic contract.
What only a person in a real browser can judge before a release, from the reading layout
to Quick Search and the Pulls tab, is the checklist in
[Manual Browser Checks](project/qa/qa-2026-11-14-manual-browser-checks.md).
Pull-request and Git navigation timing is reviewed with the performance loop’s
[navigation playbook](../explorations/performance-loop/README.md#reviewing-pull-request-and-git-navigation).

### Headless Screenshots

There is no automated visual-regression layer.
When a change is presentational and a reviewer needs to see it, drive a real browser.

Chrome’s `--headless --screenshot --virtual-time-budget` mode does not work against the
shell: the page holds the `/api/events` stream open, so virtual time never drains and
Chrome hangs without writing a file.
Two approaches work instead:

- **Drive the live application over the DevTools protocol.** Start Chrome with
  `--headless=new --remote-debugging-port=<port>` and a scratch `--user-data-dir`, read
  the page target from `http://127.0.0.1:<port>/json/list`, then send
  `Emulation.setDeviceMetricsOverride`, `Page.enable`, `Page.navigate`, and
  `Page.captureScreenshot` over the target’s WebSocket.
  Node’s global `WebSocket` means the driver needs no dependency.
- **Skip the shell for a question only about document CSS.** Request
  `/api/kpress/render` for the file and view, then write a standalone page that inlines
  the returned `html` with the stylesheet entries of the returned asset manifest and
  `/static/styles.css`. It holds no event stream, so the ordinary
  `--virtual-time-budget` screenshot works, at several widths and disclosure states in
  one pass.

Keep these harnesses in the worktree’s gitignored `attic/`; they are debugging aids, not
fixtures. The same driver answers rendering-cost questions no contract test can, and
[Rendering Large Content](large-content-rendering.md) holds the procedure for measuring
the shape of a cost before setting a bound.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
