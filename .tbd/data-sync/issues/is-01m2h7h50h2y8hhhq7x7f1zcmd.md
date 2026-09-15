---
type: is
id: is-01m2h7h50h2y8hhhq7x7f1zcmd
title: "GitHub Phase 3B: directly addressed PR bundle and selected refs"
kind: feature
status: open
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2h7hrjfx06hzpr7ptz7k9wn
  - type: blocks
    target: is-01m2h7hrjt6yzb16neh8g2zvsd
parent_id: is-01m2h3vtmk6apasv27t6ygrrxf
created_at: 2026-09-15T00:30:06.351Z
updated_at: 2026-09-15T00:30:26.393Z
---
Hydrate one directly addressed pull request without requiring a cached index. Publish one enforced ChangeRequest/v1 frontmatter-md artifact plus bounded review, thread, check, status, retrieval, and manifest records; ask core to fetch only its base, head, and optional merge refs into a Metabrowser namespace; and preserve explicit unavailable/partial states. The selected bundle and its immutable Git object IDs must be fully inspectable offline through registered read routes and a CLI golden.
