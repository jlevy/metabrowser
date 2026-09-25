---
type: is
id: is-01m3awj2tre3j0swwzvyvb9rzv
title: Pull-request header omits the base owner for a pull request from a fork
kind: bug
status: closed
priority: 4
version: 3
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: claude-code@spud10.local
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m36k3w9vgwy97c9hcj2sqrs5
hold: null
hold_until: null
created_at: 2026-09-24T23:38:37.781Z
updated_at: 2026-09-25T00:39:31.489Z
started_at: 2026-09-24T23:49:51.877Z
closed_at: 2026-09-25T00:39:31.486Z
close_reason: "PR #244: both sides owner-qualified when head repo differs from base, as github.com; CI green"
resolution: null
duplicate_of: null
---
Found in the v0.12 acceptance rerun on PR #243 (head 7d91c8f4, installed wheel 0.11.1.dev412+7d91c8f4), row M07 wording.

For a pull request whose head is in another repository, github.com qualifies both sides with their owner: cli/cli#14502 reads '00200200 wants to merge 1 commit into cli:trunk from 00200200:fix/auth-status-rate-limit-network', and encode/httpx#3783 reads 'kajinamit wants to merge 1 commit into encode:master from kajinamit:keep-method-for-redirects'. Metabrowser's header qualifies the head but not the base: 'into trunk from 00200200:fix/...' and 'into master from kajinamit:...'. For same-repository pull requests (cli/cli#14128, jlevy/metabrowser#234) both sides match github.com.

Cause (inferred): describePull in src/metabrowser/builtin_plugins/github/pull-page.js sets base: sideName(pull.base, repository), and sideName drops the owner whenever the side's repository is the base repository, which is always true for the base.

Reproduction: metab https://github.com/cli/cli/pull/14502 --no-open --port <p>, open /pull/14502, compare the header line with github.com.

Acceptance: when the head repository differs from the base repository, the header reads '<owner>:<base>' as github.com does; same-repository pull requests are unchanged. A browserless session golden pins both.
