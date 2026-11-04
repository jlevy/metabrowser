---
type: is
id: is-01m6jcdfek91r91prw434b0h3n
title: Keep the null-age pending test independent of formatter parameter additions
kind: bug
status: in_progress
priority: 2
version: 2
spec_path: docs/design-system.md
labels: []
dependencies: []
parent_id: is-01m6j4s4cat6njdpvbjf1dp8zf
created_at: 2026-11-04T04:17:30.574Z
updated_at: 2026-11-04T04:33:10.324Z
---
NormalfullMakeverify539failsoneoldsourceextractor:tests/test_browser_client_filestore.py81 expects exactfunctionformatAge(mtimeSec), but fifthlayeraddsoptions forrelativeages.4757passed9expectedskips; no productfailure. Fix extractionboundaryonly whilepreservingnullpending/tally assertions, in owningfifthbranch soits standaloneCIpasses; forwardcommit andmergefifthinto sixth, no historyrewrite. Verifyallproduction src bytesunchanged, rerunnormalfullgate/newexactwheelacceptance; old539failedreceipt retained.

## Notes

Fixed in owning fifth-layer forward commit 043f9246, merged normally into sixth bdf765c6. Only test extractor prefix changes; 600-character slice and both assertions remain intact. Production src identical b85→043 and all341 payload hashes identical539→bdf.70 focused module checks passed; fresh exact-bdf wheel passed8 public live tests/0skips and93 browser checks. Aggregate normal make verify is running; no merge authorized.
