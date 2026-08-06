#!/bin/bash
# Ensure the tbd CLI is available and run `tbd prime`.
# Installed by: tbd setup --auto. Runs on SessionStart and PreCompact.
#
# Local-first, then a VERSION-PINNED zero-install fallback. Pinning is both a
# supply-chain control (an unpinned runner re-resolves to latest on every run
# and bypasses any cool-off) and a consistency control (every teammate and agent
# runs the same tbd version).

# Prefer common local bin locations.
export PATH="$HOME/.local/bin:$HOME/bin:/usr/local/bin:$PATH"

# Local-first: use tbd if it is already on PATH.
if command -v tbd &> /dev/null; then
    tbd prime "$@"
    exit $?
fi

# Pinned zero-install fallback. Never use an unpinned runner here.
# get-tbd is an audited first-party exception to the .npmrc 14-day cool-off
# (SUPPLY-CHAIN-SECURITY.md), so override min-release-age for this exact pin only.
if command -v npx &> /dev/null; then
    npx --yes --min-release-age=0 get-tbd@0.4.2 prime "$@"
    exit $?
fi

echo "[tbd] tbd CLI not found and npx is unavailable."
echo "[tbd] Install it with: npm install -g --min-release-age=0 get-tbd@0.4.2"
exit 1
