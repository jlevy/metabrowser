---
type: is
id: is-01m2yxd3tnr1s2zf0h0jat1ey2
title: "v0.11 stabilization review: independent full review of stack #218 and #209 against specs and beads"
kind: task
status: in_progress
priority: 1
version: 44
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
child_order_hints:
  - is-01m2zpvykba6wabg6ms9wawzb0
  - is-01m2zpvzfx40az8dvj2peg3hb2
  - is-01m2zpw18m2z2nmprgkmzq3jwk
  - is-01m2zpw31yzxj69k3fdzzp3qn7
  - is-01m2zpw4zkmx00dk5gh5s4kjqm
  - is-01m2zpw6dzfwa6a86z4vc8yfzc
  - is-01m2zpw7z0f201xxwtvzb51kyk
  - is-01m2zpw9bkkn7m6gwv0q5cbeqd
  - is-01m2zpway7zvshv7271v9cp498
  - is-01m2zpwenhppjpks39tf0nxkkb
  - is-01m2zpwg44k0y7snevbfqdyw8k
  - is-01m2zpwhgmcptq6ge42ckj84rc
  - is-01m2zpwjvq4pq1cqbdqa1avrp3
  - is-01m2zpwm7b0ns673t2jyje7fdg
  - is-01m2zpwnbv0z16dxng8s75dn4b
  - is-01m2zpwpet6pzt8zvvmnx082ac
  - is-01m2zpwqfy7v676azc2mxx3g5s
  - is-01m2zpwrm0069gs0swx9m6xqfr
  - is-01m2zpwswpwq4hm7kr70ddpbjy
  - is-01m2zpwtxsex7zg035m9p3yvm7
  - is-01m2zpwvxd9vp6vpn587bsz6p7
  - is-01m2zpwxfk2v9gqyrt5yg6a59x
  - is-01m2zpwyzk68zpmngrxadssn2r
  - is-01m2zpx0fhq4x5e1qtcteearj5
  - is-01m2zpx1svn4c8an4mm9r9mv8z
  - is-01m2zpx351fryc2z9hjb2m4j4a
  - is-01m2zpx4d15neap9x8fcf36tq4
  - is-01m2zpx5m27d6tnn4qf6zbhfv8
  - is-01m2zpx6gr7kcfmwvbrfhbse7s
  - is-01m2zpx7pmkbxzgkp7cwqt6qzb
  - is-01m2zpx9218wz0egrejamr3651
  - is-01m2zpxck1jqrmv4a2dhwve47v
  - is-01m2zpxg6x10hmbxayqh9ccag1
  - is-01m2zpxmwz32ykx0q3w62qhghh
  - is-01m2zpxqcyxkb5ajsh9zm2c47p
  - is-01m2zpxv9y2v992te1pdr2x52n
  - is-01m2zpxwxtv9pcjf6ynxcan41h
  - is-01m2zpxyf1qczg3r6cadfhh7sy
  - is-01m2zvfm9pdxz0emydeqedf9gq
created_at: 2026-09-20T08:02:30.356Z
updated_at: 2026-09-20T16:48:27.398Z
---
Follow-up to mb-rldx, which was closed at 2026-09-20T07:32Z by a fast pass while its own notes said the #216 browser/plugin, resource-lifecycle, CLI/parity, and docs review passes were unfinished. Independently verify the #140/#217/#216 fix commits (da73b878, 70091d81, bc8dd72b, de0f4f5a), complete the unreviewed areas, review #209 as the security gate for serving acquired Git, reconcile every PR review channel, and reconcile beads and spec checklists with the branches. Output: confirmed findings filed as beads on their owning layers, and an ordered stabilization plan. Read-only until the plan is agreed; do not merge (landing owner is mb-n2ro).

## Notes

# v0.11 stabilization review: consolidated findings (2026-09-20)

Independent re-review of stack #218 (#125 → #134 → #136 → #139 → #140 → #217 → #216) and
parallel PR #209, after `mb-rldx` was closed by a fast pass.
Eleven read-only reviewers; every defect below was reproduced or is provable by reading,
unless marked plausible.
Heads reviewed: #140 `da73b878`, #217 `70091d81`, #216 `de0f4f5a`, #209 `398cedd4`.
Nothing was changed on any branch, PR, or bead other than this one.

## Verdict per layer

| PR | Verdict |
| --- | --- |
| #125, #134 | Landable. Low format-hardening choices to decide before the format is frozen. |
| #136, #139 | Landable. Forward-looking design gaps only. |
| #140 | Close to landable. Two Low–Medium fixes. One unmet spec gate that depends on #209. |
| #217 | Not landable. One High, four Medium. Stay draft. |
| #216 | Not landable. Two High (one introduced by the R1 fix), six Medium. Stay draft. |
| #209 | Sound design, never reviewed before. One Medium fix before main; three integration items before serving acquired Git. |

