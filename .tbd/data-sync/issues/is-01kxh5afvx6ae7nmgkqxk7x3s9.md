---
type: is
id: is-01kxh5afvx6ae7nmgkqxk7x3s9
title: Load dotenv before serve root expansion
kind: bug
status: closed
priority: 1
version: 3
labels: []
dependencies: []
created_at: 2026-07-14T20:33:01.820Z
updated_at: 2026-07-14T20:41:15.814Z
closed_at: 2026-07-14T20:41:15.814Z
close_reason: "Serve now loads dotenv before log selection, plugin discovery, and root expansion; focused regression passes, make verify reports 618 passing tests, and PR #1 CI is green."
---
PR #1 review found that serve expands a home-relative root before loading .env files, so dotenv-provided HOME is ignored. Load the dotenv chain before all configuration and path expansion, and add a regression test.
