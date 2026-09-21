---
type: is
id: is-01m2yxd3tnr1s2zf0h0jat1ey2
title: "v0.11 stabilization review: independent full review of stack #218 and #209 against specs and beads"
kind: task
status: in_progress
priority: 1
version: 51
spec_path: docs/project/specs/active/plan-2026-08-11-open-repo-from-git-url.md
labels:
  - release:v0.11.0
dependencies:
  - type: blocks
    target: is-01m2k713pxra1ns2fk3pcwrpb6
parent_id: is-01kzs5m38dz1egphfwf30c8h7n
child_order_hints:
  - is-01m2zpvykba6wabg6ms9wawzb0
  - is-01m2zpvzfx40az8dvj2peg3hb2
  - is-01m2zpw18m2z2nmprgkmzq3jwk
  - is-01m2zpw31yzxj69k3fdzzp3qn7
  - is-01m2zpw4zkmx00dk5gh5s4kjqm
  - is-01m2zpw6dzfwa6a86z4vc8yfzc
  - is-01m2zpw7z0f201xxwtvzb51kyk
  - is-01m2zpw9bkkn7m6gwv0q5cbeqd
  - is-01m2zpway7zvshv7271v9cp498
  - is-01m2zpwenhppjpks39tf0nxkkb
  - is-01m2zpwg44k0y7snevbfqdyw8k
  - is-01m2zpwhgmcptq6ge42ckj84rc
  - is-01m2zpwjvq4pq1cqbdqa1avrp3
  - is-01m2zpwm7b0ns673t2jyje7fdg
  - is-01m2zpwnbv0z16dxng8s75dn4b
  - is-01m2zpwpet6pzt8zvvmnx082ac
  - is-01m2zpwqfy7v676azc2mxx3g5s
  - is-01m2zpwrm0069gs0swx9m6xqfr
  - is-01m2zpwswpwq4hm7kr70ddpbjy
  - is-01m2zpwtxsex7zg035m9p3yvm7
  - is-01m2zpwvxd9vp6vpn587bsz6p7
  - is-01m2zpwxfk2v9gqyrt5yg6a59x
  - is-01m2zpwyzk68zpmngrxadssn2r
  - is-01m2zpx0fhq4x5e1qtcteearj5
  - is-01m2zpx1svn4c8an4mm9r9mv8z
  - is-01m2zpx351fryc2z9hjb2m4j4a
  - is-01m2zpx4d15neap9x8fcf36tq4
  - is-01m2zpx5m27d6tnn4qf6zbhfv8
  - is-01m2zpx6gr7kcfmwvbrfhbse7s
  - is-01m2zpx7pmkbxzgkp7cwqt6qzb
  - is-01m2zpx9218wz0egrejamr3651
  - is-01m2zpxck1jqrmv4a2dhwve47v
  - is-01m2zpxg6x10hmbxayqh9ccag1
  - is-01m2zpxmwz32ykx0q3w62qhghh
  - is-01m2zpxqcyxkb5ajsh9zm2c47p
  - is-01m2zpxv9y2v992te1pdr2x52n
  - is-01m2zpxwxtv9pcjf6ynxcan41h
  - is-01m2zpxyf1qczg3r6cadfhh7sy
  - is-01m2zvfm9pdxz0emydeqedf9gq
  - is-01m2zwj2wpj4abvhdng36mnm03
  - is-01m2zyv9gj9f0w6esn4vnsy38s
  - is-01m30x2tyka6xd3ta5ahbwr952
  - is-01m30x2vckrmc1c6xhtvwnnpjj
  - is-01m30yacs0ar9ggkf72fa3manp
created_at: 2026-09-20T08:02:30.356Z
updated_at: 2026-09-21T02:56:58.655Z
---
Follow-up to mb-rldx, which was closed at 2026-09-20T07:32Z by a fast pass while its own notes said the #216 browser/plugin, resource-lifecycle, CLI/parity, and docs review passes were unfinished. Independently verify the #140/#217/#216 fix commits (da73b878, 70091d81, bc8dd72b, de0f4f5a), complete the unreviewed areas, review #209 as the security gate for serving acquired Git, reconcile every PR review channel, and reconcile beads and spec checklists with the branches. Output: confirmed findings filed as beads on their owning layers, and an ordered stabilization plan. Read-only until the plan is agreed; do not merge (landing owner is mb-n2ro).

