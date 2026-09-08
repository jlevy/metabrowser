---
type: is
id: is-01m21evdjskgasyks2e37xhg9v
title: Resolve newly reported HTTPX2 dependency audit advisories
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-09-08T21:30:11.919Z
updated_at: 2026-09-08T21:45:27.456Z
closed_at: 2026-09-08T21:45:27.456Z
close_reason: Fixed in 37011c44 and pushed to the top inventory PR. Full make verify passes 1901 tests and 99 goldens, both vulnerability audits, distribution inspection and installed-wheel smoke. All six CI checks passed at run 34282011816, including Python 3.12/3.13/3.14 and complete-stack integration with main. Browser validation on the committed code passed Markdown/Python opens, Quick File, the 5000-row Recent view, back/forward, filter restoration and reload with no new warnings/errors. Controlled performance evidence and the runtime-mismatch correction are committed; small residual serving/scaling work remains in mb-5no9.
resolution: null
duplicate_of: null
---

## Notes

Full verification passed 1901 tests and 99 goldens but reported five new advisories in development-only httpx2/httpcore2 2.5.0. Reviewed upstream changelogs, PyPI upload dates and artifact SHA-256 values. Upgraded to 2.12.0 (August 18, more than 14 days old). Only added transitive record is upstream httpx2-jsfetch 1.0 (August 7), conditional on Emscripten and not installed on native test platforms. No runtime dependency or unrelated lock upgrade. Re-running full verify including audit.
