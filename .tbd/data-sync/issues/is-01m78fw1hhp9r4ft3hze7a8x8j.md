---
type: is
id: is-01m78fw1hhp9r4ft3hze7a8x8j
title: "macOS app: resolve and pass the configuration, cache, and data home variables"
kind: task
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies:
  - type: blocks
    target: is-01m78fw226k1aejzey9xamd4e7
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:11.088Z
updated_at: 2026-11-12T18:21:11.621Z
---
Phase 3 (plan: The macOS App). ChildEnvironment's allowlist drops XDG_CONFIG_HOME, XDG_CACHE_HOME, XDG_DATA_HOME, METABROWSER_CONFIG_DIR, and METABROWSER_CACHE_DIR, so a user who sets one in a shell profile gets a different configuration and cache home in app-launched servers than in Terminal (read from source; affects the repository cache today and the plugin registry later). Resolve them from the login shell once at setup, as git and gh are resolved, and pass them to servers; a setup check proves they reach a server.
