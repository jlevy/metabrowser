---
type: is
id: is-01m6c49e1xpbjr4f6dy7p8js8e
title: Two pin goldens depend on test order through a module-scoped sandbox
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m402dbhn3zsc1h896f3xnrsq
created_at: 2026-11-01T18:00:02.876Z
updated_at: 2026-11-01T18:00:02.876Z
---
Found 2026-11-01 running a large selection in reversed order: test_golden_pin_show and test_golden_pin_refusals fail, with or without the new conftest reset, apparently because the module-scoped sandbox in test_cli_git_pin_golden.py lets the first test do the clone. Only reversed order fails.
