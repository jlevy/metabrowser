---
type: is
id: is-01m013yz0cmbbav156crazdn27
title: Make entire actionable Treemap cell a pointer hit target
kind: bug
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels:
  - browser
  - design-system
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-14T21:48:30.091Z
updated_at: 2026-08-14T21:48:30.091Z
---
Current behavior

Nested directory cells expose navigation metadata only on the .tm-cell-title label strip, so delegated click handling activates the folder only when the text is clicked. The whole cell receives the hover treatment, making the much smaller hit target visually inconsistent. The existing accessible reason for keeping the nested outer cell as a group is valid: a parent role=button must not contain descendant buttons.

Implementation map

- src/metabrowser/builtin_plugins/folder/treemap.js, cellClasses and cellHtml: mark every directory and file outer rectangle as pointer-actionable without turning nested parent rectangles into nested ARIA buttons. Preserve the current label-strip role, accessible name, and roving tabindex handle for nested directory keyboard navigation.
- src/metabrowser/builtin_plugins/folder/treemap.js, cellForElement, actionableCellForElement, and the viewport click listener: resolve pointer activation from the closest data-tm-cell rectangle, validate it with cellIsActionable, and activate exactly that deepest cell. Keep data-tm-index resolution for keyboard focus only and rename or document the helper so pointer and keyboard hit models cannot be confused again.
- src/metabrowser/builtin_plugins/folder/styles.css, .tm-cell and .tm-nested interaction rules: show the pointer cursor across the complete actionable rectangle, including visible nested-folder header, gutter, and empty background. Give remainder or other descriptive cells a default cursor. Do not add overlays, raise z-index, or change display, because descendant rectangles must remain visible and independently interactive.
- tests/dom/folder_plugin_behavior.js: drive clicks against a nested parent outer background, its label, a descendant folder or file, a non-actionable remainder cell, and a file outer background. Assert one navigation per click, deepest-cell-wins routing, Treemap preservation for folders, ordinary file opening, and no ancestor fallback through an inert child.
- tests/test_browser_filter_ui.py: retain a small structural regression check that the whole-cell interaction class and hover treatment agree, while leaving behavioral routing to the DOM test.
- docs/design-system.md, Folder Treemap: document that the visible rectangle is the pointer hit target, the deepest visible cell wins when rectangles are nested, and nested labels remain the keyboard and accessibility handle to avoid invalid nested interactive roles.

Acceptance criteria

- Clicking any visible portion of an actionable directory or file rectangle that is not covered by a descendant activates that rectangle; the label is not a special pointer-only target.
- Clicking a descendant rectangle activates only the deepest descendant and never its containing directory.
- Clicking a descriptive remainder or other non-actionable rectangle performs no navigation and does not fall through to an actionable ancestor.
- Hover and cursor treatment accurately describe the full actionable hit area in light and dark themes, with no text-only hover and no stacking change.
- Enter, Space, arrow-key traversal, focus rings, accessible names, and the no-nested-buttons ARIA structure continue to work.
- Automated DOM and structural coverage passes, make verify passes, and manual validation covers nested and non-nested cells at several rectangle sizes.
