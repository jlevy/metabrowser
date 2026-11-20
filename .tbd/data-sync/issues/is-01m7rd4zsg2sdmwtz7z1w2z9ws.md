---
type: is
id: is-01m7rd4zsg2sdmwtz7z1w2z9ws
title: Serve mode binds its port before it prints the Serving line
kind: bug
status: open
priority: 2
version: 2
spec_path: docs/project/specs/active/plan-2026-11-17-open-anything-from-cli-and-app.md
labels: []
dependencies: []
parent_id: is-01m7nnxhaqce1g2ewec3wbaf7e
created_at: 2026-11-18T22:41:29.390Z
updated_at: 2026-11-20T17:01:27.186Z
---
Found in review A of jlevy/metabrowser#582 (A1). cli/serve.py finds a free port with find_available_local_port (server_utils.py), which binds and releases it, then prints 'Serving <root> at <url>' before uvicorn runs the lifespan and binds the port. Two servers started together can therefore print the same address; the one that binds second exits 1. Readers of the line race: --present's browser delivery (cli/present.py serve_detached) and the macOS app's CLIServeLaunch. #582 makes --present wait until the address answers GET /api/identity for the target's root, which tells servers of different roots apart, but not two servers of the same root. Fix: bind the listening socket before printing the line and hand it to uvicorn (Server.run(sockets=[sock])), retrying the next port when the bind fails. Not done in #582 because it changes every serve start: wildcard and IPv6 hosts, --remote, the app's servers, uvicorn's bind_socket calling sys.exit on failure, and the Ctrl-C windows _run_until_interrupted covers. Done when a server that prints the line holds the port, with a test that starts two servers on one port and sees two addresses.

## Notes

2026-11-20 audit: absorbs mb-5tcg (deferred from PR #541 review A19, closed as a duplicate): the Serving line can appear before the listening socket accepts, so an agent connecting at once is refused. Once the socket is bound before the line prints, drop the skill's retry advice. Checked on origin/main (ab64b5c86): cli/serve.py still finds the port with find_available_local_port and prints Serving before uvicorn binds.
