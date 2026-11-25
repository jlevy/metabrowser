---
type: is
id: is-01m8898kcprj50strs0xfshvjn
title: "Security hardening: close the threat model's open findings"
kind: epic
status: open
priority: 1
version: 2
spec_path: docs/project/architecture/arch-threat-model.md
labels:
  - linear
  - Bug
dependencies: []
created_at: 2026-11-25T02:41:24.188Z
updated_at: 2026-11-25T02:43:10.145Z
extensions:
  linear:
    id: dbe32518-a918-4662-8481-6c14d83fce00
    linked_at: 2026-11-25T02:43:10.145Z
---
The threat model (docs/project/architecture/arch-threat-model.md, #797) names each threat and the policy that answers it. The findings it left open are filed as beads beneath this epic: framing of the trusted shell, /raw's path race and media types, the gh environment, a served folder's diff drivers under --untrusted, the diagram frame's sandbox, quarantine of app downloads, bounded structured parsing, and the cache's size bound. Done when each is fixed or recorded as an accepted risk in the threat model.
