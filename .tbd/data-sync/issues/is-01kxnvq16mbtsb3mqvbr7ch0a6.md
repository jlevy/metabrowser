---
type: is
id: is-01kxnvq16mbtsb3mqvbr7ch0a6
title: "PR #3 review A: curate and pin the public Python surface"
kind: bug
status: closed
priority: 1
version: 4
labels:
  - pr-review
dependencies: []
parent_id: is-01kxgmkc6gb2e8s23jf409j4bv
created_at: 2026-07-16T16:21:19.187Z
updated_at: 2026-07-16T16:32:39.434Z
closed_at: 2026-07-16T16:32:39.433Z
close_reason: Public surface curated, documented, and pinned by exact contract tests; full release gate passes.
---
Owner review comment https://github.com/jlevy/metabrowser/pull/3#issuecomment-4994096399. Covers API-1 (src/metabrowser/__init__.py: remove loader/manifest internals from the top-level compatibility contract), API-2 (drop discover_plugins rather than expose its hidden DiscoveryResult return type), API-5 (tests/test_plugin_public_api.py: pin exact metabrowser and plugin_api export sets), API-6 (mark the 0.x API provisional), and API-8 (document LogParser and CLIError). Fixed when code, exact contract tests, and public plugin docs agree.

## Notes

Fixed API-1, API-2, API-5, API-6, and API-8 from PR #3 owner review comment 4994096399. metabrowser.__all__ now contains only the provisional sidekick API plus CLIError and __version__; loader and manifest internals are no longer top-level compatibility commitments. plugin_api and top-level exact export sets are pinned by tests, and docs cover LogParser, CLIError, the provisional 0.x posture, and the internal loader boundary. Verified in the 686-test make -j4 verify gate.
