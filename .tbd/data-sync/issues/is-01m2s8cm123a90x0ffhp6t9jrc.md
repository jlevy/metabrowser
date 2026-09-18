---
type: is
id: is-01m2s8cm123a90x0ffhp6t9jrc
title: Refuse a below-floor Git before creating the application home
kind: bug
status: in_progress
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
delegate: unknown@cursor
labels:
  - release:v0.11.0
  - stack:pr148
dependencies: []
parent_id: is-01kzsb4jnyd56wy89xmztkmz2m
hold: null
hold_until: null
created_at: 2026-09-18T03:19:01.921Z
updated_at: 2026-09-18T03:20:23.496Z
started_at: 2026-09-18T03:19:05.864Z
---
acquire_into_staging calls require_acquisition_git before open_cache, so a staging fetch does not create the home when Git is below the floor. acquire_file_source (the CLI --no-serve / file:// --api path) currently calls open_cache first, then acquire_into_staging. On ubuntu-latest Git 2.43.0, metab file:// --no-serve therefore creates METABROWSER_HOME and then refuses.

On a cache miss, check the acquisition floor before preparing the home. A cache hit still opens an existing home and reuses without fetching, so inspect/reuse does not require the floor. Do not serve. Do not pin Git in CI in this slice.

## Notes

PR https://github.com/jlevy/metabrowser/pull/148 on cursor/v011-cache-git-floor-home-bd04 HEAD 51ad2997, stacked on #147. acquire_file_source no longer open_cache on a miss before require_acquisition_git. Cache hit still reuses without the floor. Do not close until review.
