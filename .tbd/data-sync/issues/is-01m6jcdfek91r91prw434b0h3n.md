---
type: is
id: is-01m6jcdfek91r91prw434b0h3n
title: Keep the null-age pending test independent of formatter parameter additions
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/design-system.md
labels: []
dependencies: []
parent_id: is-01m6j4s4cat6njdpvbjf1dp8zf
created_at: 2026-11-04T04:17:30.574Z
updated_at: 2026-11-04T17:14:29.476Z
closed_at: 2026-11-04T17:14:29.476Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
NormalfullMakeverify539failsoneoldsourceextractor:tests/test_browser_client_filestore.py81 expects exactfunctionformatAge(mtimeSec), but fifthlayeraddsoptions forrelativeages.4757passed9expectedskips; no productfailure. Fix extractionboundaryonly whilepreservingnullpending/tally assertions, in owningfifthbranch soits standaloneCIpasses; forwardcommit andmergefifthinto sixth, no historyrewrite. Verifyallproduction src bytesunchanged, rerunnormalfullgate/newexactwheelacceptance; old539failedreceipt retained.

## Notes

Fixed in owning fifth-layer forward commit 043f9246, merged normally into sixth bdf765c6. Only test extractor prefix changes; 600-character slice and both assertions remain intact. Production src identical b85→043 and all341 payload hashes identical539→bdf.70 focused module checks passed; fresh exact-bdf wheel passed8 public live tests/0skips and93 browser checks. Aggregate normal make verify is running; no merge authorized.
