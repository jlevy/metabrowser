---
type: is
id: is-01m78fw1hhp9r4ft3hze7a8x8j
title: "macOS app: resolve the home variables at setup and pass them to servers"
kind: task
status: open
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies:
  - type: blocks
    target: is-01m78fw226k1aejzey9xamd4e7
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:11.088Z
updated_at: 2026-11-12T21:17:36.446Z
---
Phase 0, on the macOS app stack (plan: The macOS App, Key Decisions 6 and 7). The app's ChildEnvironment allowlist drops XDG_CONFIG_HOME, XDG_CACHE_HOME, XDG_STATE_HOME, XDG_DATA_HOME, and METABROWSER_*_DIR, so a user who sets one in a shell profile gets different homes in app-launched servers than in Terminal (read from source; affects the repository cache today). Setup runs the login shell today only when earlier lookups miss, because it can take seconds and raise privacy prompts: run it once at setup for these names, save them with the runtime, pass them to every server, and refresh on Find Again. A setup check proves they reach a server.

## Notes

Body rewritten 2026-11-12 after the Fable 5.2 design review; it supersedes the earlier review notes. The plan's Key Decisions are awaiting the owner.
