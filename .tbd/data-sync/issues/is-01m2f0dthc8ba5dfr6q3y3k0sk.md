---
type: is
id: is-01m2f0dthc8ba5dfr6q3y3k0sk
title: "PR #113 review R4: palette runs its outcome back through the error classifier"
kind: bug
status: in_progress
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m2f0dryv9qmyp9y6g1sc4gwq
created_at: 2026-09-14T03:47:28.427Z
updated_at: 2026-09-14T03:51:18.680Z
---
PR #113 review R4 (Low). src/metabrowser/static/search-palette.js:588 passes an OpenOutcome to describeOpenFailure when message is missing; an unreachable outcome without message would show file-blaming copy. Fix: require message on error/unreachable members of OpenOutcome and MetabrowserOpenFileOutcome (types.d.ts) and use outcome.message directly; update tests.
