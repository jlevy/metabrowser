---
type: is
id: is-01kzz4dty54dvgw9q1aqf3s811
title: "Links B: Enhance rendered Markdown links, resources, and fragments"
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz4dv7aj7xk3d44d0h4f7fr
parent_id: is-01kzz03fwfcvam3ft3zvfwqx7g
created_at: 2026-08-14T03:18:08.580Z
updated_at: 2026-08-14T04:06:30.324Z
---
Enhance completed KPress mounts using the typed resolver. Give safe internal anchors real /view/ hrefs, map local images and media through bounded raw-resource URLs, preserve external targets and target/download/modifier/middle/keyboard behavior, intercept only unmodified primary internal clicks through metabrowser.navigation, and scroll fragments only after the current async render. Return a disposer for listeners and pending work and add DOM, accessibility, abort, and replacement tests.
