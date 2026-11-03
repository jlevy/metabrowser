---
type: is
id: is-01m6h5aaj3kfc3t71kra95axh9
title: "PR #281 Qodo4457444624: canonical no-host comparison response"
kind: bug
status: closed
priority: 3
version: 6
labels: []
dependencies: []
parent_id: is-01m6g59qm4ewjgek4vjmndcxrj
created_at: 2026-11-03T16:54:12.802Z
updated_at: 2026-11-03T20:17:09.790Z
closed_at: 2026-11-03T20:17:09.790Z
close_reason: "Completed by forward commits in the PR-support stack; independent reviews, rechecks and dispositions are published on the owning PRs. Final integration ea771741211193a387c1771e04df29b5a9698100 passed make verify (4712 Python, 9 expected skips, 373 transcripts), 8 public live tests, installed-wheel Chrome (22 actions, 25 unchanged checkout/Git fingerprints), and all 171 CI jobs across 19 current-head runs on 14 PRs. Final clean review: https://github.com/jlevy/metabrowser/pull/288#pullrequestreview-5758664799 . No PR merged."
resolution: null
duplicate_of: null
---
Low confirmed review https://github.com/jlevy/metabrowser/pull/281#discussion_r4457444624 at3dd12b0b. pull-comparison alone still returns409/no_pull_request for hostNone, while pull envelope/markdown/refresh use not_github. Focused real-route test fails before fix; correcting source to the canonical error body and verifying no-store/no-ETag. Upper288 integration must keep hostNone=>not_github distinct from an existing checkout host without store=>no_store. No omitted-number compatibility alias. Durable evidence task evidence `bot-triage-281-283/`.

## Notes

Product error-code fix1e2bc2379d38904fdb874971dd076f99dc6a8f6f retained. Independent final integration exposed test fixture dependence on ambient cwd: upper288 correctly recognizes a GitHub checkout and returns no_store. Test-only owning281 child e8e47e4be95935b74929ce3b5b21e2a7fd75a1df explicitly serves tmp_path using established server._set_root_dir/reset fixture;1pass1.06s and normalhooks. Upper288 separate test-only child2bd58827700e951c3cd7359efd6fd20bfe33f96d of integrated65ba01e5 adds actual recognized checkout/no_store API control, no cache home acquisition and unchanged checkout fingerprint. Both plainfolder/not_github and checkout/no_store tests2pass1.54s with normalhooks. No product/golden/normalizer change. Durable no-host-fixture-correction.json/raw logs retained in bot-triage-281-283. Writer tree clean/detached; root owns final integration/fullgate/CI/publication/sync/closure.
