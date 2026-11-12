---
type: is
id: is-01m78fvwszg5ctcvezzfg5tnnp
title: Declare compatible ranges for Metabrowser's library dependencies
kind: task
status: open
priority: 2
version: 1
spec_path: docs/project/specs/active/plan-2026-11-12-plugin-sources.md
labels: []
dependencies: []
parent_id: is-01m78ftefp9ks9100ebsm7sm29
created_at: 2026-11-12T18:21:06.238Z
updated_at: 2026-11-12T18:21:06.238Z
---
Independent fix (plan: Implementation Plan, Independent fix). Replace exact pins on library dependencies (softschema==0.8.1, kpress==0.3.5, markdown-it-py==4.2.0) with compatible ranges such as softschema>=0.8.1,<0.10, keep exact versions in uv.lock, and add a CI job that installs beside a package needing the newer end of each range. Reproduced: metabrowser==0.12.0 with softschema>=0.9.1,<0.10 has no solution (research brief, Installing into Metabrowser's Environment Fails on Exact Pins). Helps plugins that stay in Metabrowser's environment; not a prerequisite for the rest of the epic.
