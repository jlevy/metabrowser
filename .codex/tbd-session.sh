#!/bin/bash
# Ensure the tbd CLI is available and run `tbd prime`.
# Installed by: tbd setup --auto. Runs on SessionStart and PreCompact.
#
# Hooks never fetch packages. Install the exact repository-supported tbd release
# once, then every session uses that local executable.

# Prefer common local bin locations.
export PATH="$HOME/.local/bin:$HOME/bin:/usr/local/bin:$PATH"

# Local-first: use tbd if it is already on PATH.
if command -v tbd &> /dev/null; then
    tbd prime "$@"
    exit $?
fi

echo "[tbd] tbd CLI not found."
echo "[tbd] Install it with: npm install -g get-tbd@0.4.0"
exit 1
