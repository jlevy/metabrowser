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
over authored same-document TOC anchors before passing them to the installed KPress TOC
through the production observation fallback.
The transcript records the delegated target and active section through a long document,
including frame coalescing and lifecycle disposal.

### Golden CLI Transcripts

`tests/golden/*.tryscript.md` are markdown files holding shell commands and their exact
expected output. [tryscript](https://github.com/jlevy/tryscript) runs each command in a
fresh sandbox and diffs the result, so a transcript is both a test and a readable record
of what the command does.

This is the layer that proves **routes**, because `metab --api <route>` issues a real
request through the real application — the same middleware, routing, and serialization
the browser reaches.
`--walk` and `--diff` call their libraries directly, so they prove the model and not the
wire; a route could accept a parameter the library never sees and those transcripts
would stay green.

Fixtures pin everything they can so transcripts assert real values rather than
wildcards: mtimes with `touch -t`, and Git identity and dates so commit revisions are
byte-identical on every machine.
Only what no fixture can pin is normalized, and `metabrowser/normalize.py` is the single
table saying what and why.

Regenerate with `make golden-update` **only to record an intended change**, then read
the diff line by line before committing it.
A regenerated transcript nobody read turns a regression into a committed expectation.

### One Harness and One Update Command

`tests/golden_harness.py` is the one place an expectation is compared or rewritten, and
the only reader of `GOLDEN_UPDATE`. It serves the two kinds of expectation pytest owns:

- **In-process transcripts**, `tests/golden/*.txt`, for commands a subprocess cannot
  run: serve mode, and acquisition, which a Git below the acquisition floor refuses.
  A driver runs `metab` through the console script’s entry point and renders each
  command’s line, exit status, and both streams in full.
  One exception keeps a transcript readable: where a command repeats a long run of an
  earlier command’s output, a driver may print the run once and name it where it
  repeats, as `cli-git-pin-tree.txt` does for the tallies every `/api/tree` answer
  carries. The run is found by comparing the two outputs, so output that stopped
  repeating prints in full again.
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
  `python -m devtools.check_goldens --report` prints the current distribution.

### What a Transcript May Replace

A value is replaced only when no fixture can pin it, and by a pattern as narrow as the
value: a time is `[TIMESTAMP]` and a counter `[COUNT]`, not `[..]`. In-process
transcripts fix the clock and build every origin with pinned identities and dates, so
times and commit IDs are literal; the placeholders that remain, each with the reason no
fixture can pin it, are listed at the top of `tests/golden_harness.py`. For tryscript,
`devtools/golden_fixup.py` is that list.

A transcript must not depend on how busy the machine is.
The server logs a request slower than two seconds to stderr, which a transcript
captures, so the Make targets run tryscript with `METABROWSER_SLOW_SERVER_MS` set past
tryscript’s own command timeout.
Run tryscript through `make test` or `make golden-update`, or set that variable, when
the machine is loaded.

### Distribution Tests

`make build` inspects the wheel for required static assets and rejects repository-only
files. It then creates an isolated uv environment from the wheel and imports the package
and CLI. This catches missing package data and source-checkout assumptions.

## Running Tests

```shell
# Complete Python suite.
uv --config-file uv.toml run --frozen pytest

# One module or test.
uv --config-file uv.toml run --frozen pytest tests/test_plugin_loader.py
uv --config-file uv.toml run --frozen pytest tests/test_plugin_loader.py::test_classifier_priority_wins

# Full release gate.
make verify
```

Node and Git are prerequisites.
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

The variable takes `node`, `git`, or both separated by a comma.
`tests/required_tools.py` is the gate, and a test asks it rather than looking the tool
up itself; a test in `tests/test_suite_gates.py` fails when one does.

## Test Tiers

`make test` is the default tier.
Three outer tiers hold evidence that the default tier cannot produce on every machine.
Each has one command, one way its tests are selected, and a stated time when it runs.

| Tier | Command | Selected by | When it runs |
| --- | --- | --- | --- |
| Default | `make test` | everything that does not skip | Every pull request in CI, on each supported Python version on Ubuntu; the pre-push hook |
| Admitted Git | `make test-admitted-git` | `ADMITTED_GIT_TESTS` in the `Makefile` | Every pull request in CI, on the lowest admitted Git release and the newest patched one |
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
(`tests/test_cache_permissions.py`) and ref names that fold together on a
case-insensitive file system (`tests/test_cache_update.py`,
`tests/test_github_pulls.py`). CI runs on Ubuntu, so no CI job runs these tests.
`make test-macos` sets `METABROWSER_REQUIRE_MACOS_TIER`, which turns a skip of one of
them into a failure, so the target cannot pass on Linux or on a case-sensitive volume.

**Live GitHub** covers what a fixture cannot: an anonymous HTTPS clone of a public
repository, and `gh` reads of public pull requests.
It is read-only and writes nothing to GitHub.
It needs the network, an admitted Git, and a `gh` signed in to github.com.
With the tier selected, a live test that skips for any of those fails; it may skip only
for what github.com holds that day.
Every other test runs with a failing stand-in `gh` first on `PATH`.

### Skips

`make test` runs pytest with `-rs`, which prints each skipped test with its reason.
In CI it also sets `METABROWSER_STRICT_SKIPS`, and a skip has to belong to an outer tier
or the test fails:

- macOS tier: a test with the `macos_tier` marker.
  Its reasons are `extended ACLs are inspected only on macOS`,
  `the file system is case-sensitive`, and
  `the store's filesystem tells letter case apart`;
- Live GitHub tier: a test with the `live_github` marker, with
  `set METABROWSER_LIVE_GITHUB=1 to run`;
- Admitted-Git tier: `needs a Git the acquisition floor admits`, where the runner’s own
  Git is below the floor.
  The admitted-git job runs those tests.

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
- `the macOS filesystem rejects undecodable byte names`, on a Mac; CI runs that test;
- `root is never denied by modes`, when the suite runs as root;
- `symlinks are unavailable`, where the platform or the account cannot create one;
- a POSIX-only reason, on a platform without POSIX modes, locks, signals, or FIFOs, and
  `could not import 'fcntl'` for the lock and atomic-write modules there;
- `is not on PATH, and METABROWSER_ALLOW_MISSING_TOOLS allows that`, after the opt-out
  above.

### Timeouts

A test has 60 seconds, set in `pyproject.toml`. When that timeout fires it ends the
whole run, not one test, so a bound inside a test must be shorter to do any good: a
child process’s `timeout`, or a polling deadline, is at most 50 seconds.
A test that needs longer carries its own `pytest.mark.timeout` with the measurement that
forced it written beside it.
A test in `tests/test_suite_gates.py` fails on a longer bound in a module that has not
raised its budget.

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
for the rule and
[Views, Models, and Routes](project/architecture/arch-views-models-routes.md) for the
table it checks.

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

The [v0.12 alpha test plan](project/specs/active/plan-2026-09-22-v012-alpha-testing.md)
sequences foundation testing, GitHub URL browsing, and direct PRs, with manual and
automated scenarios and the landing checklist.
The step-by-step procedure is
[QA: v0.12 Repository Library](qa-v012-repository-library.md).

## Manual Browser Check

Before a release, serve the public-safe manual corpus and check the real browser:

```shell
uv --config-file uv.toml run --frozen metab ./tests/manual-fixtures --no-open
```

The corpus contains Markdown with frontmatter, structured JSON, JSONL events, source
code, an SVG image, and an opaque file large enough to exercise the binary view.
Keep these fixtures generic and free of copied production data.

Open the printed URL and verify:

- first paint appears before a large tree finishes indexing;
- Markdown, structured data, source, JSONL, image, and binary views render;
- the binary Bytes view loads a second chunk on **Load more**, appends without
  re-rendering the bytes already shown, and wraps without horizontal overflow at narrow
  and wide panes in both themes;
- a binary file above the preview ceiling reports the cutoff instead of loading;
- changing and deleting files updates tree and recent views;
- a direct hash path opens independently of the tree crawl;
- when the served root is in a Git repository, opening a commit that changes the root
  renders its changed-file diff in a fresh browser session;
- light and dark themes, narrow panes, keyboard focus, and print output remain usable;
- the console and Network panel contain no unexpected errors or missing assets.

Do not make the manual check the only coverage for a deterministic contract.

### Headless Screenshots

There is no automated visual-regression layer.
When a change is presentational and a reviewer needs to see it, drive a real browser
manually.

Chrome’s `--headless --screenshot --virtual-time-budget` mode does not work against the
shell: the page holds the `/api/events` stream open, so virtual time never drains and
Chrome hangs without writing a file.
Two approaches work instead.

Drive the live application over the DevTools protocol.
Start Chrome with `--headless=new --remote-debugging-port=<port>` and a scratch
`--user-data-dir`, read the page target from `http://127.0.0.1:<port>/json/list`, then
send `Emulation.setDeviceMetricsOverride`, `Page.enable`, `Page.navigate`, and
`Page.captureScreenshot` over the target’s WebSocket.
Node 24 provides a `WebSocket` global, so the driver needs no dependency.

For a question that is only about document CSS, skip the shell.
Request `/api/kpress/render` for the file and view, then write a standalone page that
inlines the returned `html` alongside the stylesheet entries in the returned asset
manifest and `/static/styles.css`. Such a page holds no event stream, so the ordinary
`--virtual-time-budget` screenshot works, and it can be rendered at several widths and
disclosure states in one pass.
Keep these harnesses in a scratch directory; they are debugging aids, not fixtures.

The same driver answers rendering-cost questions that no contract test can.
Comparing DOM strategies for the binary Bytes view this way showed that CSS-wrapping one
large run is quadratic — 43 ms at 32 KiB rising to 33 s at 1 MiB — while pre-broken
lines in `content-visibility` blocks render the same 1 MiB in about 50 ms.
When a limit looks arbitrary, measure before changing it, and record what was measured
next to the constant.
[Rendering large content](large-content-rendering.md) holds the cost model and the
procedure for establishing the shape of a cost before setting a bound.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
