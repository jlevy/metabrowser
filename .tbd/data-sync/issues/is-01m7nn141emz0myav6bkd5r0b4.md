---
type: is
id: is-01m7nn141emz0myav6bkd5r0b4
title: "Follow-up to #523 review B: record the owner's cool-off waiver for the picomatch fix (B1), classify only npm's error shape as an outage (B2), test all four root dependency maps (B3), fix the fixAvailable:false message (B4)"
kind: task
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
created_at: 2026-11-17T21:01:27.976Z
updated_at: 2026-11-18T00:36:49.666Z
closed_at: 2026-11-18T00:36:49.665Z
close_reason: "Overtaken by #538 (merged b537e30db): the #523 exception is removed, so B1/B3/B4 no longer apply; B2 (classify only npm's error shape as an outage) is fixed in #538's b32735edd with tests"
resolution: null
duplicate_of: null
---
From security review B of jlevy/metabrowser#523 at b0ddbf1. B1: owner decided 2026-11-17 in chat to waive the 14-day cool-off for the picomatch release that fixes GHSA-fc5q-39xc-vjpf, after a hand review of its diff (as first-party rows are reviewed); write that into SUPPLY-CHAIN-SECURITY.md's removal conditions and mb-p1o0. B2: devtools/npm_audit.sh:61 greps the answer as well as stderr after NOT_A_REPORT; take option (a) search stderr only, or (b) return NOT_A_REPORT only for npm's error shape. B3: parametrize tests/test_npm_audit.py's root-dependency case over all four dependency maps. B4: for fixAvailable false, say npm could not work out a fix and to rerun.
