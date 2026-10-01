# Plan: v0.12 Alpha Testing and Stack Acceptance

**Status:** Active until the stack lands.
T0 through T2 were run on 2026-09-24 in the scope of the
[thin-mirror plan](plan-2026-09-23-v012-thin-mirror.md), and
[QA: v0.12 alpha acceptance](../../qa/qa-2026-09-24-v012-alpha-acceptance.md) records
the results. [Landing status](#landing-status) lists what remains.

## Outcome and Scope

An operator should be able to paste a GitHub repository, branch, file, or pull-request
URL, inspect the intended immutable content, and reopen previously acquired content
offline. A directly addressed PR must work without first populating a discovery index.
Tests must prove the installed application path as well as the individual contracts.

Implementation is one linear chain of open pull requests on
[stack 218](https://github.com/jlevy/metabrowser/stack/218). Keep the stack together
until it is stabilized; an intermediate testing milestone does not authorize merging a
lower layer. The landing coordinator is `mb-n2ro`.

The [thin-mirror plan](plan-2026-09-23-v012-thin-mirror.md) owns the v0.12 feature
design and the capabilities it defers.
The [repository plan](plan-2026-08-11-open-repo-from-git-url.md) and
[GitHub plan](plan-2026-08-27-github-provider-and-pull-requests.md) are background for
the foundation it kept.
This plan owns the testing milestones, the evidence requirements, and the landing
checklist. Reviews and run results belong on PRs, beads, and QA records, not in this
procedure. Tooling maintenance, including tbd releases or shortcut cleanup, is not a
prerequisite for these product milestones.

## Feature Coverage

The states below describe implementation, not merge approval.
**Built on stack** means the code is in the integration build; **retired** means the
thin-mirror plan replaced the design; **deferred** means the user moved the capability
out of v0.12 on 2026-09-23.

| Feature / owning phase | State | What works and what remains | First useful test |
| --- | --- | --- | --- |
| Local browsing and Git history/diffs | Released baseline | Filesystem Markdown, structured data, images, binary content, Git history/detail and diff infrastructure remain available | T0 browser regression |
| HTML trust foundation | Built on `main` | Sandboxed raw responses, same-origin API proof and `--untrusted` exist; every new acquired-content entry point must apply them | T0 regression; T1 acquired-content isolation |
| Repository design and hosted-review records / 0–0D | Removed from the stack (2026-09-30) | The identity, source binding, repository/PR/comment/review/thread/check records, schemas, validators, corpora, installed contract discovery, and coverage oracle are kept, unmaintained, on the `reference/v012-hosted-review` branch, tagged `reference/v012-hosted-review-2026-09-30`; pull-request data is the GitHub plugin’s JSON records | None on this stack |
| Private cache format / 1A | Built on stack | Owner-only POSIX home, `f01` records, locks, safe publication, the staging sweep, and cache-inspection routes exist; nothing deletes a published store; Windows storage fails closed pending ACL support | T0 cache and recovery tests |
| Mirror acquisition / 1B-a, thin-mirror steps 2 and 5 | Built on stack | `file://` and `https://` acquisition publishes a complete, read-only worktree-free store (a full clone), pins the commit the URL selects, and reuses the cache offline; a refresh is one `git fetch` under a fetch side lock | T0 real CLI; M02 and M05 |
| Source sessions and content readers / 1B-b | Built on stack | Attached filesystem and immutable Git subjects share capability-aware routes and bounded plugin content readers | T0 CLI/API and local browser regression |
| Immutable Git revisions and serving / 1B-c, steps 3 and 4 | Built on stack | Byte-safe paths, full-OID trees, batch readers, and a lock-free pin open serve `--show`, `--api`, `--check-api`, and the browser under the forced untrusted profile; a background refresh offers a newer revision, and the pin switches to a branch, tag, or commit; `--walk` refuses a Git source by design | T0 pin and content tests; M03 to M06 |
| GitHub URL reduction and selection / step 5 | Built on stack | Repository, tree, blob, commit, raw, and pull-request URLs reduce to a source, ref, path, and lines; a slash-containing ref splits against the mirror’s refs; any other shape is refused with a typed error | M02 |
| GitHub authentication / steps 5 and 6 | Built on stack | `gh` is Git’s credential helper for github.com and the API client, so Metabrowser reads no token | M10 |
| Pull-request data and page / steps 6 and 7 | Built on stack | One validated JSON record per pull request from `gh api`, `refs/pull/<n>/head`, merge-base Files changed, conversation, reviews, review comments, and checks, reopened offline | M07 to M11 |
| View file from a diff | Built on stack | Each file bar of a commit’s diff or Files changed opens the file at either side of the change | M03 and M08 |
| Untrusted Markdown, line anchors, and heading anchors | Built on stack | Inert Markdown and a Content-Security-Policy for untrusted sources, `#L` anchors and `?plain=1`, and `user-content-` heading ids | M06 and the record’s round-2 rows |
| Background object convergence / 2B | Retired | Stores are full clones, so no object is missing; the Simplify PR removed the prefetch and the convergence state | None |
| Selected-ref jobs, credential leases, provider binding, snapshots, and rebind / 2B and 3A | Retired | `git fetch`, the `gh` credential helper, and one record per pull request replace them | None |
| PR discovery and navigation / 3C and 4B; review anchors / 4C; SSH; checkout attachment | Deferred | Not part of v0.12 | M12 and M13 are not run |

The plans also retain these separate or later features:

| Feature | Scope and test boundary |
| --- | --- |
| Working-tree status and working-tree diffs | Separate attached-filesystem work; existing history/diffs do not complete the status panel, and status does not gate a worktree-free source |
| Full repository catalog and management | Later than the initial slice: coordinated refresh/repair/purge, size accounting and discarded-object compaction; basic inspection is already built |
| Repository chooser and session switching | Later catalog UI, recent/favorite/offline states and per-repository selection restoration; source-session primitives are already built |
| Very-large repositories | Later measured acquisition, shallow/progressive deepening and honest truncation/blame behavior |
| Issues and timelines | Later Phase 5 records, acquisition and views |
| Stacked PR browsing | Later Phase 6 derived relationships, adjacent comparisons and navigation; distinct from using a PR stack to deliver this work |
| Hosted releases and assets | Later sibling contracts, direct acquisition/views and discovery; asset bytes remain on demand |
| GitLab | Later adapter after the GitHub-first contracts and views |
| Automatic eviction | Deferred until measurements justify a policy |

SSH is deferred (`mb-bi2c`) and does not gate v0.12. Remote GitHub writes and cached
worktree materialization are non-goals.
Representing an LFS pointer or gitlink does not promise automatic LFS downloads or
submodule checkouts.

## Mechanical Mergeability and Product Readiness

Check the live stack for adjacent parents, inclusion of current `main`, clean merge
results, passing checks and ready-for-review PR state.
Resolve any actual branch rule or review requirement reported by GitHub.
Record that evidence on the integration PR.

Ready-for-review status and a clean merge do not complete the acceptance work in this
plan. Keep outstanding product findings in their beads and preserve the agreed
whole-stack landing decision independently of those GitHub flags.

## Delivery

Foundation stabilization is [#226](https://github.com/jlevy/metabrowser/pull/226), whose
reviewed green head is recorded in `mb-j439`. The work above it follows the thin-mirror
plan, whose [Delivery](plan-2026-09-23-v012-thin-mirror.md#delivery) section maps each
step and follow-up to its pull request.
Every pull request extends the tip of stack 218 and is reviewed and green before the
next one starts from its head.

The milestones and manual matrix below apply wherever the thin-mirror plan keeps the
capability; rows for a deferred capability say so.

## Testing Milestones

| Milestone | Entry condition | User-visible acceptance | Current availability |
| --- | --- | --- | --- |
| T0: local Git foundation | Current integration tip, supported Git, isolated application home | Acquire a `file://` origin, reopen its default full OID, inspect files/tree through `--show` and `--api`, and preserve local browsing | Passed: foundation acceptance in #226 and M01 in the acceptance run. Rerun it with the quick start below and the [foundation QA runbook](../../../qa-v012-repository-library.md) |
| T1: repository URL alpha | URL open and serving, ref and path selection, and trust integration (thin-mirror steps 3 to 5) | Open repository/tree/blob/commit/raw URLs; view content, history, and diffs; preserve slash-containing refs and path/line intent; reopen cached content offline | Passed in the acceptance run and its rerun, except M03’s base and head files, which wait for a rerun on View file |
| T2: direct PR alpha | T1 plus `gh` pull-request records and the pull-request page (steps 6 and 7) | Paste a PR URL; read its description, review/check state, changed files, and pinned comparison; reload and reopen offline | Passed in the acceptance run and its rerun, except M08’s base and head files (the same rerun) and M10’s private and revoked cases, which are blocked for lack of a private fixture |
| T3: discovery, navigation, and anchors | Deferred with the capabilities it tests | Bounded paginated PR navigation with honest counts/partiality, direct selection outside that index, and explicit outdated/unmappable anchors | Not part of v0.12 |

T2, in the thin-mirror scope, is the v0.12 landing milestone.
T3 and SSH acquisition are deferred, and neither gates landing.
A T0 build must be described as a foundation test build, not as GitHub URL or PR
support.

## Suggested Testing Walkthrough

1. **Select the integration build.** Follow the exact-head checkout procedure below,
   install the locked dependencies, and record the build and tool versions.
   Use an isolated application home for acquisition tests.
2. **Check the existing browser first.** Run
   `uv --config-file uv.toml run --frozen metab ./tests/manual-fixtures --no-open`, open
   the printed URL, and perform M01. Stop that server with Ctrl-C when finished.
   Separately browse the checkout as a filesystem root to inspect its existing Git
   history and diffs. This exercises the local browser, not URL acquisition.
3. **Exercise the new Git foundation.** Run the T0 quick start: cold acquire, warm
   reuse, nested file/tree inspection, then rename the origin and reopen cached content.
   Compare the full OID and file content at each step.
4. **Probe the foundation failures.** Continue through the foundation QA runbook for
   below-floor Git, read-only home, corruption/recovery and refusal behavior.
   The pin modes must report the same one-line errors as `--no-serve` (`mb-sumg`, fixed
   in #226); a traceback or a path in the message is a failure.
5. **Test real repository URLs.** Run M02–M06 through the installed CLI and a browser:
   URL intent, relative links, concurrent branches, offline restart and acquired-content
   trust. Ordinary public repository browsing does not need the GitHub API.
6. **Test one PR completely.** Run M07–M11 from a cold home, then warm/restart/offline.
   Inspect both sides of changed files, test private access when a private fixture
   exists, and interrupt a refresh.
   This completes T2, the landing milestone.

M10b, M12, and M13 test deferred capabilities and are not run for v0.12.

At each stage, run its automated scenarios before manual browsing, then capture the
actual browser results.
Repeat the relevant regressions when a later layer changes a shared path.

## Choose and Record the Integration Build

Use the current top PR from the live stack, including any testing or stabilization
layers added after the Git-pin layer.
Do not reset an existing development branch or test a stale local tracking ref.

```shell
# Set ALPHA_PR to the reviewed top PR number from stack 218.
: "${ALPHA_PR:?Set ALPHA_PR to the current integration PR number}"
ALPHA_HEAD="$(gh pr view "$ALPHA_PR" --repo jlevy/metabrowser --json headRefOid --jq .headRefOid)"
ALPHA_WORKSPACE="$(mktemp -d "${TMPDIR:-/tmp}/metab-alpha.XXXXXX")"
git fetch origin "$ALPHA_HEAD"
git worktree add --detach "$ALPHA_WORKSPACE/checkout" "$ALPHA_HEAD"
cd "$ALPHA_WORKSPACE/checkout"
git rev-parse HEAD
make install
uv --config-file uv.toml run --frozen metab --version
git --version
node --version
gh pr checks "$ALPHA_PR" --repo jlevy/metabrowser
```

Record the exact head, base, current `main`, OS, Git, Python, Node, browser, installed
version, and fixture identity with each run.
A development version derived from the last tag is not a v0.12 release; use its commit
identity to identify the build.
Refresh this evidence after a head or base changes.

## T0 Quick Start: Real Git and the Real CLI

Run this from the selected checkout on a Git version admitted by
`ACQUISITION_PATCHED_TRACKS` in `src/metabrowser/git/process.py`. A refusal on an older
Git is valid negative evidence, but does not pass acquisition.
These commands do not patch the version check or use a CLI test double.

```shell
QA_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/metab-alpha-fixture.XXXXXX")"
QA_ROOT="$(cd "$QA_ROOT" && pwd -P)"
git init --quiet --initial-branch=main "$QA_ROOT/origin"
git -C "$QA_ROOT/origin" config user.name 'Alpha Fixture'
git -C "$QA_ROOT/origin" config user.email 'alpha@example.invalid'
mkdir "$QA_ROOT/origin/docs"
printf '# Alpha fixture\n\n[Guide](docs/guide.md)\n' > "$QA_ROOT/origin/README.md"
printf '# Guide\n\nPinned content.\n' > "$QA_ROOT/origin/docs/guide.md"
printf '{"answer":42}\n' > "$QA_ROOT/origin/data.json"
git -C "$QA_ROOT/origin" add .
git -C "$QA_ROOT/origin" commit --quiet -m 'Add alpha fixture'
QA_OID="$(git -C "$QA_ROOT/origin" rev-parse HEAD)"
QA_URL="file://$QA_ROOT/origin"
export METABROWSER_HOME="$QA_ROOT/home"
test ! -e "$METABROWSER_HOME"

uv --config-file uv.toml run --frozen metab "$QA_URL" --no-serve
uv --config-file uv.toml run --frozen metab "$QA_URL" --no-serve
uv --config-file uv.toml run --frozen metab "$QA_URL" --show README.md
uv --config-file uv.toml run --frozen metab "$QA_URL" --show docs/guide.md
uv --config-file uv.toml run --frozen metab "$QA_URL" --show data.json
uv --config-file uv.toml run --frozen metab "$QA_URL" --api '/api/tree?depth=2'
uv --config-file uv.toml run --frozen metab "$QA_URL" --api /api/index/progress
uv --config-file uv.toml run --frozen metab "$QA_URL" --api /api/cache/sources
```

**Pass:** Both acquire calls identify the same store and `QA_OID`; the shows expose the
correct kinds and GitPath selections; the tree contains the nested guide and JSON file;
progress identifies a complete Git revision.
No data-mode command prints a serving banner, binds a port, or exposes a private cache
path.

Prove the cache hit does not need its origin, and that a bare path still follows local
filesystem semantics:

```shell
mv "$QA_ROOT/origin" "$QA_ROOT/origin-offline"
uv --config-file uv.toml run --frozen metab "$QA_URL" --no-serve
uv --config-file uv.toml run --frozen metab "$QA_URL" --show docs/guide.md
uv --config-file uv.toml run --frozen metab "$QA_ROOT/origin-offline" --show README.md
```

**Pass:** The first two commands reuse the original store/revision without the origin;
the third opens an ordinary filesystem selection.
The store is a full clone, so every read works with the origin gone; this proves
local-origin reuse, not GitHub transport.

For refusal, read-only-home, recovery, and HTML regression procedures, continue with the
[foundation QA runbook](../../../qa-v012-repository-library.md).
An `ssh` source and `--walk` on a Git source must still refuse; a `file://` or
`https://` source serves and answers `--show`, `--api`, and `--check-api`. Change those
expectations only in the implementation PR that adds the capability and its acceptance
evidence.

## Automated Evidence

Run `make verify` on the integration head.
It owns formatting, types, parity, Python and browserless tests, CLI goldens, dependency
audits, package inspection, and installed-wheel smoke tests.
A focused pass speeds diagnosis but does not replace that gate.

The current focused foundation lane is executable now:

```shell
uv --config-file uv.toml run --frozen pytest \
  tests/test_cli_acquire.py \
  tests/test_cli_cache_acquire_golden.py \
  tests/test_cli_cache_recovery_golden.py \
  tests/test_cli_git_pin_golden.py \
  tests/test_cli_no_serve_surface.py \
  tests/test_cache_acquire.py \
  tests/test_git_tree_source.py \
  tests/test_git_revision_content_routes.py \
  tests/test_git_revision_open.py \
  tests/test_git_full_clone_acceptance.py \
  tests/test_source_session.py \
  tests/test_content_trust.py
```

Several acquisition tests patch `require_acquisition_git` so the suite runs on older CI
Git. Keep those deterministic tests, but do not count them as proof of an unmodified
installed CLI on the minimum admitted Git.
That proof is the `admitted-git` CI job, which runs `make test-admitted-git` with
nothing patched on each Git release the job’s matrix builds.

### Add coverage with each implementation PR

These are acceptance obligations, not names of test commands that already exist.
Use existing pytest, tryscript, production JavaScript sessions, and installed-wheel
harnesses; do not introduce a second test framework merely for the alpha.

| Owning step | Efficient automated scenario | Assertion that makes it meaningful |
| --- | --- | --- |
| Foundation stabilization | Multi-entry CLI pin golden: nested directories, distinct kinds, nonempty filtered trees, history and comparison | Actual membership, ordering, counts, selections, typed unsupported states, and content (`mb-3z4d`) |
| Foundation stabilization | Same injected acquisition failure through `--no-serve`, cache API, pin API, and `--show` | Consistent sanitized user error and exit status; no traceback or staging-path disclosure |
| Foundation stabilization | Two processes reading distinct OIDs while an acquisition publishes or recovers | Immutable reads survive; no shared checkout/index; cancellation releases resources; lock contention cannot stall a serving event loop (`mb-677z`) |
| Steps 3 and 5: URL open | Installed CLI subprocess → URL reducer → acquisition → server → request | Correct selected object/path, mandatory untrusted profile, real lifecycle teardown, typed cold-cache errors |
| Steps 4 and 5: selected refs | Slash-containing branch, encoded path, branch advancement and two simultaneous subjects | Exact full OID per subject, no ambient `HEAD` substitution, no checkout mutation, no silent branch fallback |
| Step 5: credential helper | `git credential fill` against conflicting ambient configuration | Only `https://github.com` reaches `gh`; the user’s global helpers are cleared, and no other host gets a helper |
| Step 6: `gh` runner | Deterministic fake `gh` process → runner → pull-request record → CLI model | Bounded bytes/pages/time; missing `gh` or login, 403/404, rate limit, cancellation, and invalid payloads remain distinct |
| Step 6: pull-request record | PR from a fork or a deleted fork; force-push between observation and fetch | Record OIDs and content agree or return an explicit unavailable/stale state |
| Step 7: pull-request page | Production browserless lifecycle and CLI route goldens, then wheel subprocess E2E | Address parse/format, reload selection, back/forward model, disposal, document/diff identity, offline state and truncation agree |

A deferred capability gets its coverage rows when it is planned.

Keep complete normalized transcripts and add assertions for important relationships; do
not wildcard full OIDs, counts, or fixture values that can be pinned.
New routes and functional aspects need evidence in the
[parity map](../../architecture/arch-views-models-routes.md) in their owning PR.
Fixtures should be small and synthetic.

## Manual End-to-End Matrix

Run a row only after its entry condition exists.
Mark an unavailable feature **blocked**, not passed or silently skipped.
Use one public fixture repository with a known branch, commit, file, and PR; record
immutable OIDs and the observation time so a changing live repository cannot invalidate
the result unnoticed.
Use an operator-owned private fixture for private-access testing; keep its identifiers
and contents out of committed docs and logs.

| ID / milestone | Operator action | Required result |
| --- | --- | --- |
| M01 / T0 | Start the local manual corpus; open Markdown, source, JSON/JSONL, image, binary and HTML; use narrow/wide panes and both themes | Existing views, local Git history/diffs, links, focus and selection remain usable; no unexpected console/network errors |
| M02 / T1 | Paste repository, `/tree/`, `/blob/`, commit and raw URLs, including a branch containing `/` and a path containing spaces/Unicode | Correct repository, full OID, path and supported line intent; ambiguous or rejected addresses have a recoverable explanation |
| M03 / T1 | Follow relative Markdown links and open base/head files from a diff; reload, copy link, back/forward and open a second tab | Selection and revision survive each action; content never silently switches to default `HEAD` |
| M04 / T1 | Open two different branches concurrently; inspect the origin checkout and its `.git` before/after | Stable independent views; no branch/index/worktree writes to the user checkout |
| M05 / T1 | Warm content, stop the process, disable network access for the test process, restart and reopen | Same cached OIDs/content with honest offline state; unavailable uncached blobs are distinct from missing files |
| M06 / T1 | Browse acquired hostile HTML/Markdown with a populated cache; try preview-origin API access | Forced untrusted profile; no unintended executable preview/plugin loading, no cache metadata access from the preview origin |
| M07 / T2 | Paste a direct PR URL into a cold fixture home, with no PR index | PR title/body/status/check/review summaries and selected diff render; direct addressing succeeds independently of discovery |
| M08 / T2 | Open an unchanged and changed Markdown file at both PR base and head; inspect binary/rename/deletion entries | Files and comparisons use recorded OIDs; unsupported/unavailable content is explicit |
| M09 / T2 | Warm one PR, restart offline, then open the PR and its diff | Cached metadata and content agree; freshness, partiality and missing refs are visible; no unnecessary credential lookup on cache hits |
| M10 / T2 | Exercise a private fixture, an unauthorized fixture, missing `gh`/login, revoked access and a rate-limited fixture | Clear typed recovery, no interactive login on a request path, no token/private payload in diagnostics, no principal mixing |
| M10b / T2 | Bind a disposable attached checkout, change its remote to a different fixture repository, then use the explicit rebind operation | **Deferred; not run for v0.12.** Automatic rebind refuses; explicit recovery identifies the new repository and disposes of the old binding without presenting old snapshots as new content |
| M11 / T2 | Cancel or restart during refresh; revisit the previously complete PR | Prior snapshot remains usable; cancelled work does not publish mixed or regressed state |
| M12 / T3 | Page/filter PR navigation, then directly open a PR outside the current window | **Deferred; not run for v0.12.** Counts and completeness describe the bounded query; direct selection does not falsify that query |
| M13 / T3 | Inspect resolved, unresolved, outdated and unmappable review threads | **Deferred; not run for v0.12.** State remains explicit; no invented line placement or disappearing thread |

Use real browser evidence for layout, browser history, iframe origin isolation, CSP,
keyboard focus, and platform behavior.
Keep deterministic selection and lifecycle logic covered by production-module
browserless sessions as well.
A screenshot alone does not prove source identity, networking, or cache correctness.

The live GitHub smoke is read-only: open a small bounded set of existing resources.
Creating fixture repositories/PRs, posting reviews/comments, or changing permissions is
fixture preparation, separate from running the read-only smoke.
Record those prerequisites explicitly when a live case needs them; deterministic CI
fixtures cover failure cases that are costly to force against GitHub.

## Recording Results and Landing

For each run, attach the following to the integration PR or QA bead:

- Exact integration head/base/main, installed wheel/version, platform/tool versions,
  fixture revision/PR and observation time.
- Scenario ID, command or browser action, expected and actual result, and **pass / fail
  / blocked / not run**. Record skips with their reason.
- Full normalized CLI result, relevant browser screenshot/console evidence, and the CI
  run links. Keep credentials, private fixture data and personal paths out of public
  evidence.
- For a failure, the owning phase/PR, a bead, reproduction and acceptance test.
  Reuse existing findings instead of filing duplicates.

A candidate clears its milestone only after the required rows pass on the installed
artifact with unmodified production entry points.
For a preliminary release, also build and install its wheel in a clean environment and
repeat the cold/warm/offline path and the relevant browser rows.
`make build` supplies the baseline installed-wheel checks; the feature-specific
installed scenarios above must extend that evidence.

Before landing the whole stack, refresh the per-layer review ledger after all functional
changes, resolve or explicitly disposition every finding, reconcile beads/specs, confirm
ready-for-review state, and run green per-layer CI plus the top integration check
against current `main`. Preserve the formal stack and add future PRs above its current
tip. Land and tag only after the agreed milestone has passed and the user authorizes
landing/release; this testing plan performs neither.

### Landing status

Recorded 2026-09-30. Three commands give the current state, and they win where this
section disagrees: `tbd list --label release:v0.12.0` lists the open v0.12 beads,
`tbd show mb-n2ro` names the ones that block landing, and `gh pr list --state open`
shows the stack.

The acceptance rerun on the stack’s tip passed: M03’s and M08’s base and head rows (View
file, [#248](https://github.com/jlevy/metabrowser/pull/248)) are in the
[QA record](../../qa/qa-2026-09-24-v012-alpha-acceptance.md) under “Rerun on #250”.

Open before landing:

- **Startup and eager-load cost** (`mb-l8c2`). Against `main`, startup does more import
  work in every mode and the eagerly loaded JavaScript grew, while route times and
  memory are unchanged; the bead holds the measurements.
  The wall-clock pairs against `main` still need a quiet machine.
- **Test-suite review** (`mb-06up`). Its children labelled `release:v0.12.0` are landing
  work; the others follow the release.
- **M10’s private and revoked cases** are blocked until an operator-owned private
  fixture exists.
- **The checklist above**: the review ledger covering every layer, a disposition for
  each finding, every pull request on the stack out of draft, and green CI on the final
  tip against current `main`.

Checks only the user can make:

- **Paint in other browsers.** The acceptance run used one Chromium pane that was hidden
  for most rows, so it read DOM state and network traffic rather than pixels.
  Focus rings, layout at each width, the lazily rendered review bodies, and the HTML
  Preview frame were not observed, and no other browser engine was tried.
- **The user’s own GitHub account**, including a private repository: authorized private
  access and revoked access.
- **Third-party plugins against Plugin SDK 0.7.** A plugin that writes copy or Load more
  markup by hand gets a button that silently does nothing until it migrates; the
  `CHANGELOG.md` entry for the break gives the migration.

Landing is one fast-forward of `main` to the stack’s tip, on the user’s approval.
No layer merges separately.
`main` must be an ancestor of the tip at that moment, which the merge-based restacks
preserve and `git merge-base --is-ancestor origin/main <tip>` confirms.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
