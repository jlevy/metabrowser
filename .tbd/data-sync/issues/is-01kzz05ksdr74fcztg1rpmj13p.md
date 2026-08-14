---
type: is
id: is-01kzz05ksdr74fcztg1rpmj13p
title: Align Treemap identity with Registry v1
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-13-shared-file-type-taxonomy-and-breakdowns.md
labels:
  - ui
  - treemap
dependencies:
  - type: blocks
    target: is-01kzz0681weprsdjnd151fxkhj
parent_id: is-01kzyxvf9qfc627wszts904wx3
created_at: 2026-08-14T02:03:44.812Z
updated_at: 2026-08-14T03:14:19.788Z
closed_at: 2026-08-14T03:14:19.786Z
close_reason: Treemap classification and palette synchronization now use Registry v1 family/raw identities and the same Breakdown v1 palette population as Files Overview, with neutral extensionless fallback.
---
Update Treemap distribution-key resolution and any dominant-type aggregation adapters to use Registry v1 family identities for Code, Docs, Data, Logs, Archives, and Media while preserving exact raw-extension and neutral remainder keys. Keep Bytes/Files geometry, ignored scope, folder navigation, hover, icons, labels, formatting, and palette leasing unchanged. Tests: shared color identity with Files Overview for all new families, canonical compound matching, raw/No extension neutral behavior, nested hover stability, metric toggling, ignored scope, and captured Breakdown v1 input. Acceptance: Treemap owns no duplicate taxonomy and uses only public SDK classifiers/formatters.
