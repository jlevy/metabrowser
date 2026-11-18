---
type: is
id: is-01m7pr9vw086ntmjbhs35vhxe3
title: "macOS app: the owner's File menu, Open Folder…, Open URL…, and Open Recent"
kind: feature
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m7ksbn803jhw15qjc6beg7qf
created_at: 2026-11-18T07:17:54.687Z
updated_at: 2026-11-18T20:02:17.564Z
closed_at: 2026-11-18T20:02:17.563Z
close_reason: "Merged in #560 (a1100bca6)"
resolution: null
duplicate_of: null
---
The owner specified the File menu on 2026-11-18: Open Folder… (a folder or a file, a checkout included), Open URL… (a supported GitHub URL), and Open Recent (any recent item). The open-modes design states it under The File Menu (docs/project/architecture/arch-open-modes.md, #558). Open Recent is built by #546 (mb-40k4). Left: rename File > Open… to Open Folder… with docs/macos-app.md and the hand checks in docs/project/qa/qa-macos-app-hand-checks.md, and add Open URL…, which is mb-m4mg (after #539). Review A13 on #546 found that no work item carried the menu; plan-2026-11-10-native-macos-app.md Phase 4 now names this bead.
