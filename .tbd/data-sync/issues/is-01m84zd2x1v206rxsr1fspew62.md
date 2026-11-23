---
type: is
id: is-01m84zd2x1v206rxsr1fspew62
title: "Diff | Current: show a file's current version, its changes marked, beside every Rendered | Source chooser"
kind: feature
status: open
priority: 2
version: 10
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
labels: []
dependencies: []
parent_id: is-01kxse0d3sm8h0p1yh1mjwgbxz
child_order_hints:
  - is-01m84zddypdtqj4a9fj8f58287
  - is-01m84zdqftrf8jjbyz108151j2
  - is-01m84zk6ansaqq4a1tr2c2pnpd
  - is-01m84zkbbsym0ezq55f8zmg1bm
  - is-01m84zkjpq6q850pb85782y3g2
  - is-01m84zkqj2vs24fbx4ygf6wveq
  - is-01m84zkvs3zz3076170rd0krth
  - is-01m856rcj9syg0ndntv31degzt
created_at: 2026-11-23T19:51:22.203Z
updated_at: 2026-11-23T21:59:52.647Z
---
Everywhere a diff file bar has Rendered | Source, add a second chooser, Diff | Current. Diff is today's view. Current shows only the new version: in Rendered, added and changed blocks tinted green, with no removed blocks and no redlines; in Source, the unified diff with deleted lines left out, added lines green and context plain. The choice has a CLI/route equivalent and a browserless session golden, and is remembered as Rendered | Source is.

## Notes

2026-11-23: the user confirmed Diff | Current is one choice for the whole diff (remembered as diff.show), as the plan in PR #765 chose.
