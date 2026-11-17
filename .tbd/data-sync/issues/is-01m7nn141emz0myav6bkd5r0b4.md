---
type: is
id: is-01m7nn141emz0myav6bkd5r0b4
title: "Follow-up to #523 review B: record the owner's cool-off waiver for the picomatch fix (B1), classify only npm's error shape as an outage (B2), test all four root dependency maps (B3), fix the fixAvailable:false message (B4)"
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
created_at: 2026-11-17T21:01:27.976Z
updated_at: 2026-11-17T21:01:27.976Z
---
From security review B of jlevy/metabrowser#523 at b0ddbf1. B1: owner decided 2026-11-17 in chat to waive the 14-day cool-off for the picomatch release that fixes GHSA-fc5q-39xc-vjpf, after a hand review of its diff (as first-party rows are reviewed); write that into SUPPLY-CHAIN-SECURITY.md's removal conditions and mb-p1o0. B2: devtools/npm_audit.sh:61 greps the answer as well as stderr after NOT_A_REPORT; take option (a) search stderr only, or (b) return NOT_A_REPORT only for npm's error shape. B3: parametrize tests/test_npm_audit.py's root-dependency case over all four dependency maps. B4: for fixAvailable false, say npm could not work out a fix and to rerun.
