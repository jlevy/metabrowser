---
type: is
id: is-01m78t1rx3tqb97bqmekmd49kg
title: Remote mode's --ssh-options passes raw SSH flags, so metab cannot be blanket-exempted from an agent sandbox
kind: task
status: open
priority: 2
version: 1
labels: []
dependencies: []
created_at: 2026-11-12T21:19:04.609Z
updated_at: 2026-11-12T21:19:04.609Z
---
metab --remote HOST --ssh-options '<flags>' passes the string to ssh unparsed (cli/main.py --ssh-options; cli/ssh_utils.py build_ssh_tunnel_command), so an option such as -o ProxyCommand=... runs a local command. The native app's topology brief recommends exempting metab * from agent sandboxes so metab TARGET --present works; with this flag that exemption lets a sandboxed agent run arbitrary commands outside its sandbox (inferred from reading; not executed). Options: an allowlist of SSH options, moving --remote's raw options to the separate plugin-code executable the plugin-sources plan proposes, or narrowing the documented exemption to the front-door mode.
