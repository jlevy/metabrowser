---
type: is
id: is-01m7kvt7d6bw66wcfjfyke5t3m
title: "PR #496 review B1: the merge procedure's test does not show the run tested the red main"
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-11-16-fast-ci.md
labels: []
dependencies: []
parent_id: is-01m7kvt6zsgb9m5xpanazw7prr
created_at: 2026-11-17T04:21:33.222Z
updated_at: 2026-11-17T04:23:03.085Z
closed_at: 2026-11-17T04:23:03.084Z
close_reason: "Fixed in 008a68b9 as the coordinator decided: merge only once main's newest run has finished; while red, only a pull request whose latest run was triggered after the red commit landed and ran the whole matrix (plan job's tests-red, by git merge-base --is-ancestor); reruns of older runs do not qualify; auto-merge never armed; up-to-date branches a Q5 owner option. In the plan and mb-oz36."
resolution: null
duplicate_of: null
---
plan:261-263, :266-274, :723-724, :749-752 at 8b4da0cb; mb-oz36. A rerun of a pre-red run, a main run still going, and auto-merge each get a pull request onto a red or unverified main.
