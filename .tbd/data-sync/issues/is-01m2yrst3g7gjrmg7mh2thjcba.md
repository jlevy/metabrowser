---
type: is
id: is-01m2yrst3g7gjrmg7mh2thjcba
title: Review and reconcile complete PR 216 stack
kind: task
status: in_progress
priority: 1
version: 10
delegate: claude-code@spud10.local
labels: []
dependencies: []
child_order_hints:
  - is-01m2yry572407yerkvvmq14ac7
  - is-01m2yry6ccp30qxzhpjp55e6g2
  - is-01m2yry790wac45xk89eb9k8m4
  - is-01m2yry8v89w650w87p8h510dk
  - is-01m2yrya4k647b005qb2n30n0y
  - is-01m2yrybwx5zatf3w9chdnfew6
  - is-01m2yryd6had8zdvj8eag4a4v4
hold: null
hold_until: null
created_at: 2026-09-20T06:42:03.501Z
updated_at: 2026-09-20T07:08:53.747Z
started_at: 2026-09-20T06:42:30.840Z
---
Review coverage and all review channels for stack PRs 125, 134, 136, 139, 140, 217, 216; publish per-layer senior reviews; use address-pr-review for every finding; fix on owning layers, restack, verify and watch CI; publish disposition comments. Preserve existing unrelated workspace changes.

## Notes

# PR 216 stack review handoff

