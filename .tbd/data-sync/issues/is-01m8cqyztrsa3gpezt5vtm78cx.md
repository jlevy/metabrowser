---
type: is
id: is-01m8cqyztrsa3gpezt5vtm78cx
title: Verify the released SoftSchema plugin in isolated Metabrowser installs
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-26-softschema-collection-tables.md
labels: []
dependencies: []
parent_id: is-01m8cnf4sgyjn4q4psvp77emx2
created_at: 2026-11-26T20:15:15.792Z
updated_at: 2026-11-26T20:15:15.792Z
---
The preview wheel builds, and the isolated smoke currently rejects its extra softschema plugin because the expected plugin set predates the preview. After the published upstream collection API is available, update the expected plugin inventory and exercise the real collection and table APIs from an isolated installed wheel using the published pin. The preview source overlay is only for development verification.
