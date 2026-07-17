---
name: metabrowser
description: >-
  Browse local or remote directories, files, logs, JSONL streams, Markdown,
  structured data, images, and binary metadata with Metabrowser. Use when a user
  asks to explore artifacts, inspect live logs, open a local file browser,
  inventory a directory, or inspect and validate Metabrowser plugins.
---
# Metabrowser

Use Metabrowser through its self-documenting CLI. Keep the skill as a routing layer and
use command help as the source of truth for arguments and options.

## Choose the Invocation

Use the pinned zero-install runner by default:

```shell
uvx metabrowser@0.1.0
```

If the user has already installed Metabrowser globally, use `metab` instead.
Do not install it persistently only to complete a task that `uvx` can handle.

Run `<invocation> --help` before the first operation when the required command is not
already clear. Run `<invocation> <command> --help` for the selected command rather than
guessing flags.

## Route the Task

- Browse a local directory or file: pass its path directly or inspect `serve --help`
- Start a headless server: inspect `serve --help` and use its no-open option
- Browse a remote directory through SSH: inspect `remote --help`
- Produce a text, JSON, YAML, or streaming inventory: inspect `walk --help`
- Inspect or validate plugins: inspect `plugins --help`; use `plugins list --json` for
  structured discovery and `plugins doctor` for validation

## Operate Safely

- Serve only paths the user placed in scope
- Keep the default localhost binding.
  Never expose Metabrowser directly to the public internet; change the binding only for
  an explicitly requested trusted network.
- Treat installed and operator-directory plugins as executable code; pass
  `--plugins-dir` only for a directory the user trusts
- Keep Python entry-point plugins in the same uvx or uv tool environment as Metabrowser;
  use uv’s `--with` only for an explicitly trusted, version-pinned plugin distribution
- Prefer `walk --format json` when the task needs machine-readable inventory rather than
  an interactive browser
- In a headless environment, avoid opening a browser and report the local URL and
  whether the server is still running
- Preserve nonzero exits and surface plugin-doctor failures instead of reporting partial
  success as complete

## Report the Result

State what Metabrowser opened or inspected, the served root, the selected file when
applicable, the local URL for a running server, and any plugin or validation errors.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
