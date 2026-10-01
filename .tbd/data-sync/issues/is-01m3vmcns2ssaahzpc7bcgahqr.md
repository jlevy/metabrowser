---
type: is
id: is-01m3vmcns2ssaahzpc7bcgahqr
title: "Simplify the cache-internal contract registry: remove validation no caller can trigger"
kind: task
status: open
priority: 3
version: 1
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
created_at: 2026-10-01T11:42:57.312Z
updated_at: 2026-10-01T11:42:57.312Z
---
From PR #255 (mb-haxx): of 107 source mutations in the contract layer, 32 are caught by no test, before or after the trim. Most are declaration checks in build_contract_registry and corpus-file checks in the artifact inventory whose inputs now come only from this repository: since PR #246 the registry is internal to the cache with six fixed pure-yaml contracts and no third-party declarer. Mutation ids are in the PR #255 body (A02, A04, A07, A10, A13, A18-A24, A26, A30, A38, A44, A47, A48, B04, B06-B11, B14, B16, B24, B26, B29, B31, B33; A30 is an equivalent mutant). Decide per check: delete the production code as unreachable (preferred where no input can reach it), or add the one case that makes it reachable and tested. Also: three ContractInventoryEntry fields have no reader (schema_bytes_sha256, schema_digest, corpus_payload_sha256); the registry still lives in plugin_loader/ with 'installed' naming though it is cache-internal (move under cache/ once the reference branch no longer needs the old path). Not labelled v0.12: behaviour is correct; this is complexity reduction. The PR #255 review will add the exact lines.
