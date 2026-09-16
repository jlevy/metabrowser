---
type: is
id: is-01m2mh3pyq4m362014a5eqw3zw
title: "Phase 0C.2 inventory: generic contract and profile completeness checker"
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c2
  - inventory
dependencies: []
parent_id: is-01m2krxqqcrn84sje77js6e1vx
created_at: 2026-09-16T07:15:15.030Z
updated_at: 2026-09-16T08:43:20.244Z
closed_at: 2026-09-16T08:43:20.234Z
close_reason: "Implemented, verified, and published in green draft PR #136 at b907bb2734929cd0858207ba5d73639aee168636."
resolution: null
duplicate_of: null
---
Implement a provider-neutral inventory checker over InstalledRegistries and installed CapabilitySet declarations. Require every contract to expose exact schema bytes/digests, enforced structure, semantic validation, producer/consumer IDs, resolvable corpus evidence, and browser evidence when browser-consumed; require every profile to name same-provider installed contracts plus target/cardinality/pagination/completeness semantics. Reject duplicates, orphans, unresolved selectors, and declarations absent from the architecture inventory. Determine exact files/functions from the Phase 0C.1 registry seams before editing.

## Notes

Implemented the provider-neutral Phase 0C.2 inventory/evidence checker. Installed module src/metabrowser/plugin_loader/artifact_inventory.py exposes deterministic contract/profile inventory plus check_installed_evidence and validate_installed_evidence; it parses the generic base_document/base_records + cases corpus shape, resolves every selector, applies mutations, and executes structural plus semantic validation. devtools/check_artifact_contracts.py reconciles exact contract/profile architecture rows and runs exact declared browser module/corpus bytes through devtools/artifact-contract-browser-check.mjs. The Node gate requires declared exports, exact absent-key document-scope selection, selected-case parity, exact v1 result shapes, preservation of the full valid input record, input immutability, thrown-parser failure, and an explicit completion proof. Makefile lint/lint-check invoke the checker; devtools/lint.py holds the harness to Biome. Synthetic third-party tests cover valid inventory, missing/zero-case/orphan selectors, explicit null/non-string selectors, wrong expectations, malformed paths, missing/orphan/duplicate architecture rows, profile drift, missing browser export, Python/browser document-case agreement, valid/invalid parity, early exit, missing value/error, extras, malformed results, empty error, throws, record loss, and in-place mutation. Evidence: 18 focused tests passed; make lint-check passed with 16 contracts and 2 profiles OK; Ruff, BasedPyright, Biome, TypeScript, public hygiene, supply chain, parity, and Flowmark all green. Review findings mb-pql6, mb-cs4l, and mb-vnw4 are addressed in code/docs/tests but intentionally left open for PR disposition.
