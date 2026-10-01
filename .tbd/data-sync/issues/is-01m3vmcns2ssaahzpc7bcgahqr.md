---
type: is
id: is-01m3vmcns2ssaahzpc7bcgahqr
title: "Simplify the cache-internal contract registry: remove validation no caller can trigger"
kind: task
status: open
priority: 3
version: 2
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
labels: []
dependencies: []
parent_id: is-01m3te95dfdnc80j5xywqje9ke
created_at: 2026-10-01T11:42:57.312Z
updated_at: 2026-10-01T12:02:48.872Z
---
From PR #255 (mb-haxx): of 107 source mutations in the contract layer, 32 are caught by no test, before or after the trim. Most are declaration checks in build_contract_registry and corpus-file checks in the artifact inventory whose inputs now come only from this repository: since PR #246 the registry is internal to the cache with six fixed pure-yaml contracts and no third-party declarer. Mutation ids are in the PR #255 body (A02, A04, A07, A10, A13, A18-A24, A26, A30, A38, A44, A47, A48, B04, B06-B11, B14, B16, B24, B26, B29, B31, B33; A30 is an equivalent mutant). Decide per check: delete the production code as unreachable (preferred where no input can reach it), or add the one case that makes it reachable and tested. Also: three ContractInventoryEntry fields have no reader (schema_bytes_sha256, schema_digest, corpus_payload_sha256); the registry still lives in plugin_loader/ with 'installed' naming though it is cache-internal (move under cache/ once the reference branch no longer needs the old path). Not labelled v0.12: behaviour is correct; this is complexity reduction. The PR #255 review will add the exact lines.

## Notes

2026-10-01, from the PR #255 review (line numbers at 93be234c, in src/metabrowser/plugin_loader/ unless a path is given; the registry's only declarer is cache/contracts.py:205-235):

Unreachable declaration checks, deletable: artifact_contracts.py:102-119 and :323-324 (producer and consumer ids are constants; mutants A02, A20, A21); :315-322 (envelope and callables built by the cache module; A18, A19); :325-337 (corpus spec, id, media type are constants; A22-A24); :357-358 (the declarer always returns a spec; A26); :129-132 (an empty corpus is reported later by the evidence engine; A04); :248-251 (SchemaView.load at cache/contracts.py:207 runs first; A07); :273 (declared digest is the embedded one; A10); :491-492 (the dumper is always model_dump; A48); artifact_inventory.py:273-274 (same; B26). The tested A03 and A05 digest checks are tautologies for the same reason (digests computed from the same bytes at cache/contracts.py:201,215). Deleting these touches the fields schema_bytes_sha256, payload_sha256 and media_type, the three reader-less inventory fields, about six rows of _REFUSED_DECLARATIONS, tests/test_artifact_inventory.py:137-139 and tests/test_cache_records.py:152-154. Keep A06, A08, A09, A11, A12, A14/A15, A27, A28.

Dead feature, selector-less "document" contracts (B16, B33; no installed contract has empty selectors): artifact_inventory.py:218-224, :356-357, :367-372; allow_empty at artifact_contracts.py:344-348; `or "*"` at devtools/check_artifact_contracts.py:70; test rows at tests/test_artifact_inventory.py:57-69, :124-125.

Also unreachable: devtools/check_artifact_contracts.py:109-111; src/metabrowser/cache/atomic.py:113-114.

Equivalent or redundant: A30 (parse_yaml_text strips the BOM itself, so .removeprefix at artifact_contracts.py:238,376 can go); B04; B29 and B31 back each other up (one of artifact_inventory.py:286-300 or :322-333 can go); B08 crashes instead of reporting; B09 is covered by "selector has no cases".

Programming-error guards (A38, A44, A47): artifact_contracts.py:411-413, :441-443, :486-488. Replace with contracts[id] or add one three-row test.

Real gaps, one row each if the engine stays: B14 (an `expect` typo silently voids a case), B24 (a validator crash is swallowed), B10, B11, B06, B07 (corpus hygiene), A13 (prepare_schema_graph accepts type: 5, so check_schema is not redundant), a dumper that changes a number (artifact_inventory.py:56-57) or adds a key (:62), gate branches devtools/check_artifact_contracts.py:136-137, :141-142.
