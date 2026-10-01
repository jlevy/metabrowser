---
type: is
id: is-01m2h7jjgpzyfbf10238j32z6q
title: "GitHub Pulls tab: list a mirrored repository's pull requests and open any of them"
kind: feature
status: deferred
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels: []
dependencies:
  - type: blocks
    target: is-01m2kttf7tse7rs1nwrk9m3jbj
  - type: blocks
    target: is-01m2kw2d2arc9hn25pfsc4me50
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-09-15T00:30:52.949Z
updated_at: 2026-10-01T19:54:27.465Z
---
Add the Pull Requests repository-scoped nav panel after direct view and the bounded index. Project only the index row fields—no review/check summary—through RepositoryActivity and reuse bounded paging, virtualization, roving selection, query-key restoration, loading/error, root replacement, and disposal through public SDK. Selection opens the direct PR address; expansion exposes comparison files. Counts/grouping/visibility come from the bounded model. Execute exact panel-window, selection, restoration, replacement, and disposal owners in hosted-review-session and cli-ui-hosted-review.

## Notes

2026-10-01, decided by the user: 'we can land the stack first then continue a new stack with the pulls tab' and 'let's stabilize everything else but not implement the pulls tab yet, just make sure we've planned it well'. So: no implementation before the v0.12 stack lands; the plan spec (mb-qftx) is written now; the work starts afterwards as a new stack.

2026-10-01, the user's additions: (a) 'when you open a github repo that would automatically appear, if we know we have the right setup'. Design: the tab appears, like the Git tab, once the shell knows the root is a Git repository whose origin is on github.com (learned after first paint from the repository route, no startup cost); the gh check (installed, version, signed in) runs lazily when the tab is first opened, and a missing or signed-out gh is shown in the tab with what to do, not by hiding the tab. The import-boundary and 'a plain folder starts no gh' tests must keep passing. (b) the same views on an existing checkout: see mb-cbak.

2026-10-01, re-planned for the thin mirror at the user's request ('when I open a repo can I get a list of all the PRs? could Pulls be a new tab alongside the git tab?'). Not started; the user decides whether it goes before or after the v0.12 landing (the coordinator recommends after, as three PRs merged to main one at a time). The earlier description below predates the thin mirror; its provider store, auth-scoped index, RepositoryActivity projection and public nav-panel SDK are retired.

Thin-mirror design for the tab. A 'Pulls' tab beside Files and Git on a GitHub mirror, added with the shell's internal registerNavPanel (the Git tab uses it; no new plugin SDK). Rows show number, title, author, state or draft, and updated time; filters Open, Closed, All; stale, refreshing, offline and typed-failure states; a browserless session and golden. No check or review summary in the rows (it costs requests per pull request). Depends on two things: the list data (mb-lnkl), and opening any pull request from a server opened on a repository URL. Today a server serves at most the one pull request its URL named (builtin_plugins/github/served_pull.py is the companion refresh for that one number; the pull route answers 'absent' for any other; mirror_refresh and the status route carry pull_request: int | None). Selecting a row must fetch that pull request's record and refs/pull/<n>/head on demand (as the missing-commit selection fetch does) and show its page in the same tab, with 'Browse code' switching the pin to its head as now. That generalization is the riskiest piece and should be its own PR, between the list data and the tab.

2026-09-30: deferred by the user's 2026-09-23 decision (thin-mirror plan, Decisions). Not part of v0.12; does not gate mb-n2ro. The design text predates the thin mirror (provider store, auth contexts, leases and SDK panels are retired); re-plan against the thin-mirror plan before starting.
