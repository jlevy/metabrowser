---
type: is
id: is-01m7p8gh7a2s4aqast5pe3ferp
title: "Diff summary placeholder: keep one reveal and pulse through a cold landing on Changes"
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m7n6v8n050erzeb13c5tasar
created_at: 2026-11-18T02:41:55.945Z
updated_at: 2026-11-18T02:41:55.945Z
---
On a cold /pull/N/files landing, the record's paint removes the Diff summary's pending placeholder (paintSummaryWait sees diffFor null and the record branch's comparisonComing false) and mountDiff's summaryReading reinserts the same node in the same task, which restarts its .mb-delayed-loading reveal and .tally-pending pulse. Predates #532 for a pending core on Changes; #532 makes it every cold Changes landing. Found by review A on #532 (A2). Fix: while Changes has no diff mounted yet but will mount one for the record's comparison, keep the placeholder; add a cold Changes case to headerSummary and a Chrome check on the animation's startTime across the landing.
