---
type: is
id: is-01m7nazd8r0g7bx08cyhvcxhyp
title: Remove the npm audit exception for GHSA-fc5q-39xc-vjpf (picomatch ReDoS via tryscript)
kind: task
status: closed
priority: 2
version: 7
labels:
  - linear
dependencies: []
created_at: 2026-11-17T18:05:46.135Z
updated_at: 2026-11-20T17:00:13.645Z
closed_at: 2026-11-18T00:36:49.258Z
close_reason: "Done in jlevy/metabrowser#538 (merged b537e30db): tryscript 0.4.0 removes picomatch; the #523 exception is deleted"
resolution: null
duplicate_of: null
---
The npm audit gate tolerates exactly one advisory, GHSA-fc5q-39xc-vjpf (high, picomatch ReDoS through single-branch repeated extglobs, affects picomatch <= 4.0.7, no patched release when the exception was taken on 2026-11-17). The owner approved the narrow exception on 2026-11-17; mb-3ncz is the CI failure it resolves.

It is reached only through the dev dependency tryscript 0.3.1 -> tinyglobby 0.2.17 -> fdir 6.5.0 / picomatch 4.0.7, and tryscript only expands the repository's own committed glob patterns (the Makefile's 'tests/golden/*.tryscript.md' and tryscript's built-in ignores), never untrusted input. The exception is held in devtools/npm_audit_exceptions.py, applied by devtools/npm_audit.sh, tested in tests/test_npm_audit.py, and recorded in SUPPLY-CHAIN-SECURITY.md.

Remove it when either holds:
- picomatch publishes a release that fixes GHSA-fc5q-39xc-vjpf and that release clears the 14-day cool-off: update package-lock.json to it, confirm npm audit passes with no exception, then delete the exception, its test and fixture, and the SUPPLY-CHAIN-SECURITY.md entry; or
- tryscript (first-party) drops tinyglobby/picomatch or pins a fixed picomatch: take that release under the first-party review in SUPPLY-CHAIN-SECURITY.md, then delete the exception the same way.

The exception lapses by itself, failing the audit, if the advisory's affected range, the installed picomatch version, or the package path npm reports changes; a lapse is a reason to re-review, not to widen the exception.

## Notes

The exception landed with jlevy/metabrowser#523 (branch claude/npm-audit-picomatch-exception, head 7915437bf). It resolves the CI failure mb-3ncz.

2026-11-17, after security review A of #523 (head b0ddbf1): the exception now also lapses when anything else the review rested on changes: the advisory's severity, CWE or CVSS vector; picomatch's fixAvailable (so a published fix lapses it, per removal condition 1); any hop's locked version (picomatch 4.0.7, fdir 6.5.0, tinyglobby 0.2.17, tryscript 0.3.1) or isDirect; or a root dependency on picomatch, fdir or tinyglobby. The full list is the PICOMATCH_REDOS constant in devtools/npm_audit_exceptions.py.

2026-11-17, owner decision (in chat, on review B1 of #523): when picomatch publishes the fix and the exception lapses, waive the 14-day cool-off for that one picomatch release after a hand review of its diff, as first-party releases are reviewed; move the lock at once and delete the exception. Written into SUPPLY-CHAIN-SECURITY.md by mb-vo98.
2026-11-17: tryscript 0.3.2, which drops tinyglobby/picomatch (dependency choice decided by Astra per the owner's criteria), is being released by an agent from a fresh clone in attic/tryscript. When it is on npm: bump tryscript to 0.3.2 as a first-party exception (SUPPLY-CHAIN-SECURITY.md, like 0.3.0/0.3.1) and remove this exception (devtools/npm_audit_exceptions.py, its tests and fixture, the SUPPLY-CHAIN-SECURITY.md section) in the same PR.
