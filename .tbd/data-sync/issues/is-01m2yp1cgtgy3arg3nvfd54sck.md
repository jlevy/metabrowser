---
type: is
id: is-01m2yp1cgtgy3arg3nvfd54sck
title: "Agent handoff: v0.11 stack 2026-09-19"
kind: task
status: in_progress
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-20T05:53:46.008Z
updated_at: 2026-09-23T00:40:30.771Z
started_at: 2026-09-23T00:40:30.765Z
---
Task: Finish v0.11 review organization and keep the next agent oriented across tbd and metabrowser. Do not merge anything to main unless the user asks.

## Two-repo split

- **tbd** owns the written PR-sizing / stack-shape rule.
- **metabrowser** implements Repository Library + Hosted Review on GitHub stack #218, plus a parallel HTML-trust PR. Do not copy the PR policy into metabrowser `AGENTS.md`.

## PRs (lead with these)

### tbd

- https://github.com/jlevy/tbd/pull/316 — `docs/reviewable-pr-units` → `main`, ready, CI green.
  Head `e14eb1bb` (local `a0dca540` is the same tree, diverged hash only). Isolated docs change. Do not merge unless asked.

### metabrowser stack #218

https://github.com/jlevy/metabrowser/stack/218

```
main
 └── #125  Design (ready)
  └── #134  Phase 0 format/oracle (ready; folded #130 #132 #133)
   └── #136  Phase 0C inventories (ready; folded #135)
    └── #139  Phase 0D sources/bindings (ready; folded #138)
     └── #140  Phase 1A cache format (ready)
      └── #217  Phase 1B-a file:// acquire (draft; folded #208 #210)
       └── #216  Phase 1B leased pin (draft; folded #156 and #211–#215)
```

| PR | URL | Base → head | Draft | CI (last seen) |
| --- | --- | --- | --- | --- |
| #125 | https://github.com/jlevy/metabrowser/pull/125 | `main` → `codex/v011-hosted-review-design` @ `fde1d9b4` | ready | green |
| #134 | https://github.com/jlevy/metabrowser/pull/134 | design → `codex/v011-hosted-review-phase0b3` @ `18ef513a` | ready | green |
| #136 | https://github.com/jlevy/metabrowser/pull/136 | 0b3 → `codex/v011-hosted-review-phase0c2` @ `b907bb27` | ready | green |
| #139 | https://github.com/jlevy/metabrowser/pull/139 | 0c2 → `claude/v011-hosted-review-phase0d` @ `01584dba` | ready | green |
| #140 | https://github.com/jlevy/metabrowser/pull/140 | 0d → `claude/v011-cache-format-foundation` @ `18ec8870` (comment also cites later anyio `e5cfabad`) | ready | green; Bugbot Neutral + 2 unresolved Mediums |
| #217 | https://github.com/jlevy/metabrowser/pull/217 | 1A → `cursor/v011-cache-acquire-cli-bd04` @ `b09c01e0` | draft | green |
| #216 | https://github.com/jlevy/metabrowser/pull/216 | 1B-a → `cursor/v011-git-revision-pin-bd04` | draft | green at `cd33e023`; spec-status commit may be on tip |

### Independent metabrowser PRs (not in #218)

- https://github.com/jlevy/metabrowser/pull/209 — HTML trust (draft, base `main`). Parallel, required before HTTP-serving acquired Git.
- https://github.com/jlevy/metabrowser/pull/219 — temporary `docs/tbd` fork of reviewable-unit shortcuts until get-tbd ships. Lint fails on anyio 4.14.1 audit.
- https://github.com/jlevy/metabrowser/pull/207 — dependabot anyio 4.14.2. Overlaps #209 lock bump and #219 lint.
- https://github.com/jlevy/metabrowser/pull/87 and https://github.com/jlevy/metabrowser/pull/51 — research, independent.

Folded crumbs are closed: #130 #132 #133 #135 #138 #156 #208 #210 #211–#215.

## What was reorganized

v0.11 work was folded into phase survivors and linked as stack #218. History was not rewritten. Too-narrow PRs were closed with pointer comments. Do not restack unless a PR is missing or mis-based. Do not land on main.

## Canonical PR-sizing policy (tbd #316)

Source: `tbd shortcut stacked-prs` Reviewable Units + Layer Discipline.

