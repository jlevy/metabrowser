---
type: is
id: is-01m7sbwjvm0smmadqp4w4ch1qr
title: "macOS script check: quarantine helper leaves no agent name when run from an agent session"
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-19T07:38:39.860Z
updated_at: 2026-11-20T17:21:11.122Z
---
Locally, make -C apps/macos test (scripts/test-scripts.sh, 'The quarantine helper') failed on 2026-11-18 from a Claude Code session: the helper said 'simulated' then 'already', but com.apple.quarantine read '0281;6afea74a;;<uuid>', with an empty agent name, so describe_quarantine did not find 'by Metabrowser check-release (simulated download)'. Seen on PR #606's branch, which does not touch the scripts; every Swift suite passed. Check whether CI and a plain terminal pass, and whether the agent's sandbox strips the agent name.
