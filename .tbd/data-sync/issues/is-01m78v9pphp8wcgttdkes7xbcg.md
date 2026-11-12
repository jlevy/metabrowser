---
type: is
id: is-01m78v9pphp8wcgttdkes7xbcg
title: "Pulls tab in jlevy/metaproc: the metadata catalog could not be written"
kind: bug
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-11-12T21:40:53.072Z
updated_at: 2026-11-12T21:40:53.072Z
---
The user, 2026-11-12: 'metab .' in a jlevy/metaproc checkout shows, under the PR tab: 'The metadata catalog could not be written; clear the affected repository cache and retry.' Raised as cache_unwritable by _publish in src/metabrowser/builtin_plugins/github/pull_list_refresh.py, which wraps PrivateStorageError, OSError, sqlite3.Error, and ValueError from publish_page, so the cause is hidden. The user's shell runs ~/.local/bin/metab, 0.12.1.dev38 (a uv tool install from an old local wheel), while newer metab builds on this Mac (the macOS app's review build, other checkouts) share the same cache under ~/.cache/metabrowser. Find the real cause (an out-of-date metab, a catalog written by a newer schema, permissions, or a bug), say whether it is an incompatibility, and fix what is wrong.
