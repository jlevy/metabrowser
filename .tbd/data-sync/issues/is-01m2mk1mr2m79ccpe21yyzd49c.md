---
type: is
id: is-01m2mk1mr2m79ccpe21yyzd49c
title: "Phase 0C.2 review R10: validate capability evidence from the sdist"
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
created_at: 2026-09-16T07:49:04.385Z
updated_at: 2026-09-16T08:39:43.479Z
closed_at: 2026-09-16T08:39:43.479Z
close_reason: "Fixed in b907bb2734929cd0858207ba5d73639aee168636 and formally disposed on PR #136: https://github.com/jlevy/metabrowser/pull/136#issuecomment-5694591401"
resolution: null
duplicate_of: null
---
The generic installed capability discovery and evidence smoke runs only against the wheel, while the sdist check now covers unrelated file suffixes and hygiene. Install the sdist in isolation or build the tested wheel from it and run the same provider, registry, corpus, and parser evidence checks. Add a negative test where sdist capability evidence or entry points are missing and require failure.

## Notes

The same generic installed capability smoke now runs against both the built wheel and built sdist. Each isolated install discovers the independently expected provider set, builds registries, runs validate_installed_evidence over packaged schema/corpus/parser evidence, rejects discovery errors and declaration loss, and requires nonempty contract/profile registries. The sdist pyproject entry points are also reconciled before install. A negative test proves a broken sdist evidence failure is fatal and retains its diagnostic. Validation: make build rebuilt both artifacts and passed isolated installs plus doctor/API smoke (2 providers, 16 contracts, 2 profiles); 10 focused tests, Ruff, BasedPyright, and diff check passed.
