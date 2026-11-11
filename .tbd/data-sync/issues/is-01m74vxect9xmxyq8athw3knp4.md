---
type: is
id: is-01m74vxect9xmxyq8athw3knp4
title: "PR #347 B2: security headers are attached at each return, not on every response from the path"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m74vwmegp0f11eb7vj9pnq0t
created_at: 2026-11-11T08:34:42.201Z
updated_at: 2026-11-11T09:41:56.581Z
closed_at: 2026-11-11T09:41:56.580Z
close_reason: "fixed in ecdaaa51: every response leaves through one exit that adds the policy; test over each status and mode"
resolution: null
duplicate_of: null
---
Severity: Low. PR #347 review B round 1 at 8dd80d0c (https://github.com/jlevy/metabrowser/pull/347#pullrequestreview-5855525387). References: pull_snapshot.py:34-42, :149-157, :213-223, :303-305, :311-315.