The `mb-rldx` close-out claims are literally true (fix SHAs on heads, CI green, disposition
comments posted, Bugbot threads resolved).
The R1–R5, #217 R1–R3, and #140 R1–R2 fixes are correct at the root.
What was closed early: the unfinished #216 review passes, residuals of R3 and R5, and the
written record.

## Findings by owning layer

Fix on the owning layer, then restack upward.

### #140 (`claude/v011-cache-format-foundation`)

- S140-1 Low–Med. `cache/layout.py:292-297` `_preflight_layout` swallows
  `PrivateStorageError`; with a symlinked `config.yml`, a hard-linked or mode-0200 future
  `layout.yml`, `open_cache` writes 13–14 entries before refusing.
  Fix: delete the `try/except`; add the three cases to the no-mutation test.
- S140-2 Low–Med. `cache/reclaim.py:100-118` rmtree `onexc` handler raises `TypeError` for
  `os.open`/`os.scandir`; a staging entry with a mode-0000 subdirectory makes every
  `open_cache` fail. Reproduced on Python 3.14.
- S140-3 Low. Address length bound differs (`identity.py:52` vs `records.py:55`); raw
  `NotADirectoryError` with absolute path escapes `_has_durable_entries`
  (`layout.py:263-276`); `_MAX_CONFIG_BYTES` has no recorded measurement (measured about
  1.5 s for a 234 KiB config); Pydantic error text with input values reaches
  `problems[].message` (`atomic.py:93`).
- S140-4 Gate. Plan lines 1753–1760 require the `/raw` sandbox and same-origin proof to be
  evaluated against a populated cache before Phase 1B-a lands. The proof exists only on
  #209. `/api/cache/sources` returns local paths for `file://` sources. Nothing records
  the evaluation.

### #217 (`cursor/v011-cache-acquire-cli-bd04`)

- S217-1 High. `cache/acquire.py:182-194` `_parse_symref_head` keeps the last `ref:` line
  and ignores which ref it names. Any ordinary non-bare clone also advertises
  `refs/remotes/origin/HEAD`, so acquisition fails with "the source HEAD is not a branch"
  after a full fetch. Tests use only `git init` and `clone --bare` origins.
  Fix: accept the symref only when its name is exactly `HEAD`.
- S217-2 Medium. An untrusted origin's `refs/heads/zz/HEAD -> decoy` makes the published
  record name a branch that does not match the pinned commit. No ref validation before
  publication, although the spec step says to validate refs.
- S217-3 Medium. `git/process.py:279-301` builds the environment as a denylist. Ambient
  `GIT_ALLOW_PROTOCOL` overrides `protocol.allow=never`; `GIT_DEFAULT_REF_FORMAT=reftable`
  publishes a store the older admitted Gits cannot read. Fix: drop every `GIT_*` for
  isolated policies and set the wanted ones.
- S217-4 Med/Low. `ls-remote` runs with `cwd=home` and unrestricted discovery, so an
  enclosing repository's config is read (same class as R2). Fix:
  `GIT_CEILING_DIRECTORIES` or `--git-dir` of the staged repository.
- S217-5 Medium. `cli/acquire_cli.py:27-35` maps only the unsupported-version error; other
  `GitError`s escape as tracebacks, the timeout message leaks the staging path, and
  `_filter_honored` buffers `rev-list --objects` under a 32 MiB cap (refuses origins above
  roughly 500k objects, by arithmetic).
- S217-6 Stack. Commit `ad6e30f8` (below-floor refuse must not write the home) changes
  #217-owned code but sits only on #216. #217's head still has the bug; `mb-f6us` is
  closed. Move it down and restack.
- S217-7 Low. `reclaim_unreferenced_stores` scans stores × sources on every cache miss
  (plausible, extrapolated about 9–10 s at 100 × 100); detached-HEAD origins are refused
  only after the full fetch; timeout kills only the direct child.
- S217-8 Spec/CI. Phase 1B-a check-offs exist only on #216; four overclaim (ref
  validation, typed unsupported-Git state, persisted failed state, object-request oracle).
  No CI job runs acquisition on an admitted Git; the runner's Git is below the floor and
  tests monkeypatch it.

### #216 (`cursor/v011-git-revision-pin-bd04`)

- S216-1 High. Introduced by the R1 fix `bc8dd72b`. `git/tree_source.py:260-265,776-788`
  with caller `git/content_routes.py:508-510`: each nested `list_tree(child)` re-resolves
  through the parent and rebuilds every sibling. 1,000 subdirectories at default depth 2:
  about 11 s warm, 23 s cold; 4,000: 67 s warm. One `git ls-tree` spawn per child when
  cold. Fix: list by the known `entry.oid`, reparent only the match.
