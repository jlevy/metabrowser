---
title: Setup GitHub CLI
description: Ensure GitHub CLI (gh) is installed and working
category: session
author: Joshua Levy (github.com/jlevy) with LLM assistance
---
The GitHub CLI (`gh`) is required for PR and issue operations.

**In most cases, gh is already available** - tbd installs a SessionStart hook that
auto-installs gh on every session.

## Sanity Check (Do This First)

**Important:** Don’t assume gh works just because `command -v gh` succeeds.
On Claude Code Cloud, pre-installed gh may be outdated, broken, or incompatible.
Always verify:

```bash
# The real test: does gh actually work AND is it authenticated?
gh auth status
```

**Expected output:** Shows “Logged in to github.com” with your account.

If this fails for any reason, follow the steps below.

## Corner Cases You May Encounter

1. **gh exists but is broken**: `gh --version` or `gh auth status` fails with errors
   - Solution: Reinstall via ensure script (installs fresh copy to ~/.local/bin)

2. **gh exists but wrong version**: Very old gh may lack required features
   - Solution: Reinstall via ensure script

3. **gh works but not authenticated**: `GH_TOKEN` not set or invalid
   - Solution: Set `GH_TOKEN` environment variable before starting session

4. **PATH issues**: gh installed but not in PATH
   - Solution: Ensure `~/.local/bin` is in PATH, or use full path

5. **Proxied remote session intercepts GitHub (Claude Code cloud and similar)**: `gh` or
   `curl https://api.github.com` returns 403 with a message such as “GitHub access is
   not enabled for this session”, or the gh download itself 403s
   - Solution: route GitHub traffic directly instead of through the session’s
     `HTTPS_PROXY`. See the next section — do not conclude GitHub is blocked, and do not
     fall back to MCP-only workflows if the task needs `gh`.

## Proxied Remote Sessions (Read This Before Concluding GitHub Is Blocked)

Remote agent sessions often route HTTPS through a policy proxy (`HTTPS_PROXY`), and that
proxy may intercept GitHub hosts with its own 403 even when the environment’s egress
policy allows GitHub.
There are three separate channels, and a failure in one says nothing about the others:

1. **git-over-HTTP** through a local credential broker: works for the session’s
   branches, and its credentials are usually branch-scoped (tag pushes can 403).
2. **The HTTPS proxy relay**: may intercept `api.github.com` and answer 403 itself.
   A relay 403 is not proof the network blocks GitHub.
3. **Direct egress**, which honors `NO_PROXY`: governed by the environment’s network
   policy. When the environment allows GitHub, this channel works with `GH_TOKEN` — and
   `gh` honors `NO_PROXY` natively, so no raw API calls are needed.

The verified recipe:

```bash
export NO_PROXY="api.github.com,github.com,objects.githubusercontent.com,uploads.github.com,codeload.github.com,raw.githubusercontent.com${NO_PROXY:+,$NO_PROXY}"
export no_proxy="$NO_PROXY"
bash .claude/scripts/ensure-gh-cli.sh   # download works once NO_PROXY covers github.com
gh auth status                          # authenticates from the session's GH_TOKEN
```

Diagnostic discipline when a GitHub call 403s: read the response body and headers before
concluding anything.
A real GitHub answer carries `x-github-request-id`; a relay answer carries the relay’s
own message.
Retest with and without the `Authorization` header and with `NO_PROXY` set —
an unauthenticated direct probe can 403 from GitHub’s own rate limiting and prove
nothing about the token path.

## Installation

1. **Run the ensure script:**
   ```bash
   bash .claude/scripts/ensure-gh-cli.sh
   ```
   This script installs gh to `~/.local/bin` and checks authentication.

2. **If the script doesn’t exist:** Run `tbd setup --auto` to reinstall tbd hooks, which
   includes the gh CLI script.

3. **Manual installation (fallback):**
   ```bash
   # macOS
   brew install gh

   # Linux (Debian/Ubuntu)
   curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
   echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
   sudo apt update && sudo apt install gh
   ```

## Authentication

Set `GH_TOKEN` environment variable with a GitHub personal access token **before**
starting the session.
Create a [Personal Access Token](https://github.com/settings/tokens?type=beta)
(fine-grained recommended) with **Contents** and **Pull requests** read/write
permissions, then export it (e.g. add `export GH_TOKEN=...` to your shell profile or set
it in your agent environment).

## Quick Reference

| Problem | Solution |
| --- | --- |
| `gh: command not found` | Run ensure script or add ~/.local/bin to PATH |
| `gh --version` fails | gh is broken, reinstall via ensure script |
| `gh auth status` shows errors | GH_TOKEN not set or invalid |
| `Bad credentials` | Token expired or lacks permissions |
| `Resource not accessible` | Token lacks required scopes (need repo, workflow) |

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
