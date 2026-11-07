---
type: is
id: is-01m6th4q8ppch1rc8h9varn3pt
title: Use one visible content gutter for Markdown and Source
kind: bug
status: in_progress
priority: 1
version: 3
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
hold: null
hold_until: null
created_at: 2026-11-07T08:14:02.005Z
updated_at: 2026-11-07T08:50:53.115Z
started_at: 2026-11-07T08:14:58.209Z
---
User reports rendered Markdown/card content flush against pane edge despite the previous left-alignment change. Apply the same visible outer gutter/padding to Source and rendered Markdown, aligned with the first display tab. Include standalone documents, the Overview README, wide TOC and narrow drawer behavior. Measure both outer surfaces and text inset so card padding cannot conceal a missing pane gutter; update the design documentation and verify installed build.

## Notes

Acceptance clarified by owner: the card BORDER aligns with the left edge of the first display TAB BOX. Preserve KPress normal responsive padding INSIDE the card (4rem medium /2.5rem wide, compact native narrow gutter); do not force prose onto the tab label. The temporary 9a candidate inset12 was superseded by forward fix7c0188f4. Corrected exact wheel0.11.1.dev1218+7c0188f4 installed; verified8411 CHANGELOG border323.99 matches tab323.99, inner padding40px and text measure662px. Source/Raw share outer24px while retaining original code-block inner padding. Overview matches native bands. Focused layout/source/SDK/print checks pass; independent review approves. Replaced the verified old8411,8863,8864 servers with defaults preserved. Final combined stack gate/PR/CI still pending with other feature layers.
