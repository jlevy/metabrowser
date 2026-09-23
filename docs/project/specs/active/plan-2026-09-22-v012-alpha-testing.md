# Plan: v0.12 Alpha Testing and Stack Acceptance

**Status:** Active testing and delivery plan.
The stack currently supports local `file://` acquisition and CLI inspection of immutable
Git revisions.
A GitHub URL or pull-request browsing alpha requires the additional phases
below.

## Outcome and Scope

An operator should be able to paste a GitHub repository, branch, file, or pull-request
URL, inspect the intended immutable content, and reopen previously acquired content
offline. A directly addressed PR must work without first populating a discovery index.
Tests must prove the installed application path as well as the individual contracts.

Implementation continues as additional PRs on
[stack 218](https://github.com/jlevy/metabrowser/stack/218). Keep the stack together
until it is stabilized; an intermediate testing milestone does not authorize merging a
lower layer. The landing coordinator is `mb-n2ro`.

The [repository plan](plan-2026-08-11-open-repo-from-git-url.md) and
[GitHub plan](plan-2026-08-27-github-provider-and-pull-requests.md) own feature design.
This plan owns executable testing milestones and evidence requirements, without reducing
the full v0.12 milestone.
Reviews and run results belong on PRs and beads, not in this procedure.
Tooling maintenance, including tbd releases or shortcut cleanup, is not a prerequisite
for these product milestones.

## Feature Coverage

The states below describe implementation, not merge approval.
**Built on stack** means code exists in the integration build; **partial** means a
working path exists but integration or acceptance remains; **planned** means the user
workflow still needs implementation.
The owning specs retain the detailed checklists.

| Feature / owning phase | State | What works and what remains | First useful test |
| --- | --- | --- | --- |
| Local browsing and Git history/diffs | Released baseline | Filesystem Markdown, structured data, images, binary content, Git history/detail and diff infrastructure remain available | T0 browser regression |
| HTML trust foundation | Built on `main` | Sandboxed raw responses, same-origin API proof and `--untrusted` exist; every new acquired-content entry point must apply them | T0 regression; T1 acquired-content isolation |
| Repository design and hosted-review records / 0–0D | Built on stack | Identity, source binding, repository/PR/comment/review/thread/check records, schemas, validators, corpora and installed contract discovery exist; there is no GitHub acquisition or PR UI yet | Automated contract and oracle tests |
| Private cache format / 1A | Built on stack | Owner-only POSIX home, `f01` records, locks, safe publication, quarantine/trash/reclamation and cache-inspection routes exist; Windows storage fails closed pending ACL support | T0 cache and recovery tests |
| Local Git acquisition / 1B-a | Partial | `file://` acquisition publishes a worktree-free store, pins the default OID, prefetches its tree and reuses the cache offline; error, cancellation, minimum-Git and golden acceptance remain | T0 real CLI |
| HTTPS and SSH acquisition / 1B-a and 2A | Planned | Sources are recognized but refused; ordinary GitHub URL browsing needs HTTPS transport, and SSH has its own transport/prompt-suppression obligations | T1 HTTPS; separate SSH lane |
| Background object convergence / 2B | Planned | Default-tree prefetch and complete/converging state recording exist; `mb-bgn8` owns the worker after serving/job support, without blocking 1B-a publication | T1 object availability and offline cases |
| Source sessions and content readers / 1B-b | Partial | Attached filesystem and immutable Git subjects share capability-aware routes and bounded plugin content ports; integrated acceptance remains | T0 CLI/API and local browser regression |
| Immutable Git revisions / 1B-c | Partial | Byte-safe paths, full-OID trees, batch readers, leases and content-kind handling work through `--show` and `--api`; acquired-Git HTTP startup, `--walk` and `--check-api` still refuse | T0 pin/content/lease tests |
| GitHub URL reduction and serving / 2A | Planned | String-preserving CLI classification and the reducer protocol exist; registered reducers, URL selection, HTTPS opening, HTTP serving and enforced trust still need implementation | T1 repository/tree/blob/commit/raw URLs |
| Selected-ref jobs / 2B | Planned | Git process/store primitives exist; bounded jobs, cancellation/coalescing, credential leases, selected-ref fetching and publication do not | T1 missing refs, cancellation and races |
| Branch/tag/commit/path selection / 2C | Planned | Internal subjects can name an OID; URL ref/path disambiguation, slash-containing refs and branch-opening integration remain | T1 concurrent revisions and navigation |
| GitHub transport and authentication / 3A | Planned | Hardened `gh` execution, REST/GraphQL adapter, lifecycle registry, auth broker and Git credential bridge remain | T2 public/private access and failures |
| Provider binding and mirrors / 3A | Planned | Binding/partiality/publication records and fail-closed validation exist; persistent mirrors, repository summaries, current/last-complete snapshots, refresh and explicit rebind do not | T2 binding, publication and offline restart |
| Direct PR acquisition / 3B | Planned | Formats exist; fetching one PR and its companion records/Git objects, fork/force-push handling and durable offline reuse remain | T2 cold PR URL without an index |
| Direct PR view / 4A | Planned | Generic Markdown/revision/diff facilities are reusable; hosted routes, address lifecycle, PR document/status/changed-file views and pinned comparison remain | T2 end-to-end PR browsing |
| PR discovery / 3C | Planned | Query/index contracts exist; bounded paginated acquisition and durable query-specific indexes remain | T3 paging, filters and partiality |
| PR navigation / 4B | Planned | Virtual collection SDK, PR panel, virtualization, focus/restoration, child files and truthful counts remain | T3 discovery and direct selection together |
| Review anchors / 4C | Planned | Anchor models exist; production line/range mapping, rendering and explicit outdated/unmappable states remain | T3 review-thread navigation |

The plans also retain these separate or later features:

| Feature | Scope and test boundary |
| --- | --- |
| Working-tree status and working-tree diffs | Separate attached-filesystem work; existing history/diffs do not complete the status panel, and status does not gate a worktree-free source |
| Full repository catalog and management | Later than the initial slice: coordinated refresh/repair/purge, size accounting and discarded-object compaction; basic inspection/reclamation is already built |
| Repository chooser and session switching | Later catalog UI, recent/favorite/offline states and per-repository selection restoration; source-session primitives are already built |
| Very-large repositories | Later measured acquisition, shallow/progressive deepening and honest truncation/blame behavior |
| Issues and timelines | Later Phase 5 records, acquisition and views |
| Stacked PR browsing | Later Phase 6 derived relationships, adjacent comparisons and navigation; distinct from using a PR stack to deliver this work |
| Hosted releases and assets | Later sibling contracts, direct acquisition/views and discovery; asset bytes remain on demand |
| GitLab | Later adapter after the GitHub-first contracts and views |
| Automatic eviction | Deferred until measurements justify a policy |

SSH remains planned generic transport; it has not been removed from the full repository
plan merely because the first browser milestone emphasizes HTTPS. Remote GitHub writes
and cached worktree materialization are non-goals.
Representing an LFS pointer or gitlink does not promise automatic LFS downloads or
submodule checkouts.

## Mechanical Mergeability and Product Readiness

Check the live stack for adjacent parents, inclusion of current `main`, clean merge
results, passing checks and ready-for-review PR state.
Resolve any actual branch rule or review requirement reported by GitHub.
Record that evidence on the integration PR.

Ready-for-review status and a clean merge do not complete the feature and acceptance
work above. A guarded foundation build can be mechanically mergeable while T1–T3 remain
unimplemented. Keep outstanding product findings in their beads and preserve the agreed
whole-stack landing decision independently of those GitHub flags.

## Next PRs and Agent Handoff

The next implementation task begins with foundation stabilization, then advances through
one new stacked PR per phase.
All new PRs extend the current tip of Stack 218; review and test each phase before using
its exact green head as the next base.
Keep the whole stack together for the final landing decision.
No tbd release or process cleanup is a prerequisite.

| New PR | Implementation and acceptance owners | Testable checkpoint |
| --- | --- | --- |
| Foundation stabilization | Findings under `mb-gacf`; acquisition/source/pin acceptance `mb-k900`, `mb-tsdc`, `mb-hoae`; integration-base gate `mb-j439` | Complete the remaining T0 evidence and record one reviewed, green foundation head |
| Phase 2A: repository URL opening | Reducers `mb-12cz`, HTTPS acquisition `mb-s1lt`, opening/serving `mb-ew38`; review/publication `mb-innz` | Cold public HTTPS repository URL opens the default immutable revision in the browser and CLI; warm/offline reuse and forced trust pass |
| Phase 2B: object jobs and convergence | Selected-ref jobs `mb-jlon`, background convergence `mb-bgn8`; review/publication `mb-bf94` | Bounded fetch, cancellation, identity isolation, publication races and post-serving convergence are testable through CLI/models |
| Phase 2C: selected revisions | Selection `mb-2xq7`; review/publication `mb-9aku` | Branch/tag/OID/path resolution, missing-ref acquisition, concurrent subjects and offline navigation complete T1 |

The existing `mb-j439` gate remains open until the foundation acceptance is complete.
The next agent should make a focused stabilization PR above the live stack tip and
record the corrected findings there, preserving the earlier PR review history.
Do not reopen the acquired-HTTP acceptance cycle: foundation checks exercise the
existing CLI and content routes; the new server/browser path is proved in Phase 2A.

For foundation stabilization, use the existing finding beads rather than inventing a
second checklist of completion claims:

- `mb-sumg`: share acquisition-error mapping across CLI entry points and prove safe
  below-floor refusal.
- `mb-3z4d`, `mb-dg00`: nontrivial pin and acquisition/recovery goldens.
- `mb-pkho`, `mb-d1za`, `mb-oueh`: missing-object behavior and actual supported/minimum
  Git execution evidence.
- `mb-rati`, `mb-e32d`, `mb-lp89`: measured stall bounds, distribution-backport policy
  and child-process cancellation disposition.
- `mb-677z`, `mb-t7qs`: resolve async-path lock blocking and establish the measured
  large-blob/read-cost policy before extending serving.

Re-read the current findings and acceptance owners before changing their status.
The
[top-level review](https://github.com/jlevy/metabrowser/pull/216#issuecomment-5786877244)
contains the evidence and design assessment.
A green CI result or a ready-for-review flag does not close these obligations.

Phase 2A includes real HTTPS Git acquisition; URL parsing alone cannot satisfy its
cold-open checkpoint.
`mb-s1lt` owns that transport within the Phase 2A PR and blocks its publication.
Parent `mb-bi2c` retains the complete HTTPS/SSH transport scope and stays open until SSH
acceptance is also complete.
Final landing through `mb-n2ro` depends on this parent, so the separate SSH lane remains
in the full v0.12 scope without blocking the first HTTPS browser checkpoint.
Public repository browsing does not require the GitHub API.

The next agent should reuse these implementation boundaries:

- `cli/main.py` preserves root strings; connect installed reducers there.
- `cache/urls.py` owns generic classification; add declared ownership and terminal
  rejection without putting GitHub syntax in cache identity.
- `cache/acquire.py` currently refuses remote transports; retain its safe publication
  and cache-hit path when adding HTTPS.
- `cli/git_pin_cli.py`, `source.py`, `git/tree_source.py` and
  `cache/repository_store.py` provide the existing acquisition, lease, subject and
  content lifecycle. `cli/acquire_cli.py` owns the current Git-error normalization.
- `git/process.py` owns Git execution and no-lazy-fetch policy.
  Phase 2B adds jobs and neutral provider resource models; selection remains
  network-free.

These paths are relative to `src/metabrowser/`. Keep GitHub API/auth/mirrors and PR
hydration/views for Phases 3A onward; full catalog, chooser, working-tree status and
materialized checkouts are outside this batch.

## Testing Milestones

| Milestone | Entry condition | User-visible acceptance | Current availability |
| --- | --- | --- | --- |
| T0: local Git foundation | Current integration tip, supported Git, isolated application home | Acquire a `file://` origin, reopen its default full OID, inspect files/tree through `--show` and `--api`, and preserve local browsing | Runnable now; use the quick start below and the [foundation QA runbook](../../../qa-v012-repository-library.md) |
| T1: repository URL alpha | URL open and serving, selected-ref jobs, selected-branch integration, trust integration | Open repository/tree/blob/commit/raw URLs; view content, history, and diffs; preserve slash-containing refs and path/line intent; reopen cached content offline | Pending repository Phases 2A–2C |
| T2: direct PR alpha | T1 plus provider transport/auth/mirror, direct PR bundle, and direct PR view | Paste a PR URL absent from every index; read its description, review/check state, changed files, and pinned comparison; reload and reopen offline | Pending GitHub Phases 3A, 3B, and 4A |
| T3: full v0.12 acceptance | T2 plus discovery/navigation, planned review anchors and separate SSH transport acceptance | Bounded paginated PR navigation with honest counts/partiality, direct selection outside that index, and explicit outdated/unmappable anchors | Pending Phases 3C, 4B, and 4C |

T2 is the proposed first preliminary GitHub PR alpha.
T3 remains the full planned release scope.
A T0 build must be described as a foundation test build, not as GitHub URL or PR
support. SSH acquisition is separately tracked; do not infer it from an HTTPS or
`file://` pass.

Begin narrower tests before a whole milestone is complete: Phase 2A should first prove
one default-branch repository URL opening in a browser; 2B/2C then add selected refs and
branches. Phase 3A can test an acquired repository summary through the CLI, and 3B can
test a direct PR bundle before 4A adds its view.
Record that narrower coverage without claiming the complete T1 or T2 milestone.

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
   Record the known pin acquisition-error defect (`mb-sumg`) as a failure if reproduced;
   a successful happy path does not clear it.
5. **After 2A–2C, test real repository URLs.** Run M02–M06 through the installed CLI and
   a browser: URL intent, relative links, concurrent branches, offline restart and
   acquired-content trust.
   This is the first milestone for testing GitHub repository browsing end to end;
   ordinary public repository browsing does not need the GitHub API.
6. **After 3A/3B/4A, test one PR completely.** Run M07–M11, including M10b, from a cold
   home without an index, then warm/restart/offline.
   Inspect both sides of changed files, test private access and explicit rebind, and
   interrupt a refresh.
   This is the first proposed preliminary PR alpha.
7. **After discovery/navigation/anchors, test the full slice.** Run M12–M13 with
   multiple pages, filters, a directly opened PR outside the index, and
   outdated/unmappable review threads.
   This completes the broader T3 milestone.

At each stage, run its automated scenarios before manual browsing, then capture the
actual browser results.
Future rows stay blocked until their entry conditions exist; repeat relevant regressions
when a later layer changes a shared path.

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
This proves local-origin reuse, not GitHub transport or every promisor-blob offline
case.

For refusal, read-only-home, lease, recovery, and HTML regression procedures, continue
with the [foundation QA runbook](../../../qa-v012-repository-library.md).
At T0, `metab "$QA_URL" --no-open`, HTTPS/SSH acquisition, Git `--walk`, and Git
`--check-api` must still refuse.
Change those expectations only in the implementation PR that adds the capability and its
acceptance evidence.

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
  tests/test_cli_git_pin_golden.py \
  tests/test_cli_no_serve_surface.py \
  tests/test_cache_acquire.py \
  tests/test_git_tree_source.py \
  tests/test_git_revision_content_routes.py \
  tests/test_git_revision_lease.py \
  tests/test_source_session.py \
  tests/test_content_trust.py
```

Several acquisition tests patch `require_acquisition_git` so the suite runs on older CI
Git. Keep those deterministic tests, but do not count them as proof of an unmodified
installed CLI on the minimum admitted Git.
Add that execution lane before claiming the acquisition floor has been exercised end to
end.

### Add coverage with each implementation PR

These are acceptance obligations, not names of test commands that already exist.
Use existing pytest, tryscript, production JavaScript sessions, and installed-wheel
harnesses; do not introduce a second test framework merely for the alpha.

| Owning phase | Efficient automated scenario | Assertion that makes it meaningful |
| --- | --- | --- |
| Foundation stabilization | Multi-entry CLI pin golden: nested directories, distinct kinds, nonempty filtered trees, history and comparison | Actual membership, ordering, counts, selections, typed unsupported states, and content; the current one-file, depth-zero golden is insufficient by itself (`mb-3z4d`) |
| Foundation stabilization | Same injected acquisition failure through `--no-serve`, cache API, pin API, and `--show` | Consistent sanitized user error and exit status; no traceback or staging-path disclosure |
| Foundation stabilization | Two processes leasing distinct OIDs while maintenance/recovery runs | Immutable reads survive; no shared checkout/index; cancellation releases resources; lock contention cannot stall a serving event loop (`mb-677z`) |
| 2A URL open | Installed CLI subprocess → URL reducer → acquisition → server → request | Correct selected object/path, mandatory untrusted profile, real lifecycle teardown, typed cold-cache errors |
| 2B/2C selected refs | Slash-containing branch, encoded path, branch advancement and two simultaneous subjects | Exact full OID per subject, no ambient `HEAD` substitution, no checkout mutation, no silent branch fallback |
| 2B convergence | Start serving a partially populated store, converge through a bounded job, interrupt/restart, and repeat with unavailable network | Serving starts before convergence; available content remains usable; progress/completion/failure are honest; content reads never trigger implicit fetches |
| 3A provider foundation | Deterministic fake `gh` process → adapter → auth-scoped mirror → CLI model | Bounded bytes/pages/time; missing login/scope, 403/404, rate limit, partial GraphQL data, cancellation, and invalid payloads remain distinct |
| 3A credential bridge | Controlled credential session and Git transport with conflicting ambient configuration | One principal across API and Git; account switch, expired lease, redirect, and cancellation cannot supply another principal or disclose a credential |
| 3A binding and explicit rebind | Attached checkout changes its remote or a source observes a different provider repository; exercise rejection and the explicit user operation | No silent identity reassignment; rebind proof and disposition are validated, old snapshots become honestly stale/detached, and private state cannot cross bindings |
| 3A publication | Slow old refresh races fast new refresh; interruption at publication boundaries | Current pointer cannot regress; failed/partial results preserve last-complete; reachable leased snapshots survive recovery |
| 3B direct PR bundle | PR outside/absent from index; fork/deleted fork; force-push between observation and fetch | Metadata OIDs and content agree or return explicit unavailable/stale state; direct fetch neither requires nor rewrites index membership |
| 4A direct PR view | Production browserless lifecycle and CLI route goldens, then wheel subprocess E2E | Address parse/format, reload selection, back/forward model, disposal, document/diff identity, offline state and partiality agree |
| 3C/4B discovery | Multiple pages, tie-breakers, changed filters, truncation, failed page, direct selection outside index | No fabricated completeness/counts; listing fetches no PR bodies or Git refs; bounded memory and stable navigation |
| 4C anchors | File, single-line, range, outdated and unmappable anchors | Map only against sufficient immutable identity/context; show original anchor when no current mapping is justified |

Keep complete normalized transcripts and add assertions for important relationships; do
not wildcard full OIDs, counts, or fixture values that can be pinned.
New routes and functional aspects need evidence in the
[parity map](../../architecture/arch-views-models-routes.md) in their owning PR.
Fixtures should be small and synthetic.
The existing provider oracle proves record representability; it is not a substitute for
adapter-to-store-to-view execution.

## Manual End-to-End Matrix

Run T1–T3 rows only after their entry conditions exist.
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
| M10b / T2 | Bind a disposable attached checkout, change its remote to a different fixture repository, then use the explicit rebind operation | Automatic rebind refuses; explicit recovery identifies the new repository and disposes of the old binding without presenting old snapshots as new content |
| M11 / T2 | Cancel or restart during refresh; revisit the previously complete PR | Prior snapshot remains usable; cancelled work does not publish mixed or regressed state |
| M12 / T3 | Page/filter PR navigation, then directly open a PR outside the current window | Counts and completeness describe the bounded query; direct selection does not falsify that query |
| M13 / T3 | Inspect resolved, unresolved, outdated and unmappable review threads | State remains explicit; no invented line placement or disappearing thread |

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
tip. Merge and tag only after the agreed milestone has passed and the user authorizes
landing/release; this testing plan performs neither.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