The user requested a full senior engineering review of the entire stack ending at
[PR 216](https://github.com/jlevy/metabrowser/pull/216), including previously unreviewed
code, all-channel review reconciliation, the `address-pr-review` shortcut, published
review/disposition comments, and beads for all work.
The user then requested this handoff.
Work is unfinished: known Git/browser findings still need implementation, not just final
checks. Do not merge the stack to main.

## Current checkout and local work

- Current branch: `cursor/v011-git-revision-pin-bd04` (#216), local head
  `dbf50ebcb352675285b5b9af82a0cbb88ff0ee20`, based on local #217.
- #140 has local commit `da73b878c5ec72370a21efd2a6d46cf9d2fb403c`:
  `fix(cache): refuse unknown layouts before mutations`.
- #217 has local commit `70091d81`:
  `fix(cache): isolate acquisition and report selected store state`.
- Both fixes were propagated upward using `gh stack rebase --upstack --no-trunk`. None
  of these code changes or rebased branches has been pushed.
  Remote CI still describes the old heads.
  No new finding bead has been closed.
- Uncommitted changes in `tests/test_git_tree_source.py` and
  `tests/test_git_revision_content_routes.py` are intentional failing regressions for
  #216 R1–R3. Latest focused run: four failures, as expected; no implementation fixes
  for these findings have been applied.
  A backup is `/tmp/mb216-review/uncommitted-regressions.patch`.
- Preserve the preexisting `.tbd/config.yml` additions (two generated docs-cache
  entries) and untracked `.pnpm-store/`. The config edit was stashed for restacking;
  `tbd sync` regenerated the identical edit in the working tree.
  Our named stash `review216-preserve-preexisting-tbd-config` remains as a backup.
  Do not touch the older unrelated stashes.
- #140 is checked out in the sibling `metabrowser-v011-phase1a` worktree.
  It was clean before this work, fast-forwarded to published `e5cfabad` (the AnyIO
  update), and now contains our committed fix.
  Do not discard that dependency update.

## Tracking and published reviews

Parent: `mb-rldx` (in progress).
Its child coverage beads are:

| PR | Coverage bead | Review state |
| --- | --- | --- |
| 125 | mb-r1f3 | Prior architecture/contract/delivery reviews reconciled; no unanswered findings |
| 134 | mb-5mrx | Folded 130/132/133 reviews and oracle R1–R8 dispositions reconciled |
| 136 | mb-vsze | Folded 135 and final R1–R14 dispositions reconciled |
| 139 | mb-a63g | New review of Python/browser/schema observation and source-binding changes; no finding |
| 140 | mb-6jb5 | Cache-safety review and two existing Bugbot findings; fixes committed |
| 217 | mb-u2b0 | Acquisition/CLI review; three findings fixed locally |
| 216 | mb-hj2d | Source/Git/browser review in progress; five known findings remain |

Posted review and coverage comments:

- [125 coverage](https://github.com/jlevy/metabrowser/pull/125#issuecomment-5748280103)
- [134 coverage](https://github.com/jlevy/metabrowser/pull/134#issuecomment-5748280197)
- [136 coverage](https://github.com/jlevy/metabrowser/pull/136#issuecomment-5748280295)
- [139 review](https://github.com/jlevy/metabrowser/pull/139#issuecomment-5748280394)
- [140 findings](https://github.com/jlevy/metabrowser/pull/140#issuecomment-5748239121)
- [217 findings](https://github.com/jlevy/metabrowser/pull/217#issuecomment-5748256501)
- [216 first findings](https://github.com/jlevy/metabrowser/pull/216#issuecomment-5748256595)

The comments explicitly say final verification is pending.
No disposition comments or Bugbot thread resolutions have been published yet.
#216 R5 and #140 R3 below are tracked but have not yet been added to PR review comments.

## Findings and exact disposition state

### PR 140

- R1, existing Bugbot comment 4041640457, `mb-fn3h`: nonempty durable cache without a
  layout was mutated by `open_cache` before refusal.
  Fixed in `da73b878` with a shared nonmutating preflight, retaining the locked
  missing-layout check.
- R2, existing Bugbot comment 4041640465, `mb-w6oa`: direct `migrate_layout` acquired a
  lock/repaired permissions before rejecting future formats.
  Fixed in the same commit.
  Tests cover both entry points, unprepared future config, shared future layout, and all
  five durable directories.
  Layout suite: 53 passed; format and lint-check passed.
  Full final gate still required.
- R3, Low, `mb-6m25`: PR body names obsolete cache routes `entries` and `entry/{slug}`.
  Update it to actual registered `layout`, `sources`, `sources/{slug}`, and `stores`. No
  body update yet.

Review of layout, atomic publication, locks, reclamation, descriptor checks, ACL
handling, and projection bounds was performed.
Some large tool outputs were truncated; finish focused review of any remaining
home/projection sections before claiming exhaustive coverage.
No additional confirmed cache defect so far.

### PR 217

- R1, High, `mb-f44p`: SHA-256 origins failed because staging used default SHA-1 init.
  Fixed in `70091d81`: validate advertised full HEAD OID and initialize its hash format.
- R2, High, `mb-1ss2`: isolated Git policies retained environment config injection.
  Fixed: scrub `GIT_CONFIG` and `GIT_CONFIG_*`, then apply deliberate policy config.
  Real Git tests cover COUNT/key/value, PARAMETERS, and config-file injection and prove
  ordinary READ_POLICY still honors caller configuration.
- R3, High, `mb-gzl3`: racing acquisitions could return losing staged HEAD even when
  using the first published store.
  Reproduced with two live stages around a remote commit.
  Fixed: read selected store/state metadata under the store lock when attaching.
- All five new regression cases failed before fixes.
  Acquisition, process, CLI, and acquisition golden tests afterward: 44 passed, one
  platform/permission skip.
  `make format` and `make lint-check` passed on the layer.
  No full final gate or push.

### PR 216: implementation remains

- R1, High, `mb-fd2g`: `_list_tree_oid` caches path-bearing entries only by tree OID.
  Identical `one/file.txt` and `two/file.txt` trees make the second lookup return
  missing. New failing test alternates reads, listings, and synchronous lookup.
  Suggested fix: cache relative entries and reparent on each lookup, retaining
  deduplication by OID.
- R2, Medium, `mb-7988`: `_git_symlink_target` clamps `..` at root.
  Root `../README.md` and nested `../../README.md` incorrectly resolve to in-tree
  content. Reject parent traversal when already at root.
  Failing endpoint checks were added to the existing symlink test for file/raw/KPress;
  verify the KPress endpoint spelling as well.
- R3, High, `mb-z15f`: `_BatchObjectReader.info_many` and `_transact` do not enforce
  `BATCH_OBJECT_POLICY.timeout_s`. Wrap transactions in an async deadline, poison/reap
  on timeout, and raise `GitTimeoutError`. New tests stall `_read_header`, apply a short
  policy deadline, require process cleanup, and prove the next read recovers.
  Both currently fail via the outer two-second test deadline.
  Existing cleanup paths already poison on cancellation/framing exceptions.
  Consider the 900-second ACQUISITION_POLICY used for ordinary store reads when
  reviewing timeout semantics.
- R4, Medium, `mb-web5`: browser navigation and Markdown/wiki resolvers infer Git
  identity from `g1-*` filename shape.
  Legal filesystem filenames collide.
  Carry an explicit source kind, not shape inference.
  The shell already injects `METABROWSER_SOURCE_KIND` (`filesystem` or `git_revision`).
  Core navigation can use that directly.
  Plugins must use the public SDK: an additive `sourceKind` property can feed an
  optional typed intent field into pure resolvers.
  Inspect `link-enhancer.js`, `wiki-enhancer.js`, `links.js`, `wiki-resolver.js`, and
  `reconciliation-coordinator.js`; update exact production-JS fixtures/goldens and SDK
  docs. No code/test change for R4 yet.
- R5, High, `mb-0iz9`: `GitBlobIndex.tally` and `_git_filtered_tally` scan all blobs per
  directory; rollup invokes the former for every new directory.
  Measured synthetic single-file directory cases: 1,000 / 2,000 / 4,000 at 0.179 / 0.778
  / 1.852 seconds. This synchronous request work grows quadratically.
  A possible fix is a sorted byte-name index with bisected subtree ranges, reused by
  unfiltered and filtered tally paths.
  Preserve exact prefix boundaries (`a`, `a/`, `a-b`, non-UTF-8 names), unknown sizes,
  ordering, and nontrivial nested totals.
  Add deterministic algorithmic coverage and remeasure.
  No implementation/test yet; publish this review finding.

## Remaining review and validation

The entire stack has NOT completed this session’s final senior review.
The lower layers have substantive prior reviews with complete disposition maps.
#139 received a new pass.
#216 source/session, lease, CLI, Git tree/content routes, history/diff changes, and
several sidekick/browser changes were inspected, but finish the browser/plugin
integration, resource lifecycle, CLI/parity, and documentation passes.
Some large diffs were truncated in tool output; do not treat them as fully read.
In particular inspect binary/structured/diff sidekick limits, chart/JSONL byte paths,
source replacement, Git history cursor identity, and route error behavior.
Avoid speculative findings: reproduce suspected defects and track each separately.

The initial `make verify` at original tip `912e720f` passed lint/type/format, then
finished with 2,868 tests passed, two skipped, and one failure:
`test_rollup_budget_on_synthetic_large_index` took 1,936 ms versus its 1,000 ms limit.
The isolated rerun passed at 57.6 ms.
Do not weaken the threshold.
Full verification has not passed; later audit/distribution/smoke stages were not reached
in that run. Run `make verify` on the final combined code and watch every affected PR’s
CI to a terminal result after pushing.
Golden/parity requirements apply to functional changes, not just newly added routes.

Use `tbd shortcut address-pr-review` for all dispositions.
Fix on owning layers, restack, review the final diffs, then push and publish per-finding
commit/test maps. Reply to and resolve both #140 Bugbot inline threads only after
validating the fixes.
Re-sweep all review channels for new comments.
Update PR bodies and stack pointers where stale.
Close only fully resolved beads and sync; retain existing landing hold `mb-n2ro`.
Existing handoff `mb-xada` describes broader future implementation and is not superseded
wholesale by this review handoff.

## Non-obvious tool and stack details

- The primary checkout has the useful `gh-stack` metadata.
  The #140 sibling checkout says its branch is not part of a stack.
  Run stack operations from the primary checkout.
- Positional branch arguments did not select the starting layer for `--upstack`.
  Checking out #217 and running `gh stack rebase --upstack --no-trunk` correctly
  propagated #140 to #217/#216. Repeating from #217 after its fix also succeeded.
- A whole-stack rebase failed at the stale/prunable #139 worktree registration and
  restored branches. Avoid disturbing unrelated worktrees; resolve this deliberately if
  `gh stack sync` needs the whole chain.
  The two targeted upstack rebases succeeded.
  The local main ancestry check was successful before the last restack; fetch before
  deciding whether new trunk commits require another rebase.
- Rebase of #216 replays many commits and takes time.
  Transient staged files/lockfile changes appeared during replay and disappeared at
  completion. Do not edit mid-rebase.
- Shell startup in the sibling worktree prints an unrelated missing-Java warning;
  `login: false` avoids it.
  No Java dependency is needed.
- Sandbox escalation is needed for Git writes, GitHub/network, tbd writes, and uv cache
  access. Automatic approval allowed all requested operations; there was no rejection.
- Use repository Make targets and uv with `--config-file uv.toml --frozen`. The host has
  global uv config that can contaminate locks if the explicit project config is omitted.
- No review subagents were used.
  An optional request for authorization got no answer; current developer instructions
  forbid spawning without explicit authorization.
- Audit material and command logs are in `/tmp/mb216-review/`: PR metadata and review
  channels for all seven PRs and their folded predecessors, Bugbot thread IDs in
  `threads-140.json`, initial and focused test logs, review comment bodies, and the
  regression patch backup.
  The GitHub comments and synced beads are the durable record.

Active specs: `docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md` and
`plan-2026-08-27-github-provider-and-pull-requests.md`. Architecture and parity map:
`docs/project/architecture/arch-repository-sources-and-provider-mirrors.md` and
`arch-views-models-routes.md`.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
