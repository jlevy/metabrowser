---
type: is
id: is-01m2h7jjgpzyfbf10238j32z6q
title: "GitHub Pulls tab: list a mirrored repository's pull requests and open any of them"
kind: feature
status: in_progress
priority: 1
version: 28
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m2kttf7tse7rs1nwrk9m3jbj
  - type: blocks
    target: is-01m2kw2d2arc9hn25pfsc4me50
  - type: blocks
    target: is-01m6f39zpnk9rc3kjy552b88qj
parent_id: is-01m6f39t9zax1nbajkkasya6st
child_order_hints:
  - is-01m6f3a7979mvnrevs2y3ngsr6
  - is-01m6f3a7pba32qx4tw03bca2tn
  - is-01m6f3a84d9w0j3vvq3dx4w5h1
  - is-01m6f3a8hwmhajkj14c5528pc8
  - is-01m6f3a8zq6770byr49by7dwed
  - is-01m6f3djrrnd70jq09ttmspt0j
  - is-01m6fk7mz18kwadmnr0w05da09
hold: null
hold_until: null
created_at: 2026-09-15T00:30:52.949Z
updated_at: 2026-11-03T06:47:04.588Z
started_at: 2026-11-03T00:48:45.465Z
---
Add the Pull Requests repository-scoped nav panel after direct view and the bounded index. Project only the index row fields—no review/check summary—through RepositoryActivity and reuse bounded paging, virtualization, roving selection, query-key restoration, loading/error, root replacement, and disposal through public SDK. Selection opens the direct PR address; expansion exposes comparison files. Counts/grouping/visibility come from the bounded model. Execute exact panel-window, selection, restoration, replacement, and disposal owners in hosted-review-session and cli-ui-hosted-review.

## Notes

2026-11-03 status: PR #285, layer 3 of stack 286, head 766a4c3b, CI 9 of 9 green. Reviews A (senior) and B (performance) addressed at d0e277e2 (mb-m971 closed). Round-2 review C, run on Opus because the strong tier's credits ran out, found 1 Medium (tests for the Files handler's scoping and the focus fallback) and 6 Low; being addressed now under mb-7d12, with the list's pin_changed 409 after a back-cache restore. Strong-tier pass owed: mb-wlxn.

2026-11-03: implemented on claude/pulls-3-tab, PR https://github.com/jlevy/metabrowser/pull/285, head 8c17a951, above claude/pulls-2-open-any. Checkpoint seen in headless Chrome 152 on pallets/click with screenshots. make lint-check passes; make test passed but for one test fixed in the next commit, and every tryscript golden passes. Awaiting review; not closed.

2026-11-02, from the other session and the user, to apply in this step: the design system is followed rigorously. A tab is .tab-btn in a .tab-bar, and .github-pull-tabs is being removed. No literal font-size in plugin stylesheets; a check is being added to tests/test_design_vocabulary.py. Navigation rows follow One Chevron and One Row Contract with --ui-row-height and --hover-bg, Navigational Row Collections for keyboard, Age for dates, and Icons for glyphs: Lucide from static/icons.js, currentColor, --icon-glyph. Read docs/design-system.md in full before styling. It is being reorganized on claude/v012-pr-review-workflows, so merge that forward first.

2026-11-02: reopened by the user's decision to build the Pulls tab now, above the v0.12 stack. The plan spec is the authority; this bead's older text is background. Its older blockers are all closed. This is Delivery step 3; rows now show state icons and the default filter is All.

2026-10-01: the design is now the plan spec docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md (mb-qftx, commit 245f296c on codex/v012-landing-docs); it supersedes the notes below where they differ, and its Open Decisions section lists what the user decides first.

2026-10-01, decided by the user: 'we can land the stack first then continue a new stack with the pulls tab' and 'let's stabilize everything else but not implement the pulls tab yet, just make sure we've planned it well'. So: no implementation before the v0.12 stack lands; the plan spec (mb-qftx) is written now; the work starts afterwards as a new stack.

2026-10-01, the user's additions: (a) 'when you open a github repo that would automatically appear, if we know we have the right setup'. Design: the tab appears, like the Git tab, once the shell knows the root is a Git repository whose origin is on github.com (learned after first paint from the repository route, no startup cost); the gh check (installed, version, signed in) runs lazily when the tab is first opened, and a missing or signed-out gh is shown in the tab with what to do, not by hiding the tab. The import-boundary and 'a plain folder starts no gh' tests must keep passing. (b) the same views on an existing checkout: see mb-cbak.

2026-10-01, re-planned for the thin mirror at the user's request ('when I open a repo can I get a list of all the PRs? could Pulls be a new tab alongside the git tab?'). Not started; the user decides whether it goes before or after the v0.12 landing (the coordinator recommends after, as three PRs merged to main one at a time). The earlier description below predates the thin mirror; its provider store, auth-scoped index, RepositoryActivity projection and public nav-panel SDK are retired.

Thin-mirror design for the tab. A 'Pulls' tab beside Files and Git on a GitHub mirror, added with the shell's internal registerNavPanel (the Git tab uses it; no new plugin SDK). Rows show number, title, author, state or draft, and updated time; filters Open, Closed, All; stale, refreshing, offline and typed-failure states; a browserless session and golden. No check or review summary in the rows (it costs requests per pull request). Depends on two things: the list data (mb-lnkl), and opening any pull request from a server opened on a repository URL. Today a server serves at most the one pull request its URL named (builtin_plugins/github/served_pull.py is the companion refresh for that one number; the pull route answers 'absent' for any other; mirror_refresh and the status route carry pull_request: int | None). Selecting a row must fetch that pull request's record and refs/pull/<n>/head on demand (as the missing-commit selection fetch does) and show its page in the same tab, with 'Browse code' switching the pin to its head as now. That generalization is the riskiest piece and should be its own PR, between the list data and the tab.

2026-09-30: deferred by the user's 2026-09-23 decision (thin-mirror plan, Decisions). Not part of v0.12; does not gate mb-n2ro. The design text predates the thin mirror (provider store, auth contexts, leases and SDK panels are retired); re-plan against the thin-mirror plan before starting.

2026-11-03, addressing PR #285 reviews A and B (mb-m971): a key's move in the Pulls tab now replaces the history entry and a click or Enter pushes, the rule all three Navigational Row Collections keep; the list is role=tree with treeitem rows at aria-level 1 and the Files tree's keyboard handler is scoped to #tab-files, so step 4 adds only .tree-children[role=group], the chevron box, and aria-expanded; a poll reads the top window and re-reads the held range only for another list file; the four state glyphs moved to the plugin's pull-state.js. Head d0e277e2.
