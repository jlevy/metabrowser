---
type: is
id: is-01m2f0dthc8ba5dfr6q3y3k0sk
title: "PR #113 review R4: palette runs its outcome back through the error classifier"
kind: bug
status: closed
priority: 2
version: 3
labels: []
dependencies: []
parent_id: is-01m2f0dryv9qmyp9y6g1sc4gwq
created_at: 2026-09-14T03:47:28.427Z
updated_at: 2026-09-14T04:40:33.429Z
closed_at: 2026-09-14T04:40:33.428Z
close_reason: "Fixed in d454320f: message required on error/unreachable outcomes in all types; palette uses outcome.message directly; classifier only receives thrown errors."
resolution: null
duplicate_of: null
---
PR #113 review R4 (Low). src/metabrowser/static/search-palette.js:588 passes an OpenOutcome to describeOpenFailure when message is missing; an unreachable outcome without message would show file-blaming copy. Fix: require message on error/unreachable members of OpenOutcome and MetabrowserOpenFileOutcome (types.d.ts) and use outcome.message directly; update tests.
