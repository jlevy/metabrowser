---
type: is
id: is-01m6f2cps040spx689cbdwfezp
title: A refused .env key name reaches the terminal unsanitized, so a repository can write escape sequences to stderr
kind: bug
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-11-02T21:24:36.253Z
updated_at: 2026-11-02T21:24:36.253Z
---
Found 2026-11-02 by the security review of PR 274, outside that layer, on main. src/metabrowser/dotenv.py near lines 133-139 logs refused .env key names and the file path as they are. Reproduced: a key METABROWSER_<ESC>[31mRED<ESC>[0m=1 puts raw ESC bytes on stderr, so a browsed repository can colour or erase the one warning line that reports its names were ignored. The package's own loggable helper in src/metabrowser/git/process.py near lines 329-344 is the fix and is not applied there. The golden added by PR 274 exercises this line only with benign names.
