---
type: is
id: is-01m6fpmgr1agw2f4tb5t9f3bkj
title: "PR #283 D2: a partly unreadable or reftable lender is still swept and a live ref is lost"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m6f60pqc21gnqnct2pdq16zb
hold: null
hold_until: null
created_at: 2026-11-03T03:18:23.744Z
updated_at: 2026-11-03T03:28:53.085Z
started_at: 2026-11-03T03:18:36.743Z
closed_at: 2026-11-03T03:28:53.084Z
close_reason: "fixed in a2d1fb97 on PR #283: D2 collection_doubt; a ref is swept only when no loose file of its object exists and every pack file reads, else lender_missing and refs stay"
resolution: null
duplicate_of: null
---
Medium. Review D, PR #283, https://github.com/jlevy/metabrowser/pull/283#pullrequestreview-5746541377. src/metabrowser/cache/lender.py:848-861 (prepare_overlay_fetch) and :609-632 (negotiation_tips): the tips probe refuses only when every tip is unreadable; one unreadable loose object (p7) or a reftable lender with no file tips (p7b) passed it and the sweep deleted refs/pull/1/head or the default branch.
