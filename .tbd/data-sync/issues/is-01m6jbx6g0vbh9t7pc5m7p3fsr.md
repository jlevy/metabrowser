---
type: is
id: is-01m6jbx6g0vbh9t7pc5m7p3fsr
title: Remove the unreachable catalog GitHub-footer projection
kind: chore
status: open
priority: 3
version: 3
spec_path: docs/project/specs/done/plan-2026-10-01-github-pulls-tab.md
labels: []
dependencies: []
parent_id: is-01m6f39t9zax1nbajkkasya6st
created_at: 2026-11-04T04:08:37.118Z
updated_at: 2026-11-25T02:36:25.268Z
---
describePulls in builtin_plugins/github/pulls-panel.js initializes the model's github field to null and nothing assigns it, so the 'See the rest on GitHub' footer branch in the panel's renderer never draws under the incremental catalog. Remove the field, its typedef entry, the renderer branch, and its copy in tests/dom/github-pulls-panel-session.js, then regenerate the affected session expectations. No user-visible change, and no consumer needs it kept.
