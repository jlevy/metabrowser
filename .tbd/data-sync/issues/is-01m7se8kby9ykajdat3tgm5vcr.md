---
type: is
id: is-01m7se8kby9ykajdat3tgm5vcr
title: "PR and commit pages: narrow main views hide the PR title and pad every line of a long commit subject"
kind: task
status: open
priority: 3
version: 3
labels: []
dependencies: []
created_at: 2026-11-19T08:20:10.740Z
updated_at: 2026-11-19T08:53:57.980Z
---
From #608 review A6 (pre-existing): in a 260 px main view the PR title text is invisible (github/styles.css:53 corner room leaves ~0 px), and a long commit subject gets the 150 px corner room on every line (styles.css:7446). Give PR and commit pages the narrow fallback, or the first-line float #608 uses for files and folders.
