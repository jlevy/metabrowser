---
type: is
id: is-01m0h1nftt0z940hj2p13rmsn1
title: "PR #59 review R4: tbd npx fallback fails for 14 days after every tbd release"
kind: bug
status: open
priority: 3
version: 4
labels:
  - upstream-tbd
dependencies: []
parent_id: is-01m0h1neycr90x9zn2evw9vnjq
created_at: 2026-08-21T02:16:13.402Z
updated_at: 2026-08-21T05:40:31.292Z
---
PR #59 review R4 (High). Reproduced live on 2026-08-21:

  $ npx --yes "get-tbd@0.7.1" --version
  npm error code ETARGET
  npm error notarget No matching version found for get-tbd@0.7.1 with a date before ...

  $ npx --yes --min-release-age=0 "get-tbd@0.7.1" --version
  0.7.1

.npmrc sets min-release-age=14 and npm has no per-package exclusion, so the
generated hook invocation fails for fourteen days after every tbd release.
Reached only when the local tbd CLI is missing or format-incompatible.

Not fixed in this repository, deliberately: the four hook scripts are generated
by `tbd setup`, and patching them is what the 0.7.0 and 0.7.1 upgrades each
reverted. Documented as an accepted cost in SUPPLY-CHAIN-SECURITY.md and in the
Dependencies section of docs/development.md.

The fix belongs in tbd's generator: emit `--min-release-age=0` on the pinned
first-party npx invocation, or have the wrapper retry once on ETARGET. Until
then, `npm install -g get-tbd@latest` avoids the path entirely.
