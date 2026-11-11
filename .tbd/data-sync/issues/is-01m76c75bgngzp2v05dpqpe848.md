---
type: is
id: is-01m76c75bgngzp2v05dpqpe848
title: "PR #352 B1: Separate web data stores do not restrict where their cookies are sent"
kind: bug
status: closed
priority: 1
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
parent_id: is-01m76c6vcvp3rkctrfv1ykv9qz
hold: null
hold_until: null
created_at: 2026-11-11T22:38:52.271Z
updated_at: 2026-11-11T22:41:10.203Z
started_at: 2026-11-11T22:38:58.517Z
closed_at: 2026-11-11T22:41:10.202Z
close_reason: "fixed in 5136540f: every client's credential, native web views included, must be bound to its origin (distinct loopback host name with host-only cookies, or a non-cookie header token held per origin); a data store per trust profile kept for preferences and storage only; new topology falsifiable claim 4, plan mb-qzny item, and Testing Strategy bullet require a cross-port subresource, redirect, and navigation check in WKWebView, Safari, and Chrome; Show X, Phase 1, and the Nov 8 addendum agree. Confirmed by pinned flowmark check, public_hygiene, test_docs_discipline (4 passed), link check, and a re-read."
resolution: null
duplicate_of: null
---
High. PR #352 review B (https://github.com/jlevy/metabrowser/pull/352#pullrequestreview-5866200355); follows A1 (mb-rv0j). docs/project/research/research-2026-11-10-native-app-server-topology.md:630 claims a per-profile WKWebsiteDataStore keeps a token among servers of one profile, but the store belongs to the requesting view: a page on one port sends its cookies on subresource requests to another port. Trusted shells have no CSP (src/metabrowser/server.py:1942) and trusted renders use innerHTML (src/metabrowser/builtin_plugins/markdown/place-rendered.js:38). Fix: origin-bound credentials for every client including native, carried into host mode (mb-qzny), with a WebKit cross-port request check.
