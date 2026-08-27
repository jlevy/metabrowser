---
type: is
id: is-01m12ngtf7k5nmzrh15gtbt2qr
title: Record the aggregate history spool ceiling and its tmpfs consequence
kind: chore
status: open
priority: 3
version: 1
labels: []
dependencies: []
created_at: 2026-08-27T22:30:17.307Z
updated_at: 2026-08-27T22:30:17.307Z
---
GIT_HISTORY_SESSION_MAX_STORAGE_BYTES = 64 MiB is enforced per session (git/history.py:637) and handed to each new session (git/history.py:886). With GIT_HISTORY_SESSION_MAX_ENTRIES = 8 the aggregate ceiling is 512 MiB, which is not stated beside the per-session constant the way its measurement is. The spool directory is created with no dir= (git/history.py:463-466), so it lands in tempfile.gettempdir(); on many Linux distributions /tmp is tmpfs, meaning that budget is RAM rather than disk. Bounded, idle-reaped, and released on shutdown, so this is a documentation fix in settings.py, not a defect. Raised on https://github.com/jlevy/metabrowser/pull/86#issuecomment-5445472421
