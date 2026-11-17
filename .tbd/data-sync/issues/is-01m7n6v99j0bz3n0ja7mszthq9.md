---
type: is
id: is-01m7n6v99j0bz3n0ja7mszthq9
title: "Diff summaries: prefetch eagerly and answer from the last persisted cache file first"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
created_at: 2026-11-17T16:53:36.689Z
updated_at: 2026-11-17T16:53:36.689Z
---
Prefetch diff summaries for the pull requests visible in the Pulls nav and the selected one, persist them as files in the repository cache (home.py / cache helpers, the GitHub plugin's refresh machinery), and answer from the last persisted version first with refreshes layered on top, so rows and the PR page show a current or recent value at once. CLI parity: any new route or persisted state gets a metab equivalent and golden.
