---
type: is
id: is-01m2s7p36wwz4jjvvyv4x70mq7
title: Pin Git 2.50.1 in CI so live acquire tryscripts can run
kind: task
status: closed
priority: 2
version: 4
spec_path: docs/project/specs/active/plan-2026-08-28-cli-first-delivery-map.md
delegate: claude-code@spud10
labels:
  - release:v0.12.0
dependencies: []
parent_id: is-01m1389rewn2mkj8emj3wxwpr7
hold: null
hold_until: null
created_at: 2026-09-18T03:06:43.804Z
updated_at: 2026-09-23T05:32:19.789Z
started_at: 2026-09-23T03:31:08.214Z
closed_at: 2026-09-23T05:32:19.785Z
close_reason: "Done on codex/v012-foundation-stabilization (PR #226), merged from codex/v012-stab-git-floor (0a161468). The admitted-git CI job builds checksum-verified Git 2.43.7 and 2.50.1 from kernel.org with devtools/build_admitted_git.sh, caches the build keyed by runner image, release and script hash, and puts it on PATH for that job only. Checksums, their source (sha256sums.asc, fetched 2026-09-22, signature not verified) and the cool-off are recorded in SUPPLY-CHAIN-SECURITY.md, and check_supply_chain keeps script, doc and matrix in step. Both legs green at a5339d8b: https://github.com/jlevy/metabrowser/actions/runs/35820742829"
resolution: null
duplicate_of: null
---
ubuntu-latest ships Git 2.43.0, which production require_acquisition_git refuses (floor 2.43.7 / patched tracks; distro backports remain refuse). Portable acquire evidence therefore lives in pytest (mb-3639) with the floor monkeypatched.

To run cli-cache-acquire.tryscript.md / cli-cache-recover.tryscript.md as real metab subprocesses in CI, install a checksummed Git 2.50.1 (ACQUISITION_NEWEST_PATCHED) from kernel.org, verify sha256, cache the build, and put it on PATH for the test job only. Do not replace the runner git for unrelated jobs without evidence. Record the pin, checksum, and cool-off in SUPPLY-CHAIN-SECURITY.md.

Known checksums (kernel.org sha256sums.asc):
- git-2.50.1.tar.xz 7e3e6c36decbd8f1eedd14d42db6674be03671c2204864befa2a41756c5c8fc4
- git-2.50.1.tar.gz 522d1635f8b62b484b0ce24993818aad3cab8e11ebb57e196bda38a3140ea915

This is a supply-chain and CI-time change, not mixed into the portable golden slice. Distro-patched Git remains refuse in production.
