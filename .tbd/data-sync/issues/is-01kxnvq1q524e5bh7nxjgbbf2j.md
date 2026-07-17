---
type: is
id: is-01kxnvq1q524e5bh7nxjgbbf2j
title: "PR #3 review C: make uv and npm policy checks consistent"
kind: bug
status: closed
priority: 2
version: 7
labels:
  - pr-review
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-16T16:21:19.716Z
updated_at: 2026-07-16T16:44:32.180Z
closed_at: 2026-07-16T16:44:32.180Z
close_reason: TOOL-1/2, installed-wheel plugin diagnostics, and the synchronized tooling floor are implemented, regression-guarded, documented, and green under the complete release gate.
---
Owner review comment https://github.com/jlevy/metabrowser/pull/3#issuecomment-4994096399. Covers TOOL-1 (devtools/check_distribution.py: pass the repository uv.toml explicitly for every isolated wheel smoke invocation) and TOOL-2 (devtools/npm_policy.py: use one complete add/build/lock/publish/run/sync keyword set for docs and workflows). Add regression coverage for both policy boundaries.

## Notes

Fixed TOOL-1 and TOOL-2 from PR #3 owner review comment 4994096399 and aligned the build floor with KPress. Every isolated wheel command explicitly selects the repository uv.toml; one add/build/lock/publish/run/sync validator covers documentation and workflows; the installed-wheel gate now runs metab plugins doctor. Biome 2.5.2, setup-uv 0.11.26 with audited Linux SHA-256, and first-party Flowmark 0.3.2 are pinned across manifests, locks, workflows, Make, policy, supply-chain docs, and AGENTS. Broad BasedPyright/Biome suppressions were narrowed, text/index.js graduated to strict TypeScript, and exact ratchet baselines are tracked by mb-hmwo, mb-ffo9, and mb-q1wo. Full make -j4 verify passes with 686 tests, strict lint/types, Flowmark, public hygiene, audits, distributions, and the real installed-wheel doctor command.
