---
type: is
id: is-01m7sbpz9mdrvheykpf8de1wkh
title: "Commit body trailers: a hyphenated closing prose line (e.g. 'Follow-up: ...') is muted as a trailer"
kind: task
status: open
priority: 4
version: 1
labels: []
dependencies: []
created_at: 2026-11-19T07:35:35.987Z
updated_at: 2026-11-19T07:35:35.987Z
---
From #603's trailer rule (git/message.py _known_trailer): any hyphenated token counts as known, so a last paragraph that is a single 'Follow-up: we should ...' line renders muted pre-wrap instead of Markdown. Consider a known-hyphenated list (Signed-off-by, Co-Authored-By, Change-Id, Reviewed-by, Acked-by, Tested-by, Reported-by, Suggested-by, Claude-Session) or requiring a value shape (name <email>, URL, ID).