- S216-2 High for serving, Medium while CLI-only. Whole-index scans on the event loop on
  every request, uncached although the pin is immutable: `/api/tree` 1.2–1.5 s at 100k
  blobs, 12.7 s with a type filter; no node budget. R5 fixed only `tally`.
- S216-3 Medium. Content routes map only two typed Git errors; everything else, including
  the `GitTimeoutError` R3 now raises, is a bare 500 (`/api/git/*` answers 504). The error
  has no message, so the CLI prints an empty error. Reproduced by two reviewers.
- S216-4 Medium. Request-path store reads (`ls-tree`, `rev-parse`, `log`, `rev-list`,
  `show`, `diff`) run under the 900 s `ACQUISITION_POLICY`. R3 asked for this to be
  considered. A blobless store lazy-fetches under the default `READ_POLICY`, so
  no-lazy-fetch depends on every caller's policy choice. Fix: one `STORE_READ_POLICY`.
- S216-5 Medium, filesystem regression. `cli/show_cli.py:359-365`: `--show --plugins-dir`
  is ignored because `server` is imported before the plugin directories are set.
- S216-6 Medium, filesystem regression. `charts.py:84-115` replaced streaming with
  `read()` plus `splitlines()`, which splits on U+2028/U+0085; agent-log counts are
  corrupted and the streaming memory bound is gone. Reproduced by two reviewers.
- S216-7 Medium. R4's bug class on the Python side: `--show g1-notes.md` fails for a
  tracked file of that name (`show_cli.py:238`, `tree_source.py:213`). Three reviewers.
  Also Low: the browser tree renderer double-decodes display names on a pin
  (`static/app.js:1712-1842`).
- S216-8 Medium. `.jsonl` Git blobs up to 16 MiB are parsed synchronously on the event
  loop (`content_routes.py:1240`); the diff sidekick now runs filesystem calls on the loop.
- S216-9 Medium, decision. Spec 1B-b "bounded content-reader plugin calls" is checked, but
  `open_content()` raises on a pin; built-ins import private Git internals; the
  architecture doc names `resolve_content`/`stat_content`/`read_content_window`, which do
  not exist, and forbids the raw `ContentSource` that `content_source()` returns.
  Build the port or correct spec, docs, and parity map. Three reviewers.
- S216-10 Medium, parity. The only Git-pin golden is a one-file origin with an empty tree
  listing; no golden for rollup, catalog, KPress, plugin hooks, or the 404/409/413
  envelopes. Browser source-kind behaviour is checked by string greps. No DOM test sets a
  Git source kind on the link enhancer. No algorithmic regression test or recorded
  measurement for R5.
- S216-11 Low–Med. Pinned history `scope=all` walks `refs/metabrowser/subjects/*`; leasing
  another pin invalidates cursors (409) and leaks private refs.
- S216-12 Low, latent. `repository_store_lock` held across `await` (second concurrent
  lease raises `LockOrderError`); pool close race leaves an unowned `cat-file` actor; the
  pinned subject has two differently keyed identities with a colliding `"store"` default.
- S216-13 Low. Blobs over 16 MiB return 413 before classification; fixed 15 s batch
  deadline likely fails trees near 100k blobs (plausible); lexical symlink normalization;
  rollup names bypass display escaping; plugins read `window.METABROWSER_SOURCE_KIND`
  instead of the SDK; CHANGELOG contradiction and misplaced `sourceKind()` note; QA
  runbook names "stack 131" and a stale #209 head; spec 1B-c edge-case box is done but
  unchecked.

### #209 (`cursor/v011-html-trust-preview-bd04`)

- S209-1 Medium now, High once edit routes exist. `capabilities.py:103-118`,
  `cli/serve.py:200-208`: the dotenv chain loads from the opened directory and env enables
  beat `--untrusted`, so a cloned repo's `.env` can switch its own sandbox off.
- S209-2 High at integration. #216's `raw_file` returns `git_revision_raw(...)` before
  #209's per-return header wrapping; the merge conflicts on exactly those lines. Fix: a
  path-scoped header layer for `/raw`, which also covers 400/416 range errors, plus a wire
  test for an HTML blob under a Git subject.
- S209-3 Medium. No forced, non-overridable profile exists, which `mb-ew38` requires; #216
  pin entry points never call `apply_capabilities`, so `--untrusted` on a pin would be
  silently dropped after a merge.
- S209-4 Medium. HTML preview on a Git source 404s (`/raw/<path>` vs `?path=`), and
  per-segment path encoding breaks relative references.
- S209-5 Low. `Sec-Fetch-Site: none` now 403 with no CHANGELOG note; NUL in a `/raw/` path
  probably 500 (plausible); no golden for a non-default capability state; PR body names a
  stale head.
- Merge cost: nine conflicting files against the stack tip (`server.py`, `cli/main.py`,
  `show_cli.py`, `events_route.py`, `check_distribution.py`, CHANGELOG, three goldens).

