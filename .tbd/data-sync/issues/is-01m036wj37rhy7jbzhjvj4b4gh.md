---
type: is
id: is-01m036wj37rhy7jbzhjvj4b4gh
title: Bare origin was a second, empty spelling of the served root
kind: bug
status: closed
priority: 1
version: 2
spec_path: docs/project/specs/done/plan-2026-08-13-markdown-link-navigation.md
labels: []
dependencies: []
created_at: 2026-08-15T17:18:05.926Z
updated_at: 2026-08-15T17:18:11.297Z
closed_at: 2026-08-15T17:18:11.296Z
close_reason: Fixed and verified in a browser on claude/internal-links-url-scheme-rbz0f5; make verify green.
---
Replacing the hash router removed the server-side initial-README preview, so GET / rendered an empty 'Select a file to preview.' pane while /view/ rendered the root folder view. Three entry points reached that dead end: the / route itself, the header 'Jump to root' link, and the metab startup banner, which printed a bare http://host:port whenever no --path was selected (the default invocation).

Fixed on claude/internal-links-url-scheme-rbz0f5: / now issues a temporary 307 to /view/, the header link and CLI banner emit the canonical route, and tests cover all three plus the regenerated serve-banner golden.
