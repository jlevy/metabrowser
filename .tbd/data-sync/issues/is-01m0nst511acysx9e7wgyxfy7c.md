---
type: is
id: is-01m0nst511acysx9e7wgyxfy7c
title: "File header: tilde-expand a served root under the home directory"
kind: feature
status: open
priority: 2
version: 1
labels: []
dependencies: []
parent_id: is-01m0ndp6h7a3hx27zbswtknk89
created_at: 2026-08-22T22:35:09.728Z
updated_at: 2026-08-22T22:35:09.728Z
---
Requested: render a served root under the user's home directory as `~/...` rather than the absolute path, to spend less of the header's width on a prefix that is the same on every page.

`/Users/someone/wrk/github/projectname` becomes `~/wrk/github/projectname`, which is 12 characters shorter here and more on a longer username.

Display only. The absolute root still rides on `data-served-root` and in the anchor title, and nothing about navigation or the API changes -- paths on the wire are relative to the root already.

Decide where it happens: the server knows the home directory and the browser does not, so this is most likely a server-side display field rather than a browser guess. Windows and a root-owned or non-home root need to fall through to the absolute path unchanged.
