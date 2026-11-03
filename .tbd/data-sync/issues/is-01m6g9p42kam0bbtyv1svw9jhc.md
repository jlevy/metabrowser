---
type: is
id: is-01m6g9p42kam0bbtyv1svw9jhc
title: "PR #288 B3: align served-repository architecture with checkout support"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m6g5eqdtdmc5pj1eb9ryy6s1
created_at: 2026-11-03T08:51:19.250Z
updated_at: 2026-11-03T08:51:19.250Z
---
Independent review Low: current behavior section at arch-repository-sources-and-provider-mirrors.md still says StoreMirror is sole GitHub source and folders answer not_github, contradicting checkout origin fallback added immediately below. Update current contract, retain documented read-only/network constraints.
