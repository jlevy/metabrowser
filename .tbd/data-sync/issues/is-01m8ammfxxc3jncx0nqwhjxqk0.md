---
type: is
id: is-01m8ammfxxc3jncx0nqwhjxqk0
title: "Commits tab: choosing an origin branch on a checkout swaps its refs for the store's"
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-26T00:38:37.244Z
updated_at: 2026-11-26T00:38:37.244Z
---
Found reviewing PR #857. On a checkout with an origin store, choosing an origin branch or tag sets read_from='origin' (checkout_revisions.py:592), so every Git route reads the store: /api/git/refs and scope=all then list only the store's refs, and the checkout's local branches and HEAD lane vanish. Before #857 a checkout's Commits tab always showed its own refs. Fix: show the checkout's refs alongside the store's when the chosen revision is read from the store (the checkout may lack the store's newer commits, so decorate only refs whose commits are present, or read refs from both).
