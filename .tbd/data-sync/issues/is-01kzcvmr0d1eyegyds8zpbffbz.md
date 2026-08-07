---
type: is
id: is-01kzcvmr0d1eyegyds8zpbffbz
title: "HTML P4: html kind, full-page detection, and sandboxed preview"
kind: feature
status: open
priority: 1
version: 1
spec_path: docs/project/specs/active/plan-2026-08-06-html-rendering-and-trust-model.md
labels: []
dependencies: []
parent_id: is-01kzcvm6cpe5b8sb9b9n3gb16g
created_at: 2026-08-07T00:58:17.996Z
updated_at: 2026-08-07T00:58:17.996Z
---
Add a built-in html kind for .html/.htm with preview and source views. A bounded 4 KiB sniff (doctype/<html/<head/<body/<frameset, BOM- and comment-tolerant) selects the default view only, never gates the feature. Preview renders an iframe with sandbox="allow-scripts allow-popups allow-forms" and referrerpolicy="no-referrer" — never allow-same-origin, never allow-top-navigation — with a disposal path. Suppress the preview view when active_content is off. Document the trust model in SECURITY.md and the README.
