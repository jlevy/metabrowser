---
type: is
id: is-01m8edaswj95zwmwj9hz59ntg6
title: Serve the shared formatter in the WebKit diff measurement harness
kind: bug
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-26-post-load-performance.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/920
    at: 2026-11-27T11:50:17.184Z
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m8cs8jdw8yh0hvdy6449jm9j
hold: null
hold_until: null
created_at: 2026-11-27T11:47:57.449Z
updated_at: 2026-11-27T12:09:58.793Z
started_at: 2026-11-27T11:48:21.599Z
closed_at: 2026-11-27T12:09:58.788Z
close_reason: "Merged #920 at 63c60489. The final exact Linux CI 45994950748 and macOS 45994950669 passed, and the local Chrome/WKWebView benchmark completed both engines."
resolution: null
duplicate_of: null
---
Post-merge macOS run 45992157722 found that the diff-layout benchmark page loads formatters.js and the restrictive WebKit measurement server omits it. Add the exact static asset and verify the existing dependency-closure guard and native CI.
