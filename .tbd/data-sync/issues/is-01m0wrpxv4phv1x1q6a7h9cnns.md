---
type: is
id: is-01m0wrpxv4phv1x1q6a7h9cnns
title: Make Git revisions copyable with the shared identifier affordance
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0w542g2gzak7th85hx2bdz8
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T15:30:36.515Z
updated_at: 2026-08-25T15:30:43.138Z
---
Files/functions: src/metabrowser/static/git-panel.js renderCommitDetail; src/metabrowser/static/plugin-sdk.js shared copy delegation and feedback; src/metabrowser/static/app.js file-header copy markup/delegation cleanup; src/metabrowser/builtin_plugins/diff/diff-view.js renderFileBar and copy-click exclusion; src/metabrowser/static/styles.css; docs/design-system.md; tests/dom/git-panel-behavior.js; tests/dom/sdk-copy-delegate-behavior.js; tests/dom/diff-view-behavior.js; tests/test_browser_assets.py; tests/test_design_vocabulary.py; CHANGELOG.md and the active spec. Behavior/invariants: present the short revision in path-like monospace metadata with an adjacent shared copy icon; copying writes the full commit ID and gives the standard success/failure/resting feedback; filenames and revision identifiers use one delegated explicit-text copy contract; no inline handlers, copied text remains HTML-safe, and existing path copies preserve behavior. Acceptance: focused DOM/static tests cover full-ID payload, accessible labels, feedback and failure, path-copy parity, shared icon/control vocabulary, and make format/make verify pass.
