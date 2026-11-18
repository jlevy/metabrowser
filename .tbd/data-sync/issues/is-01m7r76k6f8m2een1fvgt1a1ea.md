---
type: is
id: is-01m7r76k6f8m2een1fvgt1a1ea
title: Revise the object data model plan against main as of 2026-11-18 and the PRs landing soon
kind: task
status: in_progress
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-14-object-data-model-and-views.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7f2vek3t6sca32adhd4gq33
hold: null
hold_until: null
created_at: 2026-11-18T20:57:30.574Z
updated_at: 2026-11-18T22:03:23.070Z
started_at: 2026-11-18T20:57:35.381Z
---
Since #453 merged, #487, #491, #484, #536, #522, #529, #506, #528, #558, #546, #540, #559, #511, #493 landed and #550/#552, #380, #534, the fdu stack are open. Fold reuse points (pull-files-summary, ChangeSums, actorIdentity, page/view header, drawn-from-disk fixture), fix Background, terms (view, recent, kind), Pulls row structure, readers list, decision options, and 33 drifted anchors. Decisions stay open for the owner.

## Notes

Owner decisions, 2026-11-18 (to record in the plans): Block-accepted the recommendations for 2, 3, 4, 6, 9, 10, 11, 13, 14, 15, 16, 17, 18, 21, 23. Decisions 1 and 31: SoftSchema for both objects and UI state. Decision 5: pull-request everywhere (rename the --present kind and SelectionKind tokens with the macOS app in one commit; repository/tree map to folder, blob to file). Decision 8: UTC strings at second precision. Decision 12: host frame plus an SDK header frame (noted on mb-7t5s). Decision 19: a main navigation tab named Recent, showing everything happening on the GitHub repo, the Git repo, or the working directory by root type, with working-tree changes as an object and time-clumped updates beside atomic events (design in a companion Recent-tab plan). Decision 20: follow #380's caret rule if it is accepted; until then additions do not bump. Decision 22: D, the page first and the contracts second. Layout: six plan specs (object model, view model, Recent tab, agent interface, plugin authoring, implementation map) in one PR, #570. Owner also asked to plan incremental delivery, weighing an early working-tree diff object against safe cleanups first, and asked for a first-principles walkthrough of every decision before they are final.
