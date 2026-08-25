---
type: is
id: is-01m0wrpxv4phv1x1q6a7h9cnns
title: Make Git revisions copyable with the shared identifier affordance
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T15:30:36.515Z
updated_at: 2026-08-25T15:45:11.180Z
closed_at: 2026-08-25T15:45:11.179Z
close_reason: Git revisions now use the shared copyable-identifier affordance and copy the full ID; all registered exact-value copy surfaces share one tested delegate.
resolution: null
duplicate_of: null
---
Files/functions: src/metabrowser/static/git-panel.js renderCommitDetail; src/metabrowser/static/plugin-sdk.js shared copy delegation and feedback; src/metabrowser/static/app.js file-header copy markup/delegation cleanup; src/metabrowser/builtin_plugins/diff/diff-view.js renderFileBar and copy-click exclusion; src/metabrowser/static/styles.css; docs/design-system.md; tests/dom/git-panel-behavior.js; tests/dom/sdk-copy-delegate-behavior.js; tests/dom/diff-view-behavior.js; tests/test_browser_assets.py; tests/test_design_vocabulary.py; CHANGELOG.md and the active spec. Behavior/invariants: present the short revision in path-like monospace metadata with an adjacent shared copy icon; copying writes the full commit ID and gives the standard success/failure/resting feedback; filenames and revision identifiers use one delegated explicit-text copy contract; no inline handlers, copied text remains HTML-safe, and existing path copies preserve behavior. Acceptance: focused DOM/static tests cover full-ID payload, accessible labels, feedback and failure, path-copy parity, shared icon/control vocabulary, and make format/make verify pass.

## Notes

Implemented the SDK-owned explicit-text copy delegate and migrated file-header, diff-file, and Git-revision copy surfaces. The short revision displays beside the shared icon while the full ID is the payload. DOM/static design tests cover accessibility, exact payload, success/failure/reset feedback, row-toggle exclusion, and path parity. Full make verify and dark/light real-browser copy validation pass.
