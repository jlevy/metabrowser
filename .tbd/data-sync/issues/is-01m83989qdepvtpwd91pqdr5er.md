---
type: is
id: is-01m83989qdepvtpwd91pqdr5er
title: "T3: A comparison's file-type tally route for the diff chooser's counts"
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-17-general-diff-rendering.md
delegate: claude-code@spud10
labels:
  - diff
dependencies:
  - type: blocks
    target: is-01m8398zrcds3cgc9ebm47c9td
parent_id: is-01m83968ry3rs287s3mgg0r93y
hold: null
hold_until: null
created_at: 2026-11-23T04:05:02.298Z
updated_at: 2026-11-23T10:38:17.498Z
started_at: 2026-11-23T05:40:04.347Z
closed_at: 2026-11-23T10:38:17.497Z
close_reason: "Merged in https://github.com/jlevy/metabrowser/pull/736 (stack #735, merged 2026-11-23 as 72b7173)"
resolution: null
duplicate_of: null
---
The chooser lists only the types a change set has, with counts, as the Files tab's does
from the rollup's tally (`extensions`, `canonical_extensions`, `type_families`,
`type_presets`; see `wire_models.py` and `inventory_engine/providers/python_inventory.py`).

- Add a route answering that tally for a comparison, taking the same comparison params:
  a `comparison-types` hook in the diff plugin and a delegating `pull-comparison-types`
  in the GitHub plugin (as `pull-comparison` delegates to `comparison_at`). Alternative
  to weigh: one hook with a `view=types` param. Pick whichever keeps the route map
  simplest; do not add a field to the file-diff-v1 document.
- Counts over the whole change set, ignoring `types=`, so the menu does not shrink as
  the reader narrows. A change counts once per type it matches (renames across types).
- The gitignored column of the tally is zero for a comparison; say so in the docstring.
- Reuse the inventory's tally builder rather than writing a second one.
- Parity rows for each new route, goldens, and the route map
  (`docs/project/architecture/arch-views-models-routes.md`) in the same change.
