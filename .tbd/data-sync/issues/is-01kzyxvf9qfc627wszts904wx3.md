---
type: is
id: is-01kzyxvf9qfc627wszts904wx3
title: Implement shared file type taxonomy and bounded breakdowns
kind: feature
status: open
priority: 2
version: 5
spec_path: docs/project/specs/active/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - file-types
  - cross-project
dependencies: []
created_at: 2026-08-14T01:23:15.382Z
updated_at: 2026-08-14T01:52:29.832Z
---
Implement the Metabrowser-owned reference TOML registry, typed file facts and classification model, nested UI-ready breakdown, and shared conformance corpus described by the linked plan. Add Logs, Archives, and Media; singleton disclosures; and bounded No extension and Remaining types children. Then have fdu adopt the normalized registry and export compatible registry and breakdown formats without adding a runtime dependency between repositories.

## Notes

Planning landed through merged PR #38 at f63ab1d. Implementation remains unstarted. The clean implementation branch codex/file-type-systematization is based directly on that merge; execute Phase 1 in Metabrowser before synchronizing the reviewed registry and conformance corpus into fdu.
