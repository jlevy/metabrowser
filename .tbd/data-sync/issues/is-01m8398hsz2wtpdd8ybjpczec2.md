---
type: is
id: is-01m8398hsz2wtpdd8ybjpczec2
title: "T4: Expose the File type menu builders through window.metabrowser"
kind: task
status: in_progress
priority: 2
version: 3
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
created_at: 2026-11-23T04:05:10.589Z
updated_at: 2026-11-23T06:07:56.785Z
started_at: 2026-11-23T06:07:56.784Z
---
The Files tab builds the chooser's rows in private `app.js` globals (`filterTypeOptions`,
`filterTypePresets`, `filterTypeFamilies`, `filterTypePresetSections`, reading
`_extensionTally` and friends). Plugins may not reach into those (AGENTS.md, Browser and
Plugin Boundary), so the diff plugin cannot reuse them today.

- Move them into a strict-checked module (e.g. `static/file-type-menu.js`) as pure
  functions of a tally plus options (show-ignored, the row cap
  `FILTER_TYPE_MENU_MAX`, the icon resolver), returning the `options` and
  `presetSections` that `filterControls.menuGroupHtml` takes.
- The Files tab calls the module with its tally; no visible change, existing Files
  goldens and DOM sessions unchanged.
- Publish it on the SDK (`plugin-sdk.js`, `types.d.ts`). Additive, so no
  `PLUGIN_SDK_VERSION` bump unless a manifest contract changes.
- Loading tier: same as today's code (eager, since the Files tab uses it on load);
  state that in the asset tier table.
