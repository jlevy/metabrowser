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

## Testing Milestones

| Milestone | Entry condition | User-visible acceptance | Current availability |
| --- | --- | --- | --- |
| T0: local Git foundation | Current integration tip, supported Git, isolated application home | Acquire a `file://` origin, reopen its default full OID, inspect files/tree through `--show` and `--api`, and preserve local browsing | Runnable now; use the quick start below and the [foundation QA runbook](../../../qa-v012-repository-library.md) |
| T1: repository URL alpha | URL open and serving, selected-ref jobs, selected-branch integration, trust integration | Open repository/tree/blob/commit/raw URLs; view content, history, and diffs; preserve slash-containing refs and path/line intent; reopen cached content offline | Pending repository Phases 2A–2C |
| T2: direct PR alpha | T1 plus provider transport/auth/mirror, direct PR bundle, and direct PR view | Paste a PR URL absent from every index; read its description, review/check state, changed files, and pinned comparison; reload and reopen offline | Pending GitHub Phases 3A, 3B, and 4A |
| T3: full v0.12 acceptance | T2 plus discovery/navigation and planned review anchors | Bounded paginated PR navigation with honest counts/partiality, direct selection outside that index, and explicit outdated/unmappable anchors | Pending Phases 3C, 4B, and 4C |

T2 is the proposed first preliminary GitHub PR alpha.
T3 remains the full planned release scope.
A T0 build must be described as a foundation test build, not as GitHub URL or PR
support. SSH acquisition is separately tracked; do not infer it from an HTTPS or
`file://` pass.

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
| 3A provider foundation | Deterministic fake `gh` process → adapter → auth-scoped mirror → CLI model | Bounded bytes/pages/time; missing login/scope, 403/404, rate limit, partial GraphQL data, cancellation, and invalid payloads remain distinct |
| 3A credential bridge | Controlled credential session and Git transport with conflicting ambient configuration | One principal across API and Git; account switch, expired lease, redirect, and cancellation cannot supply another principal or disclose a credential |
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
changes, resolve or explicitly disposition every finding, reconcile beads/specs, remove
draft status only when its obligations are complete, and run green per-layer CI plus the
top integration check against current `main`. Preserve the formal stack and add future
PRs above its current tip.
Merge and tag only after the agreed milestone has passed and the user authorizes
landing/release; this testing plan performs neither.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
