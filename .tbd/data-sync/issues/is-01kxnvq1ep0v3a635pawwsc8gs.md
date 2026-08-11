---
type: is
id: is-01kxnvq1ep0v3a635pawwsc8gs
title: "PR #3 review B: type and document sidekick return and error contracts"
kind: bug
status: closed
priority: 2
version: 4
labels:
  - pr-review
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-16T16:21:19.446Z
updated_at: 2026-07-16T16:32:40.907Z
closed_at: 2026-07-16T16:32:40.906Z
close_reason: Return, error, and empty-path contracts are typed, exported, documented, and tested.
---
Owner review comment https://github.com/jlevy/metabrowser/pull/3#issuecomment-4994096399. Covers API-3 (src/metabrowser/projections.py: concrete dict[str, Any] | None result and absent-file documentation), API-4 (publish catchable artifact decompression and JSONL parse exceptions), and API-7 (document resolve_path empty-string/root and directory behavior). Fixed when annotations, exports, tests, and docs describe success and failure behavior exactly.

## Notes

Fixed API-3, API-4, and API-7 from PR #3 owner review comment 4994096399. extract_agent_charts_cached now returns dict[str, Any] | None and documents the absent-file result. ArtifactCompressionError, ArtifactDecompressionLimitError, ArtifactDecompressionTimeoutError, and JsonlParseLimitError are catchable from metabrowser and metabrowser.plugin_api. resolve_path documents the empty-string served-root result and directory possibility. Verified with focused contract tests and the 686-test release gate.
