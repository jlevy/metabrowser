---
type: is
id: is-01m21evdjskgasyks2e37xhg9v
title: Resolve newly reported HTTPX2 dependency audit advisories
kind: bug
status: in_progress
priority: 1
version: 2
labels: []
dependencies: []
created_at: 2026-09-08T21:30:11.919Z
updated_at: 2026-09-08T21:31:53.206Z
---

## Notes

Full verification passed 1901 tests and 99 goldens but reported five new advisories in development-only httpx2/httpcore2 2.5.0. Reviewed upstream changelogs, PyPI upload dates and artifact SHA-256 values. Upgraded to 2.12.0 (August 18, more than 14 days old). Only added transitive record is upstream httpx2-jsfetch 1.0 (August 7), conditional on Emscripten and not installed on native test platforms. No runtime dependency or unrelated lock upgrade. Re-running full verify including audit.
