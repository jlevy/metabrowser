---
type: is
id: is-01m83ra8436w1qcsw9ryn8k91b
title: "Folder mode: a commit opened by its ID is served under the last branch when it is that branch's tip, and then follows the branch"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7v8bs62dz0nqmqb9rnhgsdb
created_at: 2026-11-23T08:28:14.851Z
updated_at: 2026-11-23T09:33:27.067Z
closed_at: 2026-11-23T09:33:27.064Z
close_reason: "Fixed on claude/folder-branch-follow in fe783c3c7 (code and tests), 86baa10f9 (page), 2a01347f8 (docs), as review A of #747 asked: CheckoutRevisions records how the revision served was asked for (_by_id). A selection that names a ref, as ref or under, follows it; one that names only oid never moves, even when it is served under the ref last served because it is that ref's tip, so the selector still names the ref while status says follows false. Asking for the revision already served the other way changes only that. test_a_commit_opened_by_its_id_at_a_branchs_tip_stays_that_commit, the review's reproduction, failed at 2a1e72b3c and passes. The mirror's same fix is mb-cww9 in #745; a commit by ID read from the store of the origin is that session's."
resolution: null
duplicate_of: null
---
Review A of #747 (A1). CheckoutRevisions.switch_pin keeps the last served ref for an oid request (kept = under, _last_ref), so POST /api/source/pin {"oid": <tip>} made while a branch is served answers ref=refs/heads/<branch>, follows=true, probe_every_s=2.0, and the next page ask moves the page off the commit when the branch moves. Reproduced at 2a1e72b3c: pin refs/heads/feature, pin oid=FEATURE, git branch -f feature local-work, page ask: the pin is local-work. The bead mb-0qgm, changelog.d/mb-0qgm.md and docs/browsing-history.md say a commit opened by its ID stays that commit; test_a_commit_id_and_the_working_tree_never_move opens the ID only from the working tree, where no ref is kept. Decide: either a pin asked for by oid does not follow in a checkout (remember how the pin was asked; no _tip, follows false), or state the exception in the docs, the changelog and the FOLLOWED_CHECKOUT_REFS comment and pin it with a test.
