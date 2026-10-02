---
type: is
id: is-01m3wjge2pn6nf3cvcvpbbdx2z
title: "Release rehearsal for v0.12 before landing: the standard release checklist's stability steps against v0.11.0"
kind: task
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-10-01T20:29:17.780Z
updated_at: 2026-10-02T20:47:25.782Z
started_at: 2026-10-01T20:29:25.524Z
---
The user, 2026-10-01: 'We have a standard release process to check for stability and no regressions on features or performance. Let's go ahead and run that early before we land this entire stack. Since there are so many changes, there's quite a bit of risk.' Run docs/publishing.md's Release Checklist steps 1-5 as a rehearsal on the stack's candidate, without tagging, releasing or merging: (2) the complete 'make verify'; (3) the previous-release performance loop (explorations/performance-loop/README.md, 'Comparing a candidate with the previous release') against v0.11.0, recorded as a committed experiment with the performance report regenerated; every candidate run must pass the hard responsiveness and correctness gates, and a repeatable wrong-way metric blocks until fixed or explicitly accepted by the user; read the backend comparison's equivalence (differing rows is a regression until shown otherwise; differing tallies must be confined to what the changelog describes); (4) CI green on the exact candidate commit; (5) review the changes since v0.11.0 and propose the version. Steps 6-10 (tag, publish, post-release checks) are not run. Re-run on the final tip before the landing decision. Related gates: mb-2g6f (regular-folder differentials), mb-67s1 (wall-clock pairs on a quiet machine).

## Notes

2026-10-02: still owed: release checklist step 3 on a quiet machine with no agents running, on the final head (5 headed pairs passing the hard gates, 5 compare_builds pairs read for first_row), recorded as exp-039. Steps 1, 2, 4, 5 passed in exp-038 (#265). make verify passed on 8879c4de.

2026-10-01 rehearsal on c16912f8 (draft PR #265, exp-038, verdict unresolved). Steps 1, 2, 4, 5 pass: make verify exit 0 (3,877 passed, 8 tier skips; 38 goldens; audits clean; distribution checks pass; installed wheel works); CI 9 of 9 on the exact commit; proposed version 0.12.0. Step 3: equivalence passes (four compare_builds runs, 0 row and 0 tally differences; --walk output byte-identical, 46,721,591 bytes); every responsiveness and correctness gate passes in 32 headed captures; load-independent numbers fine (startup scripts 173 vs 171 KB; DOM, repaints, shift, heap equal; instructions within 1.04x except --doctor 1.78x). Wall-clock gates failed for BOTH builds under load (first_row gate 350 ms: control missed 6 of 11 cached captures, candidate 5 of 11; every candidate miss had load above 30; ratios scatter 0.25x-3.5x). Backend first_row leans against the candidate in 5 of 10 pairs under load (1.07x and 1.00x when both answer under 20 ms; 1.03x by instructions): open until a quiet run. Owed before landing: (1) on a quiet host (the machine was at load 12 when no agents ran), on the final tip, with bytecode in both environments: 5 headed pairs with every candidate capture passing the hard gates, and 5 compare_builds pairs read for first_row; rerun with 'EXP=exp-039 <scratchpad>/release-check/rerun.sh <ref> all' (harness worktree metabrowser-v012-release-check; corpus .bench/project-10 there); (2) the user's acceptance of --doctor at 1.78x; (3) fix probe.js frame_missing_px (the stand-in shares the new .preview-frame column: 450 px vs 900 px); (4) CHANGELOG corrections: lines about --allow-edits on a file:// pin (refused in cli/git_pin_cli.py); add --diff refused on a Git source, URL modes need POSIX (home.py) while pyproject says OS Independent, typed 404 for unrelated histories; (5) the 300,000-file flat-stress pass from exp-036 was not run (disk). Not measurable by the loop: a Git source (no control), repeated loads in one tab (mb-tdmd).
