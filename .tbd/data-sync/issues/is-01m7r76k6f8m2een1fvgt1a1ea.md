---
type: is
id: is-01m7r76k6f8m2een1fvgt1a1ea
title: Revise the object data model plan against main as of 2026-11-18 and the PRs landing soon
kind: task
status: in_progress
priority: 2
version: 11
spec_path: docs/project/specs/active/plan-2026-11-14-object-data-model-and-views.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7f2vek3t6sca32adhd4gq33
hold: null
hold_until: null
created_at: 2026-11-18T20:57:30.574Z
updated_at: 2026-11-19T06:35:37.173Z
started_at: 2026-11-18T20:57:35.381Z
---
Since #453 merged, #487, #491, #484, #536, #522, #529, #506, #528, #558, #546, #540, #559, #511, #493 landed and #550/#552, #380, #534, the fdu stack are open. Fold reuse points (pull-files-summary, ChangeSums, actorIdentity, page/view header, drawn-from-disk fixture), fix Background, terms (view, recent, kind), Pulls row structure, readers list, decision options, and 33 drifted anchors. Decisions stay open for the owner.

## Notes

Owner decisions, 2026-11-18 (to record in the plans): Block-accepted the recommendations for 2, 3, 4, 6, 9, 10, 11, 13, 14, 15, 16, 17, 18, 21, 23. Decisions 1 and 31: SoftSchema for both objects and UI state. Decision 5: pull-request everywhere (rename the --present kind and SelectionKind tokens with the macOS app in one commit; repository/tree map to folder, blob to file). Decision 8: UTC strings at second precision. Decision 12: host frame plus an SDK header frame (noted on mb-7t5s). Decision 19: a main navigation tab named Recent, showing everything happening on the GitHub repo, the Git repo, or the working directory by root type, with working-tree changes as an object and time-clumped updates beside atomic events (design in a companion Recent-tab plan). Decision 20: follow #380's caret rule if it is accepted; until then additions do not bump. Decision 22: D, the page first and the contracts second. Layout: six plan specs (object model, view model, Recent tab, agent interface, plugin authoring, implementation map) in one PR, #570. Owner also asked to plan incremental delivery, weighing an early working-tree diff object against safe cleanups first, and asked for a first-principles walkthrough of every decision before they are final.

Walkthrough, 2026-11-18: the owner confirmed group 1 (Decisions 1/31, 2, 3, 4, 5, 6, 7 A, 8, 10) after the first-principles explanation. Decision 7 A is now taken. Next: group 2 (views and lists: 11, 12, 13, 14, 17, 21, 23).

Walkthrough, 2026-11-18: the owner confirmed group 2 (Decisions 11, 12, 13, 14, 17, 21, 23) at their recommendations, with one refinement to 11: card stays in the named shape set, but its frame is built only with its first real use (the Recent plan moved /recent cards to R4). Next: group 3 (9, 15, 16, 20, PS-1 to PS-7).

Walkthrough, 2026-11-18: the owner confirmed group 3 at the recommendations: Decisions 9 A, 15 A, 16 A (20 already taken), and the plugin authoring plan's PS-1 to PS-7, all A. Next: group 4 (22, VM-10, and the working-tree-first ordering).

Walkthrough, 2026-11-18: the owner confirmed group 4: Decision 22 D (already taken), VM-10 A with the view slice first or beside the object slice, and the implementation map's Ordering 2 (groundwork capped at eight PRs, then the working tree, with V and P in parallel). Next: group 5 (18, 19, RT-1 to RT-7).

Walkthrough, 2026-11-18: the owner confirmed group 5: Decision 18 A, 19 C (taken), RT-1 to RT-7 at their recommendations (RT-4 A in R1 then B from R2; RT-5 A, with B revisited once a refs source exists). The owner asked to add later a bounded recorder of file-change events from the event stream, so file updates become real edit history rather than current modification times; plan it as an R4-or-later item in the Recent plan. Next: group 6 (VM-1 to VM-9, AI-1 to AI-6).

Owner, 2026-11-18: MCP must not be a required part of the architecture; the CLI (metab, taught by the skill) is the complete agent surface. In the final pass, AI-1 says so, and the MCP adapter (mb-5lgp, already optional, P3) is described as outside this design, a dependency of nothing.

Walkthrough complete, 2026-11-18: the owner confirmed group 6 and asked to record all. VM-1 A, VM-2 B, VM-3 C, VM-4/5 A with correction 1 (drop the --untrusted to offer coupling; the default follows whether the caller is local; --ui-control offer stays available), VM-6 B, VM-7 A, VM-9 A. Correction 2: an intent that sends if_generation must name its viewer. AI-1 A reworded (the CLI through the skill is the complete agent surface; MCP is outside the design), AI-2 A, AI-3 A, AI-4 B (the intent verb is present), AI-5 B, AI-6 A. Every decision in the six plans is now taken.
