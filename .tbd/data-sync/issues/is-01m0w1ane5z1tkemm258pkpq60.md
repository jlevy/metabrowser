---
type: is
id: is-01m0w1ane5z1tkemm258pkpq60
title: "Phase 4.6: Measure and validate intraline behavior in a real browser"
kind: task
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m0w1b43a6zy5a3j7z4yv76v7
  - type: blocks
    target: is-01m0w1bh84kq4t17bjwxyqv5mj
parent_id: is-01m0w18bwddnc94htabvg4zke8
created_at: 2026-08-25T08:41:57.444Z
updated_at: 2026-08-25T08:42:25.923Z
---
Files/functions:
- Add or extend checked-in real-browser fixtures/explorations for JavaScript, YAML, Markdown, long lines, shifted/unequal runs, unrelated text, and the maximum accepted comparison shape.
- Exercise refineChangedRun/refineFileChangedRuns and the mounted diff view under the repository browser test path.
- If and only if traces justify a separate production bound, add a named constant beside its measured fixture and test plain/whole-line fallback.

Measurements:
- Capture changed-run UTF-16 size, edit distance/work, elapsed main-thread time, and available allocation/heap evidence for ordinary, unequal, minified-long-line, unrelated, and maximum-patch cases.
- Evaluate synchronous/yielded work against the existing interaction budget before considering a worker. Add no arbitrary cutoff or dependency.

Acceptance:
- Real browser validates unified/split JavaScript, YAML, and Markdown syntax plus intraline layers; copy/selection text; horizontal overflow; narrow layout; fold and layout state; no late mutation; no console error.
- Long/pathological cases remain responsive and preserve selectable exact text through honest fallback.
- Light, dark, and high-contrast screenshots/inspection confirm the row/inner hierarchy.
- The measurement record is reproducible and explains whether the existing patch/hydration boundary is sufficient.
