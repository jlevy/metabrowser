---
type: is
id: is-01m6c49cy0mdpx3e4gp3f7fz0q
title: A visible tooltip whose anchor is removed after the delay stays up
kind: bug
status: open
priority: 4
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-11-01T18:00:01.727Z
updated_at: 2026-11-01T18:00:01.727Z
---
Found 2026-11-01 while fixing mb-0oxi in PR #275, which covers removal during the 300 ms delay only. Removal after the tooltip has shown still leaves it up until the next hover.
