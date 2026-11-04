---
type: is
id: is-01m6hpk8g024g79y02he6x1srw
title: Preserve expanded PR row geometry across virtualized remounts
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-10-01-github-pulls-tab.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6hkbt0t0qhvrhxhktgefe38
hold: null
hold_until: null
created_at: 2026-11-03T21:56:11.392Z
updated_at: 2026-11-04T17:14:29.681Z
started_at: 2026-11-03T21:57:11.811Z
closed_at: 2026-11-04T17:14:29.681Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Real headless-browser probe expanded a noncurrent600-file PR row to15185.5px, scrolled it offscreen until its DOM was removed, then returned. The old PR-row content-visibility auto/41.5px intrinsic fallback replaced its measured expanded geometry, collapsing scrollHeight19704to4560 and clamping scrollTop. The new top-level window already bounds mounted rows near100, so remove redundant PR-row content-visibility/intrinsic-size CSS and recheck the unchanged browser remount assertion plus5000-row performance. Keep logical expanded state and bounded nested file rows.
