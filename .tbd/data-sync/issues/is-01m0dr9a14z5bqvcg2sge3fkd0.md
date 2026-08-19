---
type: is
id: is-01m0dr9a14z5bqvcg2sge3fkd0
title: "Submodules end-to-end: fixture, adapter, apply semantics, corpus"
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-08-19T19:34:33.763Z
updated_at: 2026-08-19T19:34:33.763Z
---
The format models gitlinks (entry_type submodule, mode 160000, content = commit oid) and TreeSnapshot round-trips them, but nothing exercises them end-to-end: the fixture repo has no submodule (use git update-index --add --cacheinfo 160000,<oid>,path plumbing — no network), the adapter never sees one, and apply_file_change needs a decided rule for gitlink content — the new oid is IN the document (new.content.oid), so apply should take it from the content ref directly rather than the resolver or a text patch. Add: fixture submodule bump, adapter taxonomy assertion, corpus validation + apply case, oracle pass. Also decide how the diff view renders a submodule bump (old→new short oid line, like GitHub).
