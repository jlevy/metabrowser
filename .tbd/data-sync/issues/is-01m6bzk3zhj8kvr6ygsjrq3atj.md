---
type: is
id: is-01m6bzk3zhj8kvr6ygsjrq3atj
title: A served mirror's refresh with no git says the installed Git is older
kind: bug
status: open
priority: 4
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-11-01T16:37:57.360Z
updated_at: 2026-11-01T16:37:57.360Z
---
Found while fixing mb-r0kr in PR #274. static/source-freshness.js near line 58 tells a refresh with no git on PATH that the installed Git is older, because the outcome unsupported_git covers both a missing and an old Git. Reached only if git disappears while a mirror is served. mb-r0kr fixed the acquisition message; this is the same wording on the refresh path.
