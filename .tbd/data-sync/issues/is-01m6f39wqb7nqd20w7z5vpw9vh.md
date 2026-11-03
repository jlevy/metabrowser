---
type: is
id: is-01m6f39wqb7nqd20w7z5vpw9vh
title: "Step 2: open any pull request from a repository server"
kind: feature
status: in_progress
priority: 1
version: 12
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: claude-code@spud10
labels: []
dependencies:
  - type: blocks
    target: is-01m2h7jjgpzyfbf10238j32z6q
parent_id: is-01m6f39t9zax1nbajkkasya6st
child_order_hints:
  - is-01m6f3a55zw0sg0cjwd44w5gss
  - is-01m6f3a5ksq0g3qa148nz5q4f0
  - is-01m6f3a64s0ym51z5jstr4kxb2
  - is-01m6f3a6sjp293xntwmfty69pn
  - is-01m6f9dnpygp2ysppv0dtpftvj
  - is-01m6fazyxdrqzk761v5sjyaefc
hold: null
hold_until: null
created_at: 2026-11-02T21:40:32.618Z
updated_at: 2026-11-03T07:25:50.858Z
started_at: 2026-11-02T22:48:21.918Z
---
Delivery step 2 and the riskiest: routes take a number, a provider-kept set replaces the single companion, one attended pull request, what starts a fetch, the job bound, and the Browse code cases. Checkpoint: on a server opened from a repository URL, /pull/<n> for any number offers Fetch and then shows the page.

## Notes

2026-11-03 HANDOFF (paused for another agent): #281 head 653f31bc; reviews A, B, C, D addressed, round 3 not warranted. Awaiting the owner's merge.

2026-11-03 status: PR #281, layer 2 of stack 286, head 5d5546fc, CI 9 of 9 green, mergeable. Reviews A, B, C (round 1) and D (round 2) addressed (mb-fve3, mb-t3gn, mb-cv0q closed); round 3 not warranted. Since 24deeb22 only forward merges. Route changes: /api/source/refresh can answer 429 too_many; its {"for":"commit"} answers carry pull_refresh. Children close at merge.

Implemented on claude/pulls-2-open-any, PR https://github.com/jlevy/metabrowser/pull/281, head d44412bd. Checkpoint seen in real Chrome with the real gh on pallets/click. make test and make lint-check pass on the final commit. Awaiting independent review; not closed.