### #134, #136, #139

- S134-1 Low, decide before freeze. `GitObjectId` accepts 41–63 hex
  (`hosted_review/models.py:29`, JS mirror) while #140/#216 require 40 or 64; validators
  do not require canonical serialization (`!!binary` and comments pass, several
  identities per record); no length bounds on `id`/`title`/`handle`; colon-joined ids are
  ambiguous if parsed; hard ordering rules on provider timestamps; oracle URL allowlist
  uses bare prefixes.
- S136-1 Med–Low. One broken third-party `metabrowser.capabilities.v1` entry point makes
  every built-in record fail validation, reported as a record defect, with discovery
  re-run per call (latent until Phase 3). The documented schema digest check is a no-op
  for built-ins. Duplicate inventory projections.
- S139-1 Medium, design. No rebind or tombstone path for a source whose repository is
  deleted and recreated; specify before Phase 3 storage (`mb-s0gv`, `mb-jlon`).
- Docs drift. `arch-repository-sources-and-provider-mirrors.md` status still "planned"
  with six unbuilt seams; `arch-external-resources-and-views.md` contradicts
  `arch-hosted-review-model.md` on bindings; `arch-git-and-comparison-sources.md` says the
  format is "designed only"; parity map lists nonexistent SDK operations; #134 PR body
  says 36 cases (61).

## Process and record

- Audit: `main`, #125, #134, #136, #139, and #219 lock anyio 4.14.1, which fails
  `make audit` today. Dependabot #207 fixes it and passes the cool-off.
- Record: #216 still carries "R5 remains pending … not a passing full gate"; #140 and #217
  say "not pushed or CI-verified yet"; four lower layers say verification is pending;
  promised final coverage records were never posted; dispositions name no tests and no R5
  measurement; #209 has no review of any kind; no approving review on any PR; no recorded
  `make verify` at any current head, and none on macOS.
- Beads: close `mb-r1f3`, `mb-5mrx`, `mb-vsze`, `mb-dznr`, `mb-wgm8`; re-scope or reopen
  `mb-30ox`, `mb-1qsn`, `mb-kicj`, `mb-vknc`, `mb-fbm2`; correct `mb-dxmb`, `mb-k900`,
  `mb-n2ro` (notes and eight labels), `mb-xada`, `mb-z335`, `mb-hoae`, `mb-rldx` notes.
  Missing owners: three Phase 1B-a items, https/ssh acquisition, #219 unfork, the
  #209-versus-stack conflict.
- Graph: `mb-n2ro` is blocked by all nine future-phase publication beads, so the current
  stack cannot land before the whole roadmap; `mb-ew38`'s #209 gate is only transitive;
  `mb-lnkl`/`mb-bue2` invert 3C-before-4A; `mb-dxmb` ↔ `mb-k900` is circular.
- Workspace: stale worktree registration `metabrowser-v011-phase0d` blocks a whole-stack
  rebase; `gh stack` metadata is two commits behind on #216; `feat/git-graph-view` (179
  commits) and `pr13-folder-treemap` (6) are unpushed; `claude/v011-cache-measurements` is
  already contained in #140; `.pnpm-store/` is unignored.

## Resume state (paused 2026-09-20 on user request; resume about 45 minutes later)

Done: #207 merged (main locks anyio 4.14.2); stale `metabrowser-v011-phase0d` worktree
registration removed; 38 finding beads filed under this bead; user decisions recorded on
mb-0um4 (build the bounded content reader), mb-maws (#209 lands before #217; merge still
needs explicit approval), mb-v4dh (split the mb-n2ro blocker set). User also approved
pushing fixes to PR branches and posting corrective PR comments.

Ten fix agents were STOPPED mid-work. Their isolated worktrees persist under
`.claude/worktrees/agent-*` with uncommitted partial edits; briefs are
`scratchpad/fix-brief.md` plus the per-agent prompts in the session. Intended branches:
stab/s140, stab/s217 (cherry-pick ad6e30f8 first), stab/s216-core, stab/s216-cli,
stab/s209, stab/s209-raw, stab/s134 (+ stab/s136-format, stab/s139-format,
stab/s139-rebind), stab/s136, stab/docs. The bead-bookkeeping agent had applied nothing.
On resume: inspect each worktree (`git status`, `git log`), then relaunch each agent
pointing at its existing worktree to continue, rather than starting over.

Then: review diffs; integrate bottom-up (#140, #217, #216); restack onto main; add the
multi-entry Git-pin golden (mb-3z4d); `make verify` on macOS; push; watch CI; build the
content reader (mb-0um4); apply bookkeeping (mb-v4dh); post dispositions (mb-9ajn); ask
for approval to merge #209, then second restack and integration (mb-gqmt, mb-99ub,
mb-g5je, mb-rlt4).

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
