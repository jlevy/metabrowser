---
type: is
id: is-01m7nnxqk729cfx3vnqv22nryh
title: "App: RootIdentity replaces the local-path session key"
kind: feature
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
labels: []
dependencies:
  - type: blocks
    target: is-01m7nnxrj9txmcjawfmkz6frad
  - type: blocks
    target: is-01m7nnxtkffq4pxbm414fj6ef5
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
created_at: 2026-11-17T21:17:05.510Z
updated_at: 2026-11-18T20:21:03.657Z
closed_at: 2026-11-18T20:21:03.652Z
close_reason: "Landed in jlevy/metabrowser#539 as SessionRoot (apps/macos/Sources/ShellCore/Folders/SessionRoot.swift): a folder path or canonical repository URL, never the pin (changed shape: no pin in the key); session map, log name (FolderSession.path), pre-ready title (SessionRoot.identity) and launch lane use it. SavedTab.root stays a folder path because repository tabs are not saved; saving them is mb-682q."
resolution: null
duplicate_of: null
---
Phase 1, apps/macos. A root is a canonical local path or a source (canonical repository URL plus pin). Move session map, log names, pre-ready title, SavedTab.root, and runtime-waiting folders behind it.
