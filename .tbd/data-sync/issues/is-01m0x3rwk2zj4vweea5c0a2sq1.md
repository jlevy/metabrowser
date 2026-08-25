---
type: is
id: is-01m0x3rwk2zj4vweea5c0a2sq1
title: Share immediate dimmed preview feedback
kind: task
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-25-git-revision-navigation-performance.md
labels: []
dependencies:
  - type: blocks
    target: is-01m0x3sawfqnqshvkb4rqz54yq
  - type: blocks
    target: is-01m0x3skec67w78kafbez3xj2d
parent_id: is-01m0w52mbqvhdj9r2et2eh9p55
created_at: 2026-08-25T18:43:55.097Z
updated_at: 2026-08-25T18:44:18.507Z
---
Files/functions: src/metabrowser/static/app.js claimPreview plus new begin/end shared preview-navigation state exposed through MetabrowserShell, selectFile, renderPreviewHtml, and renderPreviewNode; src/metabrowser/static/git-panel.js clearPendingState and selectCommit; src/metabrowser/static/styles.css preview pending modifier and token; tests/test_browser_loading_delay.py and focused DOM or static contracts; docs/design-system.md and CHANGELOG.md. Behavior: a retained preview dims immediately and gently for both file and Git selection, keeps its geometry and interactions stable, sets and clears aria-busy under claim ownership, restores full brightness as soon as the requested view reaches the painted readiness boundary, and never leaves stale pending state after replacement, error, cancellation, tab ownership change, or disposal. Initial empty loads retain the delayed neutral spinner. Reduced motion disables the opacity transition but not the state change. Acceptance: focused tests fail before and pass after; both navigation paths use one class and shell lifecycle; both themes and reduced motion pass visible checks; no progress bar, blocking overlay, or minimum animation delay.