## Notes

# v0.11 stabilization review and fixes (2026-09-20)

Independent re-review of stack #218 and PR #209 after `mb-rldx` was closed by a fast pass,
then fixes for everything it found.
Eleven read-only reviewers, then implementers on isolated worktrees.
Per-finding detail lives on the child beads and in the PR disposition comments.

## Landed on main

- **#207** anyio 4.14.2. `main` and four stack layers failed `make audit` on three
  advisories until it merged.
- **#209** HTML trust model: sandboxed `/raw` from a path-scoped layer, `/api`
  same-origin proof, `--untrusted`, path-shaped `/raw/{path}`, the `html` kind.
  Merged as `fd65812b` after its first-ever review, its fixes, and a real-browser check
  against a hostile fixture.
- **#220** "Open as full page": a plain anchor to the same `/raw/<path>` the frame uses.
  Merged as `269320b2`.

## Stack #218: restacked, fixed, green, not landed

All seven layers were merged forward onto the new `main` and carry their reviewed fixes.
No commit was rewritten, so every SHA cited in a published disposition stays reachable.
CI green on all seven; `stack-integration` green, which is the check that merges `main`
into each head.
Local gate on macOS at the tip: 3061 passed, 2 skipped, 145 golden transcripts.

| PR | Head |
| --- | --- |
| #125 | `e25ec590` |
| #134 | `5dfca8d8` |
| #136 | `bf30d6f3` |
| #139 | `ba1d47db` |
| #140 | `cee52937` |
| #217 | `6dc2617c` |
| #216 | `842da53a` |

Highest-severity fixes: an ordinary non-bare clone could not be acquired at all (#217);
the earlier R1 fix had made nested pin listings quadratic (#216); whole-index rescans on
every request (#216); Git `/raw` would have bypassed #209's sandbox after the merge, now
proven otherwise by a wire test (#216); `--untrusted` was silently dropped on Git pins
(#216, #217); two regressions that affected plain filesystem browsing (#216).

## In flight when work paused

`feat/content-reader` (branch clean, no commits yet; agent stopped partway, its worktree
is `.claude/worktrees/agent-a5acb944186ec3859`).
Bounded source-agnostic content reader through `plugin_api` (`mb-0um4`): the agent had
derived the operation inventory and was about to move the four sidekicks.
Restart it rather than resuming; nothing is committed.

## Open, in rough order

1. `mb-0um4` content reader, then `mb-3z4d` multi-entry Git-pin golden (the current one
   is a one-file origin with an empty tree listing).
2. `mb-x85f` **needs a decision**: a browsed repository's `.env` can set
   `METABROWSER_PLUGINS_DIRS` and load plugin JavaScript into the application origin.
   On `main` today, predates #209. Recommendation: refuse the key from a dotenv file
   inside the served root, and always under `--untrusted`.
3. `mb-5721` store lock held across an `await`; `mb-vs5q` `StableToken` unbounded and
   enums coercing bytes; `mb-mzdj` three spec test-strategy items; `mb-lp89`
   process-group kill; `mb-pkho`, `mb-rati`, `mb-e32d`, `mb-d1za` Phase 1B-a remainders;
   `mb-bi2c` https/ssh acquisition; `mb-dbue` unfork #219.
4. Landing: `mb-n2ro` (this stack plus #209, still held, needs explicit approval), then
   `mb-nhky` for the later phases.

## Notes for whoever picks this up

- CI is Linux only, and this stack's cache layer is full of platform-specific
  permission and ACL behavior. One test passed on macOS and failed on Linux
  (`chmod(follow_symlinks=False)` on a link). Expect more of both directions.
- The machine was at load average 348 during the final gate; a 60-second pytest timeout
  fired on a test that passes in 215 s in isolation. Prefer CI when the machine is busy.
- Fable ran out of monthly budget mid-session; everything after that is Opus.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
