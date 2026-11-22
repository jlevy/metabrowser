---
type: is
id: is-01m82gne59vcwq0ba102wpc5x8
title: "metab --host :: (and any IPv6 host) cannot serve: the port search binds an AF_INET socket"
kind: bug
status: in_progress
priority: 3
version: 3
delegate: claude-code@spud10.local
labels: []
dependencies: []
hold: null
hold_until: null
created_at: 2026-11-22T20:55:18.437Z
updated_at: 2026-11-22T21:31:50.422Z
started_at: 2026-11-22T21:03:35.908Z
---
The --host help in src/metabrowser/cli/main.py advertises wildcard binds including '::', but local_port_is_free / listen_on_available_local_port in src/metabrowser/server_utils.py always create socket.AF_INET sockets, so bind(('::', port)) raises gaierror for every port and serve fails with 'No available port'. This predates #699 (the old probe was AF_INET too). Fix: choose the family from getaddrinfo(host), or remove the IPv6 claim from the help. Found reviewing #699 on 2026-11-22.

## Notes

2026-11-22: fix in PR #703 (branch claude/serve-ipv6-host), not merged. listen_on_available_local_port takes the socket family from getaddrinfo(host), IPv4 first for a name of both families; '::' listens dual-stack (IPV6_V6ONLY cleared) and prints 127.0.0.1; an IPv6 literal is bracketed in the banner URL and in the Host allowlist; a host with no address fails with 'Cannot listen on host'. --remote's probe stays IPv4. Tests: tests/test_serve_ipv6_host.py, tests/test_server_utils.py, tests/test_host_validation.py. Leave open until #703 merges.
