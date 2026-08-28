---
type: is
id: is-01m1389bszmmkqj7d90sq8p3bj
title: Accept local origins as first-class Git sources under the untrusted profile
kind: task
status: open
priority: 1
version: 2
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
labels: []
dependencies:
  - type: blocks
    target: is-01kzsb4jnyd56wy89xmztkmz2m
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
created_at: 2026-08-28T03:58:15.870Z
updated_at: 2026-08-28T03:58:46.976Z
---
Closed design decision (2026-08-28): cache/urls.py classifies transport as https, ssh, or local, and accepts file:// URLs and local repository paths as Git sources. acquire() binds local sources to the untrusted profile unconditionally. Documented as mirror and air-gapped support. Rationale: the safe URL grammar exists to reject ambiguous and dangerous input (credentials, query, fragment, option-like strings), not a transport strictly safer than those already allowed. This keeps acquisition goldens on the production code path; the rejected alternative, a test-only escape hatch, forks test and production logic.
