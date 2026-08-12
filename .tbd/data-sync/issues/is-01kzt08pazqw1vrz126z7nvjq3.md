---
type: is
id: is-01kzt08pazqw1vrz126z7nvjq3
title: "PR #24 review R18: tab switch leaves an orphaned preview spinner"
kind: bug
status: closed
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-08-06-git-graph-view.md
labels: []
dependencies: []
parent_id: is-01kzctqt5s7te6w75jm5pvg6g7
created_at: 2026-08-12T03:29:13.566Z
updated_at: 2026-08-12T03:29:14.509Z
closed_at: 2026-08-12T03:29:14.508Z
close_reason: Fixed on feat/git-graph-view (59f99ba).
---
activateNavPanel claims the preview, invalidating any in-flight file or commit load, but nothing retired the placeholder those loads had already painted, so the pane could sit on 'Loading file...' until an unrelated navigation redrew it. A consequence of the R1 preview-ownership generations. A loading placeholder is now replaced on activation; rendered content is left alone. No automated coverage: there is no app.js harness for activateNavPanel and building one costs far more than the four-line guard, so it is on the manual validation checklist (mb-tyqr).
