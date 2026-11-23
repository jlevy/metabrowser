---
type: is
id: is-01m84zd2x1v206rxsr1fspew62
title: "Diff | Current: show a file's current version, its changes marked, beside every Rendered | Source chooser"
kind: feature
status: open
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
child_order_hints:
  - is-01m84zddypdtqj4a9fj8f58287
  - is-01m84zdqftrf8jjbyz108151j2
created_at: 2026-11-23T19:51:22.203Z
updated_at: 2026-11-23T19:51:43.317Z
---
Everywhere a diff file bar has Rendered | Source, add a second chooser, Diff | Current. Diff is today's view. Current shows only the new version: in Rendered, added and changed blocks tinted green, with no removed blocks and no redlines; in Source, the unified diff with deleted lines left out, added lines green and context plain. The choice has a CLI/route equivalent and a browserless session golden, and is remembered as Rendered | Source is.
