---
type: is
id: is-01kzsd1epcab6ghygv2syte5he
title: Remove duplicate Quick Find instructions and audit nearby status copy
kind: bug
status: in_progress
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01kzrtbtsh9k6p8x84rta84y4p
created_at: 2026-08-11T21:53:13.419Z
updated_at: 2026-08-11T22:01:56.764Z
---
Quick Find repeats the input instruction in both its placeholder and its status line. Reproduce the visible states, make the status line report scope or state instead of repeating how to type, and audit nearby user-facing messages for duplicated instructions or unnecessary verbosity. Add behavior coverage and validate in the browser.

## Notes

Reproduced the duplicate placeholder and idle status in the live Quick File dialog. Revised Quick File copy so the placeholder owns input guidance, idle status reports scope, delayed progress reports active work, and completion reports match count or an explicit empty result. Standardized search and open-file recovery wording, shortened the truncation note, localized count formatting, expanded the design system with a mandatory Chrome-copy review policy, and updated the scalable-search contract. Repository-wide placeholder/status audit found no other adjacent placeholder duplication. make verify passes with 886 tests and 28 golden cases; live browser states show the new scope and match copy.
