---
type: is
id: is-01m0tybhfzk2t62dtnbzkhzzyg
title: Preserve deterministic order when loading multiple plugins for one kind
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies:
  - type: blocks
    target: is-01m0vcqjmdqs2zhk804rgbjjm9
parent_id: is-01m0txqcnz6aef2rzesn4cmy5w
created_at: 2026-08-24T22:30:46.014Z
updated_at: 2026-08-25T02:42:00.460Z
---
Release-readiness finding on main c123ae6. loadPluginsForKind starts all descriptors with Promise.all, so network and module completion order decides which registerView call wins when two plugins register the same kind/view. The server constructs manifest views in stable discovery order and last-write-wins, so the renderer can disagree with the selected manifest entry. Load descriptors sequentially in server order and add a delayed two-plugin collision test.
