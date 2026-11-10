---
type: is
id: is-01m7327d4wd92r1n5bnmr1b0zb
title: Implement cache-first PR review and rendered Markdown
kind: epic
status: in_progress
priority: 2
version: 11
spec_path: docs/project/specs/active/plan-2026-11-02-pr-review-mirror-and-checkout.md
delegate: codex@spud10.local
labels: []
dependencies: []
child_order_hints:
  - is-01m715sezspp55zz5v346nrv9n
  - is-01m715sfem46c801k52wr03qt6
  - is-01m715y0nv4hwkwvkvfze1m4r1
  - is-01m718rgbk80mnnjb8d4b1r4xz
  - is-01m73288nre2ajj6ve3p0c9b86
  - is-01m732t9rgn9xnfxfzejj9psqp
  - is-01m734yq0xac22pqms8am9sy50
hold: null
hold_until: null
created_at: 2026-11-10T15:46:31.195Z
updated_at: 2026-11-10T17:58:28.037Z
started_at: 2026-11-10T16:27:59.682Z
---
Implement the reviewed designs in #346 in dependency order. Stack after #346: exact immutable revision views; bounded eager comparison preparation and keyed GitHub reads; Markdown rendered diffs. Keep checkout and managed modes on the same snapshot path and verify cold, warm, offline and concurrent sessions.

## Notes

Built three forward-only branches above #346: codex/pr-review-snapshots, codex/pr-review-cache-loads, codex/pr-rendered-markdown-diffs. Complete local verification and formal GitHub stack publication are in progress. Leave the epic and implementation beads open until the layers land. Paired documentation-heavy browser timing is tracked separately on mb-5rth.

GitHub stack #350 is published: #346 → #347 exact revision links → #348 cache preparation and concurrent loads → #349 Markdown redlines. The three follow-ups are draft PRs. Focused local lint, automated checks, and built-in browser fixtures passed. The full local run hit external scratch limits; standard GitHub CI is running. Keep the implementation beads open through merge.
