---
type: is
id: is-01m78v9pphp8wcgttdkes7xbcg
title: "Pulls tab in jlevy/metaproc: the metadata catalog could not be written"
kind: bug
status: closed
priority: 1
version: 5
labels: []
dependencies: []
created_at: 2026-11-12T21:40:53.072Z
updated_at: 2026-11-13T06:58:44.168Z
closed_at: 2026-11-13T06:58:44.167Z
close_reason: "Merged in jlevy/metabrowser#386 (merge 3e7834dd). Cause: an out-of-date CLI metab (0.12.1.dev38) sharing a cache with newer builds. Newer catalogs are now refused before any gh call; damaged ones rebuild. The app's metaproc window loads its Pulls list."
resolution: null
duplicate_of: null
---
The user, 2026-11-12: 'metab .' in a jlevy/metaproc checkout shows, under the PR tab: 'The metadata catalog could not be written; clear the affected repository cache and retry.' Raised as cache_unwritable by _publish in src/metabrowser/builtin_plugins/github/pull_list_refresh.py, which wraps PrivateStorageError, OSError, sqlite3.Error, and ValueError from publish_page, so the cause is hidden. The user's shell runs ~/.local/bin/metab, 0.12.1.dev38 (a uv tool install from an old local wheel), while newer metab builds on this Mac (the macOS app's review build, other checkouts) share the same cache under ~/.cache/metabrowser. Find the real cause (an out-of-date metab, a catalog written by a newer schema, permissions, or a bug), say whether it is an incompatibility, and fix what is wrong.

## Notes

2026-11-12 diagnosis: ~/.local/bin/metab is 0.12.1.dev38 (commit 1db567f77). It cannot read the catalog newer builds write to the shared ~/.cache/metabrowser: ad2969d6 (dev115) raised CATALOG_PROJECTION to 2 and 50e471f4 (dev135) added delta_started_at without a version bump; dev38's checkpoint model (projection le=1, extra=forbid) raises ValidationError, wrapped as cache_unwritable on every write. Current main reads the same file fine (117 rows on a copy). So both: an out-of-date metab, and an incompatibility between versions sharing one cache. Fix in jlevy/metabrowser#386 (newer catalogs refused with newer_cache before any gh call; damaged ones self-heal; shape/version pin test). Recovery: upgrade the CLI metab to a current build; with a current metab nothing to run.

2026-11-12: #386 reviewed through A (senior), B (security), C, D, and E; E approves with no findings at 83bb74fb. CI running there. Close once green.
