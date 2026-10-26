---
type: is
id: is-01m404jrt4sm3rndr1kznbpr6v
title: Separate cache and configuration storage using uv/fdu conventions
kind: epic
status: closed
priority: 2
version: 12
delegate: codex@spud10.local
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
child_order_hints:
  - is-01m404yq5wyjd4tha1p66x5y9a
  - is-01m404yqhz92wqk3x2dfea9251
  - is-01m404yqx2zybbd9789dsb98q8
  - is-01m4569nqwa1mqxdpgaxvbhd3d
  - is-01m456f4va45tae7y1mj72aa3p
hold: null
hold_until: null
created_at: 2026-10-03T05:42:51.965Z
updated_at: 2026-10-26T15:27:23.911Z
started_at: 2026-10-03T05:49:23.081Z
closed_at: 2026-10-26T15:27:23.910Z
close_reason: "Landed on main in #268. Cache and configuration now use separate XDG roots on macOS and Linux with exact --cache-dir / --config-dir overrides; METABROWSER_HOME and the old single-home layout are no longer read and existing files are left untouched. Verified 2026-10-26 on main: browsing a plain folder with isolated --cache-dir and --config-dir creates neither directory. The breaking entry is at the top of the 0.12.0 CHANGELOG section and is on the sign-off list in review-2026-10-01-v012-changes-to-existing-behavior.md."
resolution: null
duplicate_of: null
---
Approved v0.12 clean break: use ~/.cache/metabrowser and ~/.config/metabrowser on Linux/macOS, honoring app-specific and XDG overrides. Remove METABROWSER_HOME and the combined home layout; no backward compatibility aliases, migration, or fallback. Update architecture, runtime paths, safety checks, CLI/UI contracts, test fixtures, goldens, runbook, and release notes. Existing user files remain untouched. Parent release-stability epic tracks overall acceptance.

## Notes

User explicitly approved a clean break for this minor release with zero compatibility constraints. Earlier migration/alias suggestions are superseded. Child beads cover design, runtime storage, and validation. Cache and config each accept exact CLI/environment overrides ahead of XDG bases and defaults; config lifecycle is independent of cache. Existing old files are left untouched.

Published for review as draft PR https://github.com/jlevy/metabrowser/pull/268, commit cbb92dc9. Final local pre-push gate passed: 4005 tests, 8 skipped, 278 transcript checks; installed candidate 0.11.1.dev669+cbb92dc9 verified by both executables and 11-plugin doctor. GitHub CI pending; dependency audit mb-19fc and manual release acceptance remain open.
