---
type: is
id: is-01m2s8cm123a90x0ffhp6t9jrc
title: Refuse a below-floor Git before creating the application home
kind: bug
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: unknown@cursor
labels:
  - release:v0.11.0
dependencies: []
parent_id: is-01kzsb4jnyd56wy89xmztkmz2m
hold: null
hold_until: null
created_at: 2026-09-18T03:19:01.921Z
updated_at: 2026-09-18T03:19:06.046Z
started_at: 2026-09-18T03:19:05.864Z
---
acquire_into_staging calls require_acquisition_git before open_cache, so a staging fetch does not create the home when Git is below the floor. acquire_file_source (the CLI --no-serve / file:// --api path) currently calls open_cache first, then acquire_into_staging. On ubuntu-latest Git 2.43.0, metab file:// --no-serve therefore creates METABROWSER_HOME and then refuses.

On a cache miss, check the acquisition floor before preparing the home. A cache hit still opens an existing home and reuses without fetching, so inspect/reuse does not require the floor. Do not serve. Do not pin Git in CI in this slice.

## Notes

Starting on cursor/v011-cache-git-floor-home-bd04 stacked on #147. Cache-miss acquire_file_source must require_acquisition_git before open_cache.
