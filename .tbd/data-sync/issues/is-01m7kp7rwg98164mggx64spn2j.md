---
type: is
id: is-01m7kp7rwg98164mggx64spn2j
title: Fallback measurement harness and per-kind native CI report (R17, R29)
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-08-23-inventory-provider-refactor-and-fdu-adoption.md
labels: []
dependencies: []
parent_id: is-01m0r8xt95921dabcddjjm7csf
created_at: 2026-11-17T02:44:05.648Z
updated_at: 2026-11-17T02:44:05.648Z
---
Keep the fallback composite outside src/ as a maintained harness injected at the composition root; register fdu in bench_serving with wheel attestation; CI reports per query kind whether fdu answered natively. See docs/project/research/research-2026-11-17-fdu-backend-revisited.md, D12.
