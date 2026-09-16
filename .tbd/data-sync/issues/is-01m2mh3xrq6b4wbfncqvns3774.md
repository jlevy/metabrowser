---
type: is
id: is-01m2mh3xrq6b4wbfncqvns3774
title: "Phase 0C.2 distribution: inventory-driven installed-wheel evidence gate"
kind: task
status: closed
priority: 1
version: 6
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c2
  - distribution
dependencies: []
parent_id: is-01m2krxqqcrn84sje77js6e1vx
created_at: 2026-09-16T07:15:22.006Z
updated_at: 2026-09-16T08:43:20.269Z
closed_at: 2026-09-16T08:43:20.268Z
close_reason: "Implemented, verified, and published in green draft PR #136 at b907bb2734929cd0858207ba5d73639aee168636."
resolution: null
duplicate_of: null
---
Replace Phase 0C.1's explicit built-in schema/file smoke list with a generic installed-distribution check driven by discovered capabilities and the installed contract/profile inventory. In devtools/check_distribution.py and focused tests, build/install the wheel in isolation, discover every provider, verify exact schema/corpus/browser-module bytes and digests, execute every corpus selector through structural and semantic validation, and prove public capability imports remain lightweight. Do not import source-tree paths or hard-code hosted-review contract IDs.

## Notes

Replaced hosted-review-specific wheel/sdist evidence lists and direct model smoke with installed capability discovery plus metabrowser.plugin_loader.artifact_inventory.validate_installed_evidence. Gate is non-vacuous, reconciles every discovered contract/profile declaration, checks public capability imports stay free of SoftSchema/jsonschema/frontmatter imports, and has a regression guard forbidding reintroduction of hosted-review allowlists. Validation: 44 focused Phase 0C.2/registry tests passed; Ruff clean; BasedPyright 0 errors; make build passed, including isolated wheel doctor/API/distribution smoke.
