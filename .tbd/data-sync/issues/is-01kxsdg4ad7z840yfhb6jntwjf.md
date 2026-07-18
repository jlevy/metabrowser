---
type: is
id: is-01kxsdg4ad7z840yfhb6jntwjf
title: "Cut v0.1.1: release staged; awaiting GitHub release publication (owner action)"
kind: task
status: open
priority: 1
version: 1
labels: []
dependencies: []
created_at: 2026-07-18T01:29:50.669Z
updated_at: 2026-07-18T01:29:50.669Z
---
Release prep merged to main (7f0a6c8): changelog 0.1.1, skill runner pin 0.1.1, @latest install instructions. make verify green (727 tests), CI green, derived version confirmed 0.1.1 via hatchling. Session git proxy 403s tag pushes and no release-creation API is available, so the owner publishes the GitHub release with tag v0.1.1 on main; publish.yml then trusted-publishes to PyPI. Post-publish: watch workflow, verify PyPI metadata, uvx smoke tests, skill install check.
