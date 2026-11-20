---
type: is
id: is-01kxse0wddy6je24t1dm5caber
title: "Diff: context expansion, whitespace controls, and measured virtualization"
kind: feature
status: open
priority: 2
version: 18
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01kxse0wpvpg9vx64phcr3bh8s
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
child_order_hints:
  - is-01m0tw8haj67tstjassnq9we07
  - is-01m0w062fn61tjrdp37vnga45p
  - is-01m0w18bwddnc94htabvg4zke8
  - is-01m0y5h1kk1waq5baqsvmqcx6k
  - is-01m0y74n2yd54hyz6kqn93xsw4
created_at: 2026-07-18T01:38:59.628Z
updated_at: 2026-11-20T19:15:57.624Z
extensions: {}
---
Bounded context expansion through content references, whitespace controls, and measured row virtualization or worker evaluation for the diff plugin's renderer (builtin_plugins/diff/diff-view.js). Already on main: intraline refinement (Phase 4, #81, diff-intraline.js), unified and split layouts with bounded syntax (mb-sj1s, #76), and folded runs that mount only their visible prefix (Phase 5). PR #76 finding 76-6 still defers a hunk-boundary lexical-confidence cue until full-source tokenization or context expansion can replace the per-hunk reset.

## Notes

Unified/split layout and syntax highlighting completed by mb-sj1s. The 2026-08-25 Phase 4 addendum chooses a pinned, attributed port of VS Code's pure DP/Myers refinement and boundary heuristics, with browser-local ranges, monotonic split pairing, lighter similar-line tints, stronger changed-range tints, exact-text/syntax composition, measured bounds, and whole-line fallback. Planning evidence is closed in mb-vlz2 and published in PR #81 at commit efa6c97 with exact-head CI green. Context expansion, whitespace controls, and virtualization/worker evaluation remain separate follow-up scope. PR #76 finding 76-6 continues to defer any hunk-boundary lexical-confidence cue until full-source tokenization or context expansion can replace the per-hunk reset honestly.
