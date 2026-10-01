---
type: is
id: is-01m2h7hrjfx06hzpr7ptz7k9wn
title: "GitHub pull-request list for a mirrored repository: bounded list data from gh"
kind: feature
status: deferred
priority: 1
version: 13
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
delegate: null
labels: []
dependencies:
  - type: blocks
    target: is-01m2h7jjgpzyfbf10238j32z6q
  - type: blocks
    target: is-01m2kw2cf1gxnanj6e1wyh6frw
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
hold: null
hold_until: null
created_at: 2026-09-15T00:30:26.382Z
updated_at: 2026-10-01T19:38:41.279Z
started_at: 2026-09-16T21:10:44.906Z
---
Publish a bounded query-keyed ChangeRequestIndex after direct PR hydration works. Keep rows summary-only and record normalized query identity, deterministic ordering, per-page provenance, observation window and remote consistency, dedupe, bounds, cursors, and honest coverage. Store one repository/auth-scoped index reused by all attached clones and managed URL sources; listing fetches no Git refs. Cover continuation, moving pages, reauth isolation, stale/offline state, missing direct item, and no-ref-fetch.

## Notes

2026-10-01, re-planned for the thin mirror at the user's request ('when I open a repo can I get a list of all the PRs? could Pulls be a new tab alongside the git tab?'). Not started; the user decides whether it goes before or after the v0.12 landing (the coordinator recommends after, as three PRs merged to main one at a time). The earlier description below predates the thin mirror; its provider store, auth-scoped index, RepositoryActivity projection and public nav-panel SDK are retired.

Thin-mirror design for the list data. One request per 100 pull requests with 'gh api repos/<owner>/<repo>/pulls?state=<open|closed|all>&per_page=100&page=<n>' through the existing gh runner (callers name every page; no --paginate); summary rows only (number, title, state, draft, author login, updated time, base and head labels), validated by a Pydantic model and bounded per row and per file; kept as one JSON file beside the per-PR records (cache/sources/<slug>/pulls/index.json or one file per state), with the fetch time, the reader and what was fetched (state, pages), written with the existing private atomic write and a schema integer (a mismatch refetches). Honest bounds: open first; more pages on demand; the count shown is what was fetched, with 'more on GitHub' when the last page was full. Refresh in the background like the mirror (stale-while-revalidate, joined through the refresh coordinator, typed failures from the gh runner: gh missing, signed out, rate limited). Listing fetches no Git refs. Parity: a route under /api/plugin/github/ reachable with 'metab <repo-url> --api', an in-process golden with the fake gh, and no record or list ever carrying a credential.

2026-09-30: deferred by the user's 2026-09-23 decision (thin-mirror plan, Decisions). Not part of v0.12; does not gate mb-n2ro. The design text predates the thin mirror (provider store, auth contexts, leases and SDK panels are retired); re-plan against the thin-mirror plan before starting.
