---
type: is
id: is-01m0tybh589avf526rvh35kzqj
title: Version or preserve the released plugin asset lifecycle
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m0txqcnz6aef2rzesn4cmy5w
created_at: 2026-08-24T22:30:45.671Z
updated_at: 2026-08-24T22:30:45.671Z
---
Release-readiness finding on main c123ae6. Version 0.6.0 eagerly loaded every plugin stylesheet, classic script, and index module with the page; main now loads them only after a selected kind while PLUGIN_SDK_VERSION remains 0.4. docs/plugins.md still promises extra_styles are loaded with the page. Existing 0.4 plugins may depend on page-global CSS or index side effects and are admitted without an upgrade gate. Either preserve the 0.4 lifecycle or bump the SDK, update built-in manifests, and document the break.
