---
type: is
id: is-01m2nz9gwd4wyxmrpx49cp9yck
title: "GitHub pull requests on an existing checkout: shared records, no writes to the user's repository"
kind: feature
status: open
priority: 1
version: 27
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: null
labels: []
dependencies:
  - type: blocks
    target: is-01m2kw2bvjj5kcsczkz40cmhqx
  - type: blocks
    target: is-01m6f3a2f5v5bkym87p85a0wq2
parent_id: is-01m6f39t9zax1nbajkkasya6st
child_order_hints:
  - is-01m6f3abb5ys26ghefzy1d3kcs
  - is-01m6f3abz4cv8g936k4ry94ygb
  - is-01m6f3aces3z20vehpwkkxdd7m
  - is-01m6f3acyxhn6fc74nvnwbb6gm
hold: null
hold_until: null
created_at: 2026-09-16T20:42:19.915Z
updated_at: 2026-11-03T02:06:04.286Z
started_at: 2026-09-16T21:12:28.713Z
---
Enable hosted capabilities for an ordinary user-owned Git checkout without converting or copying it into a managed repository entry. Discover credential-free provider remote candidates read-only; resolve an unambiguous candidate through the provider registry to stable RepositoryRef; require explicit selection for multiple GitHub remotes and fork/upstream ambiguity; attach the session without persisting its absolute path; reuse the global provider mirror and lazily create or hydrate the shared repository store only for branch, diff, or PR content. Derive the canonical RepositoryStoreId deterministically from provider kind, canonical instance, raw stable repository opaque ID, and Git object format; converge verified objects and aliases under ordered locks and CAS without a mutable provider-to-store pointer. Prove no writes to files or .git, two local clones plus HTTPS/SSH sources reuse one provider repository and canonical store under the same auth context, different auth contexts remain isolated, failed convergence leaves aliases unchanged, purge/detach preserves shared reachable state, and local dirty state remains a filesystem overlay rather than mirror input.

## Notes

2026-11-02, from #283's owner: hold steps 5 and 6 until they send one more head, #283 with #284 merged in (order #280, #284, #283). It brings typed answers base_uncertain, commits_unavailable, lender_missing, parent_unavailable; GitCommitStats counts can be null for a commit whose parent is past a shallow boundary, so arithmetic must handle null; ref_on_origin can be null while a served ref has been swept and not refetched, which does not mean gone from origin; the pull page's session prints from tests/dom/github-pull-page-session.js and github-pull-page-second-session.js, so new output goes in the second or is asserted.

2026-11-02: gate updated, reported by the other session: the owner accepted the overlay store design, taking every recommendation. Plan: docs/project/specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md on claude/v012-pr-review-design at b330e0c9; read its Fit with the Pulls Tab Plan and Finding the Checkout sections before designing this step. It assumes: no-loss is relaxed for overlays; only a checkout named with --checkout or served with metab <checkout> may lend, so a metab <checkout> server opening a pull request is a legitimate lender with zero flags; an uncertain merge base deepens as a bounded job and reads base_uncertain meanwhile and offline; an existing full mirror is kept and the conversion printed; borrows sits beside location in status and the heading tooltip. Do not start until the other session says its overlay step 1 on claude/v012-overlay-acquisition is reviewed. That plan's step 4 rewrites the Pulls plan's step 5 text.

2026-11-02: GATE. Build last. The proposal docs/project/specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md on branch claude/v012-pr-review-design revises this plan's alternates rejection and the in-page fetch with an overlay store that borrows a checkout's objects. It is under independent review and the owner has not decided. This step and mb-r50o depend on its outcome.

2026-11-02: reopened by the user's decision to build the Pulls tab now, above the v0.12 stack. The plan spec is the authority; this bead's older text is background. Its older blockers are all closed. This is Delivery step 5.

2026-10-01: the design is now the plan spec docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md (mb-qftx, commit 245f296c on codex/v012-landing-docs); it supersedes the notes below where they differ, and its Open Decisions section lists what the user decides first.

2026-10-01, decided by the user: 'we can land the stack first then continue a new stack with the pulls tab' and 'let's stabilize everything else but not implement the pulls tab yet, just make sure we've planned it well'. So: no implementation before the v0.12 stack lands; the plan spec (mb-qftx) is written now; the work starts afterwards as a new stack.

2026-10-01, re-planned at the user's request: 'we also need to consider how to offer that (having views and refreshing on the github PRs and other data) on top of an existing checkout as well as a metabrowser-owned cache checkout'. Not started; sequenced after the mirror case (mb-lnkl, then on-demand pull-request open, then mb-iw1v). Thin-mirror design for a local checkout served as a folder: (1) Identity: the GitHub repository is read from the checkout's origin remote (github.com only; which remote on a fork is a user decision, origin first, a setting later). (2) One set of records: the pull-request list and per-PR records are keyed by the repository identity and live in Metabrowser's cache (cache/sources/<slug>/pulls/), shared by a checkout and a cache mirror of the same repository; a source directory with records and no store must be a valid cache state. Nothing is written into the user's checkout. (3) No writes to the user's repository: no fetch of refs/pull/<n>/head into the user's .git (the stack's rule: no branch, index, worktree or ref writes). Conversation, reviews and checks need no Git objects and work on any checkout. Files changed and View file work when the base and head commits are already in the checkout; otherwise the page offers an explicit fetch into Metabrowser's own mirror (a full clone, so the user's choice). A cache-side store that borrows the checkout's objects (alternates) is possible and left out of the first version (a gc in the user's repository can break it). (4) Network only when asked: opening a local folder makes no network request today and that stays true; on a checkout the list loads when the user opens the Pulls tab and refreshes in the background only while that tab is in use. A cache mirror already refreshes in the background. (5) Trust: the folder is trusted, pull-request text is not; it renders through the inert allowlist regardless of the folder's profile, and the hostile-content tests run under both profiles. Suggested PRs: one for the tab and PR pages on a checkout (identity, shared records, lazy gh check, network on use), one for Files changed on a checkout. The earlier description below predates the thin mirror.

2026-09-30: deferred by the user's 2026-09-23 decision (thin-mirror plan, Decisions). Not part of v0.12; does not gate mb-n2ro. The design text predates the thin mirror (provider store, auth contexts, leases and SDK panels are retired); re-plan against the thin-mirror plan before starting.
