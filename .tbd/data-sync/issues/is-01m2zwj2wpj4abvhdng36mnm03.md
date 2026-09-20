---
type: is
id: is-01m2zwj2wpj4abvhdng36mnm03
title: "S209-8: PR 209 has never been validated in a real browser, and three spec test-strategy items are unexercised"
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
  - stack:pr209
dependencies: []
parent_id: is-01m2yxd3tnr1s2zf0h0jat1ey2
created_at: 2026-09-20T17:06:59.092Z
updated_at: 2026-09-20T17:16:30.840Z
---
All evidence for PR 209's containment is header assertions on the wire plus a browserless DOM session against the production plugin JS. No one has loaded a hostile page in a real browser and observed the sandbox hold. Spec testing-strategy items with no test: (1) relative references end to end, a page with a sibling stylesheet AND a subdirectory image fetched from the expected /raw/ paths; (2) a nested same-directory iframe and a frameset page actually loading (regression test for the deliberately absent frame-ancestors); (3) dangerous types on the wire beyond html and svg: xhtml, xml, pdf, js, extensionless. Do a scripted real-browser pass using the manual plan recorded in the PR 209 disposition, record results on the PR, and add the three missing tests.

## Notes

2026-09-20: real-browser validation DONE by the user against a hostile fixture served by the PR 209 build (head 04534249): preview default, relative references, nested frame, every sandbox probe blocked; reported as working well. Server side confirmed with curl on the live build (sandbox headers on 200 and 400, Origin null and cross-site text/plain POST get 403, fragment defaults to Source). Note: the desktop built-in browser pane blocks the sandboxed subframe with ERR_BLOCKED_BY_CLIENT, so it cannot be used for this check. REMAINING: the three missing automated tests (relative references end to end with a subdirectory image; nested iframe and frameset loading; dangerous types on the wire beyond html and svg). The PR 209 description is stale (head SHA, 'do not merge' line); an automated edit was blocked by the permission layer, so it needs a manual edit or an allow rule.