- A PR is a review unit: accept or reject without reading parent or child; otherwise fold.
- Focused isolated work stays a standalone PR of any size.
- Spec/bead-driven work consolidates into larger PRs, then one formal stack per major feature or phase.
- Beads are not PRs. Lettered headings (`0A`, `0B.1`) are not PR boundaries.
- `--base` on another feature branch is a stack; declare it with `gh stack`.
- Prefer fewer larger layers. Typically 8 PRs or fewer per stack.
- Two-level review: each PR, then the stack. Agents, then a human.
- Do not land a stack on trunk unless asked. Use `gh stack merge`, not `gh pr merge`.

Metabrowser overlay: #219 forks those shortcuts into `docs/tbd/`. Not in `AGENTS.md`. Unfork after get-tbd ships.

## Plan specs (refreshed 2026-09-19 on the open branches)

- `docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md` — status now names stack #218; Phase 0/1A done on ready layers; 1B-a/1B-b/1B-c partially checked against #217/#216; 2A+ unchecked.
- `docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md` — Phase 0–0D done on #218; Phase 1A cache items checked; generic https acquire and Git-tree goldens still unchecked; Phase 2+ not started.
- `docs/project/specs/active/plan-2026-08-06-html-rendering-and-trust-model.md` — on #209 only. Phases 1–4 checked. Status says draft #209, not main, not stack #218.

## Beads after this handoff

### metabrowser

| ID | State | Role |
| --- | --- | --- |
| mb-k7zy | in_progress | Epic / roadmap |
| mb-n2ro | in_progress, **hold blocked** | Sole landing owner. Do not merge without explicit approval |
| mb-x8x0 | closed | Restack to #218 |
| mb-109m | closed | Points at tbd #316 and metabrowser #219 |
| mb-h51g | in_progress | 1B-a remaining checklist (see spec) |
| mb-k900 | in_progress | Review/publish #217 |
| mb-dg00 | in_progress | Remaining acquire goldens |
| mb-3bna | in_progress | Source boundary; work is on #216 |
| mb-tsdc | in_progress | Review source boundary inside #216 |
| mb-z335 | in_progress | Git pin; work is on #216; some edge tests still open |
| mb-hoae | in_progress | Review Git pin inside #216 |
| mb-fn3h | open | #140 Bugbot: missing layout still mutated first |
| mb-w6oa | open | #140 Bugbot: migrate_layout writes before format refusal |
| mb-d658 | in_progress | HTML publication/review; impl is #209 |
| mb-wyd4 | open | HTML epic |
| mb-ew38, mb-12cz, mb-innz, mb-jlon, mb-2xq7, later hosted-review beads | open | Not started |

Closed citing survivor PRs: mb-kf4w, mb-t7l7, mb-h5jw, mb-u2x2, mb-y561, mb-5edg, mb-hodu, mb-3639, mb-1i98 → #217; mb-cun0, mb-vib1, mb-nk32, mb-4x15 → #209.

### tbd

| ID | State | Role |
| --- | --- | --- |
| tbd-njm1 | closed | Encoded in #316 |

## Remaining implementation gaps

Honest vs the stacked diffs, not the titles.

### On ready stack layers

- **#125:** design only. 2 commits behind `origin/main` (`#137` tbd 0.9.0). Stack internally consistent (`needsRebase: false`). Do not rebase unless asked.
- **#134 / #136 / #139:** Hosted Review Phase 0 format, inventories, source-binding. Implemented. Ready for PR-level review.
- **#140 Phase 1A:** owner-only home, f01 records, locks, cache routes. Two unresolved Bugbot Mediums (`mb-fn3h`, `mb-w6oa`) in `src/metabrowser/cache/layout.py`.

### On draft #217 (Phase 1B-a)

Implements file:// classify → worktree-free acquire → publish store then alias → prefetch default tree → `--no-serve` / cache-inspect `--api`. Goldens: `cli-cache-acquire`, `orphan-reclaim`, `readonly-hit`, `recover`. https/ssh refused. Does not serve.

Still not on any branch (spec Phase 1B-a):

