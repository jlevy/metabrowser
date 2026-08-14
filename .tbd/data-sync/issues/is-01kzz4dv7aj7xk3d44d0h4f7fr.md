---
type: is
id: is-01kzz4dv7aj7xk3d44d0h4f7fr
title: "GitHub A: Build the repository link-resolution fixture matrix"
kind: task
status: in_progress
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzz4dvgrdq6g9fmsejnhrx0g
parent_id: is-01kzz03g4npz4pma4px6mdq2s0
created_at: 2026-08-14T03:18:08.870Z
updated_at: 2026-08-14T04:13:07.980Z
---
Complete tests/fixtures/markdown_link_resolution.json and a GitHub-style repository fixture covering inline, reference, raw-HTML, image, resource, folder, root, relative, query, heading, missing, hostile, spaces, Unicode, literal percent, and reserved-name cases. Drive pure resolver and DOM cases from the shared matrix where practical and prove exact zero-configuration behavior.
