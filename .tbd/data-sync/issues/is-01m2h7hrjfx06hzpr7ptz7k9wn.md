---
type: is
id: is-01m2h7hrjfx06hzpr7ptz7k9wn
title: "GitHub pull-request list for a mirrored repository: bounded list data from gh"
kind: feature
status: in_progress
priority: 1
version: 27
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m2h7jjgpzyfbf10238j32z6q
  - type: blocks
    target: is-01m2kw2cf1gxnanj6e1wyh6frw
parent_id: is-01m6f39t9zax1nbajkkasya6st
child_order_hints:
  - is-01m6f3a2xknb6bzh2m26w2zema
  - is-01m6f3a3c2fsrz21ph82xrc6yg
  - is-01m6f3a3v2ny6852knvbqn6pmt
  - is-01m6f3a4ab0xx86kma2fv9t9cy
  - is-01m6f3a4rcc45rvvzgy17a392p
  - is-01m6f9zg2thrbwm74y2hn6eeqq
hold: null
hold_until: null
created_at: 2026-09-15T00:30:26.382Z
updated_at: 2026-11-03T07:25:50.209Z
started_at: 2026-09-16T21:10:44.906Z
---
Publish a bounded query-keyed ChangeRequestIndex after direct PR hydration works. Keep rows summary-only and record normalized query identity, deterministic ordering, per-page provenance, observation window and remote consistency, dedupe, bounds, cursors, and honest coverage. Store one repository/auth-scoped index reused by all attached clones and managed URL sources; listing fetches no Git refs. Cover continuation, moving pages, reauth isolation, stale/offline state, missing direct item, and no-ref-fetch.

## Notes

2026-11-03 HANDOFF (paused for another agent): #279 head fff4d499 (pin_changed fix e8b7ff3d merged forward); reviews A, B, C addressed. Awaiting the owner's merge, after stack 278. Open question for the owner in the PR body (whether a first GET of the list should fetch). When 278 merges, stack 286 must be unstacked, #279 retargeted to main, and relinked.

2026-11-03 status: PR #279, layer 1 of stack 286, base claude/v012-overlay-acquisition, head 1cb84734, CI 9 of 9 green, mergeable. Reviews A, B, C addressed (mb-r5me, mb-u0gx closed). Since then only forward merges of the stack below (#280 454a509e, then f7cf3464 and 2a22035b). Children stay in progress until the owner merges. Open question for the owner in the PR body: whether a first GET of the list should fetch when nothing is cached.

2026-11-02: step 1 built on claude/pulls-1-list-data, PR https://github.com/jlevy/metabrowser/pull/279 (head 1108bd99). Checkpoint verified against pallets/markupsafe and offline with a failing gh; the GET alone reads the cache, so a POST pulls-refresh comes first (asked in the PR). Open until it merges.

2026-11-02: reopened by the user's decision to build the Pulls tab now, above the v0.12 stack. The plan spec is the authority; this bead's older text is background. Its older blockers are all closed. This is Delivery step 1.

2026-10-01: the design is now the plan spec docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md (mb-qftx, commit 245f296c on codex/v012-landing-docs); it supersedes the notes below where they differ, and its Open Decisions section lists what the user decides first.

2026-10-01, decided by the user: 'we can land the stack first then continue a new stack with the pulls tab' and 'let's stabilize everything else but not implement the pulls tab yet, just make sure we've planned it well'. So: no implementation before the v0.12 stack lands; the plan spec (mb-qftx) is written now; the work starts afterwards as a new stack.

2026-10-01, re-planned for the thin mirror at the user's request ('when I open a repo can I get a list of all the PRs? could Pulls be a new tab alongside the git tab?'). Not started; the user decides whether it goes before or after the v0.12 landing (the coordinator recommends after, as three PRs merged to main one at a time). The earlier description below predates the thin mirror; its provider store, auth-scoped index, RepositoryActivity projection and public nav-panel SDK are retired.

Thin-mirror design for the list data. One request per 100 pull requests with 'gh api repos/<owner>/<repo>/pulls?state=<open|closed|all>&per_page=100&page=<n>' through the existing gh runner (callers name every page; no --paginate); summary rows only (number, title, state, draft, author login, updated time, base and head labels), validated by a Pydantic model and bounded per row and per file; kept as one JSON file beside the per-PR records (cache/sources/<slug>/pulls/index.json or one file per state), with the fetch time, the reader and what was fetched (state, pages), written with the existing private atomic write and a schema integer (a mismatch refetches). Honest bounds: open first; more pages on demand; the count shown is what was fetched, with 'more on GitHub' when the last page was full. Refresh in the background like the mirror (stale-while-revalidate, joined through the refresh coordinator, typed failures from the gh runner: gh missing, signed out, rate limited). Listing fetches no Git refs. Parity: a route under /api/plugin/github/ reachable with 'metab <repo-url> --api', an in-process golden with the fake gh, and no record or list ever carrying a credential.

2026-09-30: deferred by the user's 2026-09-23 decision (thin-mirror plan, Decisions). Not part of v0.12; does not gate mb-n2ro. The design text predates the thin mirror (provider store, auth contexts, leases and SDK panels are retired); re-plan against the thin-mirror plan before starting.
