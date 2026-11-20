---
type: is
id: is-01m7r5cmz107gb7jxq0y6pp7fe
title: "Spec: switch folders in a macOS app window"
kind: epic
status: open
priority: 2
version: 23
spec_path: docs/project/specs/active/plan-2026-11-18-macos-folder-switching.md
refs:
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/565
    at: 2026-11-20T17:03:47.586Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/566
    at: 2026-11-20T17:03:47.588Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/568
    at: 2026-11-20T17:03:47.588Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/575
    at: 2026-11-20T17:03:47.588Z
  - kind: pr
    url: https://github.com/jlevy/metabrowser/pull/578
    at: 2026-11-20T17:03:47.588Z
delegate: claude-code@spud10
labels:
  - linear
dependencies: []
child_order_hints:
  - is-01m7r5cnfs2h2yhkcgj238s73w
  - is-01m7r5cnya426kax3rszcj3h2w
  - is-01m7r5cpdc6a2t69qm9095k7yk
  - is-01m7r5cpw7ydejcrrp3m5myfa5
  - is-01m7r5cqbfnb75d2301fykkfxy
  - is-01m7r5cqvfrxqwbh4cz8y07f4j
  - is-01m7r78htyngg4yffcrhha72r2
  - is-01m7razn2kfrd1sxxr84zpz716
  - is-01m7razpm14gejs9ar57kfagbs
  - is-01m7razs4t61pc2b14a8y36818
  - is-01m7raztsv2t8kvjfvjetcb8yd
  - is-01m7razw0sk5h1jjkamx3a5wsw
  - is-01m7regj6mpxdzr60zmvmp0fhw
  - is-01m7regx59vw3j1t4rk8v6j25b
  - is-01m7ressh43myae3chm9e1hvf8
  - is-01m7revap56remwa88vj1n6xj9
hold: null
hold_until: null
created_at: 2026-11-18T20:25:51.840Z
updated_at: 2026-11-20T17:17:37.219Z
started_at: 2026-11-18T20:58:34.140Z
---
A window shows any open folder in place; folders a window switches away from stay open in the background; the title is a native chooser of open and recent folders with an always-shown chevron and a hover surface; a native switcher panel; marks shared with the page. Native chrome, design-system content. Draft awaiting the owner's answers to Q1-Q5.

## Notes

2026-11-20 audit: moved from in_progress back to open. The stack (#565 plan, #566, #568, #575, #578) is merged and no PR is open; the description's 'Draft awaiting the owner's answers' is superseded. What remains is mb-89bu (app tests, live tests and screenshot set), mb-q2hc (an app test target), mb-6ccy (stays open until the hand checks are run), mb-so7f (rename the window-named page events), and mb-bvla (keep the open-folder order across a relaunch).

2026-11-20 audit: Folder switching merged (#565-#578). The four open children and mb-bvla are test, parity-hand-check and rename follow-ups.