- Not-yet-converged blob read online and offline
- No-lazy-fetch acceptance against the lowest admitted Git in CI
- Measured initial-acquisition stall bound (object-fetch already uses 1000/30)
- Distribution-backport policy (Ubuntu/Debian version-string lie)
- Remaining `mb-dg00` goldens (interrupt before store, between store and alias, CAS ref, URL grammar, isolated fetch failures, unsupported-Git and repair-guidance goldens)
- Force untrusted profile for URL-opened roots (needs #209 + serving)

### On draft #216 (Phase 1B source + pin)

Implements `RepositorySubject` / `SourceSession`, `GitPath` / `GitRevisionSubject`, batch readers, maintenance locks, `metab file://… --show` and non-cache `--api`. Folds #156. ~101 files / +10k. Large review.

Still missing:

- HTTP `--walk` / `--check-api` / serve of acquired Git (`mb-ew38`)
- Focused tests for symlink, gitlink, LFS-pointer, oversized-blob, promisor-miss
- Independent publication reviews (`mb-tsdc`, `mb-hoae`)
- https/ssh open and provider URL reducers (`mb-12cz`, Phase 2A)

### Not on any open branch (later spec phases)

- Phase 2A URL open and web-URL reduction
- Phase 2B provider jobs / selected refs
- Phase 2C selected branch
- Hosted Review Phase 3 `gh` adapter, binding, PR bundle/index
- Hosted Review Phase 4 views / virtual nav / anchors
- Phase 5 issues, Phase 6 stacks, hosted releases, GitLab
- Catalog, chooser, measured large-repository support

### HTML #209 (parallel)

Implements spec Phases 1–4 on `main`. Not in stack #218. Required before serving fetched Git; not required for `--show` / `--api`. Lock-only anyio 4.14.2 overlaps #207. `mb-d658` still owns publication before URL-open serving.

## Review order

1. PR-level: #316 (tbd, isolated), then stack bottom-up #125 → #134 → #136 → #139 → #140 (include Bugbot) → #217 → #216. Review #209 on its own.
2. Stack-level: walk #218 as one story after the layers.
3. Do not merge to main unless the user asks. Landing owner is `mb-n2ro` (`hold: blocked`).

## Risks

- **#140 Bugbot:** two Mediums can write a home before refusing a future/missing layout.
- **#125 vs main:** tbd 0.9.0 (`#137`) is on main and not in the stack. Rebase is a full restack.
- **#216 size:** one reviewable unit by policy, but a long review.
- **#207 / #209 / #219 anyio:** three PRs touch the same advisory. #219 lint is the audit failure on 4.14.1.
- **tbd pre-push:** Lefthook runs full `pnpm test`; 5s timeout flakes happened before. #316 already pushed; do not `--no-verify` unless retries prove unrelated flake.
- **Drafts:** #217 and #216 are still drafts. Ready layers are not landed.

## Commands

```bash
# metabrowser
cd /Users/levy/wrk/github/metabrowser
gh stack view --json
gh pr view 125 && gh pr view 216 && gh pr view 209
tbd prime
tbd show mb-k7zy mb-n2ro mb-h51g mb-k900 mb-dg00 mb-3bna mb-z335 mb-fn3h mb-w6oa mb-d658

# specs on the stack tip / #209
# plan-2026-08-11-open-repo-from-git-url.md
# plan-2026-08-27-github-provider-and-pull-requests.md
# plan-2026-08-06-html-rendering-and-trust-model.md  (#209 only)

# tbd
cd /Users/levy/wrk/github/tbd
gh pr view 316
tbd prime
tbd show tbd-njm1
```

## Notes

Spec-status commits are on the open PRs, not main:

- #216 https://github.com/jlevy/metabrowser/pull/216 tip 912e720f (repo-library + hosted-review plan status)
- #209 https://github.com/jlevy/metabrowser/pull/209 tip 398cedd4 (HTML plan status)

tbd policy: https://github.com/jlevy/tbd/pull/316
Metabrowser stack: https://github.com/jlevy/metabrowser/stack/218

Superseded in part 2026-09-20 (all PR facts re-verified with gh on 2026-09-20):

- Heads are now #140 da73b878, #217 70091d81, #216 de0f4f5a.
- Both #140 Bugbot Medium threads are resolved (GraphQL reviewThreads isResolved=true);
  mb-fn3h and mb-w6oa are closed.
- tbd PR https://github.com/jlevy/tbd/pull/316 is MERGED (mergedAt 2026-09-20T06:17:47Z).
- dependabot PR #207 is MERGED (mergedAt 2026-09-20T15:26:53Z); origin/main now locks
  anyio 4.14.2 (uv.lock).
- Current stabilization work is tracked in mb-gacf.
