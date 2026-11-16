---
type: is
id: is-01m7jpaams522c71rjkqnjj04t
title: "PR #477 A1: Home leaves the Pulls list's closed stacks, opened files, and roving row as the reader left them"
kind: bug
status: closed
priority: 2
version: 3
delegate: claude-code@macbookpro
labels: []
dependencies: []
parent_id: is-01m7jjcfgz5r5ykt72449xb6as
hold: null
hold_until: null
created_at: 2026-11-16T17:26:14.933Z
updated_at: 2026-11-16T17:46:10.993Z
started_at: 2026-11-16T17:28:18.758Z
closed_at: 2026-11-16T17:46:10.992Z
close_reason: "Fixed in c1b48908d (PR #477 review A): optional MetabrowserNavPanel.home called by main-tabs.js goHome for every panel; Files resetFilesTab, Pulls closes rows' files, opens every stack, Tab stop to the first row; stack-groups, pulls-nav, preview sessions and goldens, Chrome route (fails without the reset); docs no longer list them as kept. Disposition reply: https://github.com/jlevy/metabrowser/pull/477#issuecomment-6924312625"
resolution: null
duplicate_of: null
---
Medium. main-tabs.js goHome resets no mounted panel state; pulls-panel.js closedStacks, anchorChosen/anchor, expansion; docs CHANGELOG.md:7-10, design-system.md Home, plan Phase 26 say exactly. Review A (round 1), PR #477: https://github.com/jlevy/metabrowser/pull/477#pullrequestreview-5923748713
