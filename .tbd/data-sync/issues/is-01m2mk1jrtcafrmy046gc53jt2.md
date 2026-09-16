---
type: is
id: is-01m2mk1jrtcafrmy046gc53jt2
title: "Phase 0C.2 review R4: isolate installed-distribution Python smoke"
kind: bug
status: closed
priority: 1
version: 4
spec_path: docs/project/specs/active/plan-2026-08-27-github-provider-and-pull-requests.md
labels:
  - phase:hosted-review-0c2
  - review
dependencies: []
parent_id: is-01m2kry0g3g8hbnhr896wvqeve
created_at: 2026-09-16T07:49:02.361Z
updated_at: 2026-09-16T08:39:43.397Z
closed_at: 2026-09-16T08:39:43.397Z
close_reason: "Fixed in b907bb2734929cd0858207ba5d73639aee168636 and formally disposed on PR #136: https://github.com/jlevy/metabrowser/pull/136#issuecomment-5694591401"
resolution: null
duplicate_of: null
---
The isolated distribution smoke preserves ambient PYTHONPATH, PYTHONHOME, and PYTHONOPTIMIZE, runs plain python, and implements correctness checks with assert. This can import the checkout instead of the tested artifact and optimization can erase the checks. Scrub ambient path/home/optimization variables, run the interpreter in isolated mode, use explicit failures, and add a regression with poisoned PYTHONPATH and PYTHONOPTIMIZE proving the installed artifact is used and broken invariants still fail.

## Notes

Implemented in devtools/check_distribution.py and tests/test_distribution_policy.py. Every install subprocess now strips PYTHONPATH, PYTHONHOME, and PYTHONOPTIMIZE; embedded Python runs with -I; correctness checks use explicit RuntimeError failures instead of assert. The focused regression poisons all three variables, verifies the sanitized environment and isolated interpreter flag, and proves no smoke invariant is assert-based. Validation: 10 focused distribution tests passed; Ruff format/check passed; BasedPyright reported 0 errors; git diff check passed; make build passed end to end.
