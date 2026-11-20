---
type: is
id: is-01m7sgg8y7t2z88xxfc54fbktn
title: "View header: a file or folder name wider than 450 px still breaks mid-word beside View on GitHub between 680 px and its width + 230 px"
kind: task
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wysf407hkpj5n35r533gzc
created_at: 2026-11-19T08:59:19.366Z
updated_at: 2026-11-20T17:18:25.408Z
---
From #608 review A1 residual: the corner moves to the eyebrow row below 680 px (--view-header-title-room 450px, holding 91% of this repo's names). Wider names break mid-word beside the corner's first-line float from 680 px to about width + 230 px. Proposed fix: a ResizeObserver first-line check that moves the corner to the eyebrow when the title's unbroken width exceeds its first line beside the room.
