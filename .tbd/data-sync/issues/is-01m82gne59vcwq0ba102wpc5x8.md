---
type: is
id: is-01m82gne59vcwq0ba102wpc5x8
title: "metab --host :: (and any IPv6 host) cannot serve: the port search binds an AF_INET socket"
kind: bug
status: in_progress
priority: 3
version: 2
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-22T20:55:18.437Z
updated_at: 2026-11-22T21:03:35.910Z
started_at: 2026-11-22T21:03:35.908Z
---
The --host help in src/metabrowser/cli/main.py advertises wildcard binds including '::', but local_port_is_free / listen_on_available_local_port in src/metabrowser/server_utils.py always create socket.AF_INET sockets, so bind(('::', port)) raises gaierror for every port and serve fails with 'No available port'. This predates #699 (the old probe was AF_INET too). Fix: choose the family from getaddrinfo(host), or remove the IPv6 claim from the help. Found reviewing #699 on 2026-11-22.
