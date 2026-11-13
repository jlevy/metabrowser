---
type: is
id: is-01m7b629bqq75pspfegwh78sy4
title: Commits landing answered from the old walk when HEAD moves during its read
kind: bug
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-11-13T19:27:33.238Z
updated_at: 2026-11-13T19:27:33.238Z
---
Found in the round 2 review of #400; also on main. A history page that settles during the newest landing's HEAD read calls selectNewestWhenReady from loadNextPage's finally (git-panel.js ~650) and answers the landing from the old walk. If HEAD then moved, ensureHistory calls refreshHistory() with no selectedId, so the list ends with no selection while the pane shows the previous newest commit. Repro: the round 2 reviewer's harness probe; the 'in front' case in tests/dom/git-panel-behavior.js holds page reads to avoid it. Fix: have the landing wait for the HEAD read, or re-answer after the refresh.
