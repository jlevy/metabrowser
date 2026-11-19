# Research: Operational Visibility Into Claude Code and Codex

**Date:** 2026-11-19

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** In Progress.
Bead `mb-d7q6` tracks it.
The format survey of `~/.claude` and `~/.codex` is complete.
The plugin design under [Recommendations](#recommendations) is a proposal, and the
[Open Questions](#open-questions) need the owner’s answers before a plan.

## Overview

The owner asked, on 2026-11-19:

> “I’d like to use metabrowser to get full operational views of ~/.claude and ~/.codex.
> We already have pretty good coverage of log files, but can we research the formats of
> all files in those directories comprehensively and let’s consider how to have full
> operational visibility on all things claude and codex are doing.”

and added:

> “We might also in the future extend to other agents but those are a good start.
> We want to structure this so it is a plugin, even if we distribute it built into
> metabrowser, it should be structured like an additional plugin that uses our plugin
> structure.”

Operational visibility here means answering, from the files the agents already write,
questions such as: what is running right now, what did each session and subagent do and
cost, which files did it change, which hooks and permission decisions fired, which
scheduled tasks and automations ran, and how close the account is to its rate limits.

This brief records what each agent writes, where Metabrowser’s coverage stands today,
and a proposed plugin that adds the rest.

## Questions to Answer

1. Which files do Claude Code and Codex write under their home directories, in what
   formats, how are they written, and how do they join?
2. Which operational questions does each file answer, and which questions have no file
   that answers them?
3. What does Metabrowser show for these files today?
4. How should a plugin that answers the rest be structured, so that it is shipped built
   in but uses only the contract an installed plugin uses, and so that other agents can
   be added?
5. What does the plugin SDK lack for this?

## Scope

**In scope:** every file family under `~/.claude` and `~/.codex` on one macOS machine,
written by Claude Code 2.1.233 to 2.1.325 (the desktop app’s embedded CLI and the
standalone CLI) and by Codex CLI 0.157.0 with the Codex desktop app’s bundled
app-server, plus the few files outside those directories that they point to.

**Out of scope:** other agents (Gemini CLI, Pi, Cursor, and others), apart from keeping
the design open to them; remote or cloud sessions, which leave no local files; and
reading the agents’ source code.
Formats were inferred from the files themselves and not from published documentation, so
every schema below is observed behavior that can change with any release.

## Methodology

Three read-only surveys ran on 2026-11-19, one for `~/.claude`, one for the files in
`~/.codex`, and one for the SQLite databases in `~/.codex`. No file was modified, SQLite
databases were opened read-only, and the surveys recorded shapes only: record types and
their counts, field names and types, enumerated values, sizes, and timestamps, never
message content, paths, or secrets.

- **Sampling:** JSONL schemas come from the newest and oldest files in each family plus
  a spread across versions; directory counts, sizes, and small metadata files were read
  exhaustively. Enumerations from samples may be incomplete.
- **Joins** were verified by resolving one family’s identifiers in another and counting
  the hits; the counts are quoted where they matter.
- **Liveness** was checked by comparing sizes, inodes, row counts, and
  `PRAGMA data_version` across snapshots taken seconds apart while sessions ran.
- **Today’s coverage** was checked with `metab PATH --show FILE` on a current Claude
  session log and on Codex rollout files.

## Findings

### Today’s Coverage in Metabrowser

The built-in `agent-log` plugin (`src/metabrowser/builtin_plugins/agent_log/`) opens a
coding-agent JSONL session log with Log, Charts, and Raw JSON views.
The parsers are in core, in `src/metabrowser/logutil/parsing.py`, as four built-in
adapters (`claude`, `codex`, `gemini`, `pi`), and `detect_adapter` picks one from the
first 20 lines.

Coverage is narrower than it looks, and two gaps hit the two agents this brief is about:

- **Current Claude Code session logs are not recognized.** Since about 2.1.247 a session
  file opens with `queue-operation`, `attachment`, `custom-title`,
  `file-history-snapshot`, `last-prompt`, `agent-name`, `atis-latch`, and `user`
  records, and the first `assistant` record is usually past line 20. `detect_adapter`
  looks for a `system` record with subtype `init` or a hook subtype, or for an
  `assistant` record, so it answers `unknown`, and the file opens as `unknown-jsonl`
  with Log and Raw JSON and no Charts.
  In 40 of the 40 newest session files no `assistant` record appeared in the first 20
  lines.
- **Codex rollout files are not recognized.** The `codex` adapter parses the
  `codex exec --json` stream (`thread.started`, `turn.*`, `item.*`), not the rollout
  files Codex keeps in `~/.codex/sessions`, whose records are `session_meta`,
  `response_item`, `event_msg`, `turn_context`, and others.
  A small rollout opens as `unknown-jsonl`; a 97 MB one exceeds `_JSONL_PARSE_MAX_BYTES`
  and opens as an error.
- **Compressed logs do not open.** Codex compresses idle rollouts to `.jsonl.zst`, and
  some Claude logs are `.jsonl.zst` too.
  Metabrowser’s compressed-artifact support reads gzip only, and Python’s standard
  library has zstd only from 3.14 (`compression.zstd`), while the supported range starts
  at 3.12.
- **Nothing but session logs has a view.** SQLite databases open as `binary`; there is
  no session list, no live-session view, no cost rollup, no subagent tree, no
  file-history view, no hook or permission view, and no view of scheduled tasks,
  automations, settings, plugins, or skills beyond their text.

### `~/.claude`: Claude Code

`~/.claude` held 7.1 GB. Subagent transcripts are 5.0 GB of it, main transcripts 1.3 GB,
compressed transcripts 0.35 GB, and spilled tool results 0.44 GB.

#### File Families

| Path pattern | Format | Write pattern | Joins on |
| --- | --- | --- | --- |
| `projects/<enc-cwd>/<sid>.jsonl` | JSONL transcript | Append-only, live during a turn | `sessionId` is the file stem |
| `projects/<enc-cwd>/<sid>.jsonl.zst` | zstd JSONL | Compressed by an outside tool, not by Claude Code | Same |
| `projects/<enc-cwd>/<sid>/subagents/agent-<aid>.jsonl` | JSONL transcript | Append-only, live | `agentId`; `sessionId` is the parent’s |
| `…/subagents/agent-<aid>.meta.json` | JSON | Written at spawn, rewritten with `finished: true` | `toolUseId`, `parentAgentId`, `agentType` |
| `…/subagents/agent-<aid>.prefix.json` | JSON | Written at spawn | Prompt-cache prefix state |
| `projects/<enc-cwd>/<sid>/workflows/`, `…/subagents/workflows/wf_<id>/` | JSON, JSONL journal | Written per run | `runId`, `taskId`, `agentId` |
| `projects/<enc-cwd>/<sid>/tool-results/*` | Text, images, PDF pages | Created once | `persistedOutputPath`, hook record `content`, tool-use id |
| `projects/<enc-cwd>/<sid>/custom-title.json` | JSON | Rewritten | Session title |
| `projects/<enc-cwd>/memory/*.md` | Markdown with front matter | Rewritten by the agent | `originSessionId` |
| `file-history/<sid>/<hash16>@v<N>` | Raw file bytes | Created once per version | `backupFileName` in transcript records |
| `sessions/<pid>.json`, `sessions/<pid>.<hash>.key` | JSON | Created at start, rewritten on status change, deleted at exit | `pid`, `sessionId`, `hostSessionId` |
| `session-env/<sid>/` | Directory | Created at start | `sessionId` |
| `shell-snapshots/snapshot-bash-<ms>-<rand>.sh` | Bash | One per process start | Process start time only |
| `scheduled-tasks/<task-id>/SKILL.md` | Markdown with front matter | Written by the desktop app | Task id in the desktop app’s schedule |
| `plugins/*.json`, `plugins/marketplaces/`, `plugins/store/` | JSON, trees | Rewritten on refresh | Marketplace and plugin names |
| `skills/<name>/SKILL.md`, `agents/*.md` | Markdown with front matter | User-edited or synced | Skill name; `agentType` |
| `telemetry/1p_failed_events.<sid>.<uuid>.json` | JSONL | Appended when an upload fails | `session_id`, `agent_id` |
| `backups/.claude.json.backup.<ms>` | JSON | One per process start, five kept | None |
| `history.jsonl` | JSONL | Appended by the terminal CLI only | `sessionId` |
| `settings.json` | JSON | User and `/config` | None |
| `stats-cache.json`, `projects/<enc-cwd>/sessions-index.json` | JSON | Stale; no longer refreshed | None |
| `.last-cleanup`, `.last-update-result.json`, `cache/*` | Text, JSON | Rewritten | None |

A project directory’s name is the session’s absolute working directory with every
character outside `[A-Za-z0-9]` replaced by `-`. That encoding is lossy, so the real
`cwd` comes from the transcript’s records, not from the directory name.

#### The Transcript

A transcript is a stream of records, each with a `type`. In the 20 newest files (75,000
records), by count: `assistant`, `user`, `api-request`, `queue-operation`, `attachment`,
`api-request-blob`, then session metadata records, `system`, `file-history-snapshot`,
`file-history-delta`, `api-request-shape`, and `cost-state`. No `summary` or `progress`
record appeared in any sampled file.

- **Conversation records** (`user`, `assistant`, `attachment`, `system`) share an
  envelope: `uuid`, `parentUuid`, `isSidechain`, `timestamp`, `sessionId`, `cwd`,
  `gitBranch`, `version`, `entrypoint`, and `slug`. The `cwd` and `gitBranch` change
  within a session in about a third of files.
- **One `assistant` record per content block.** Records that share a `message.id` carry
  the same `usage`, so token totals must count each `message.id` once; summing every
  record roughly doubles them.
  `usage` carries input, output, cache-read, and cache-creation tokens (split by
  5-minute and 1-hour TTL), server tool use, and thinking tokens.
  Content blocks are `text`, `thinking`, and `tool_use`. Error stubs carry
  `isApiErrorMessage`, `apiErrorType`, and `quotaLimits`.
- **`user` records** carry tool results, a `permissionDecision` (decision, source,
  reason type, rule source, classifier category), a `toolDenialKind`, and prompt
  provenance: `turnOrigin` (human, peer, task notification, auto-continuation,
  scheduled, SDK) and an `origin` object.
  `toolUseResult` holds a tool-specific result: Bash output, exit interpretation, and
  background task id; an Edit or Write `structuredPatch` and `originalFile`; an Agent
  call’s `agentId`; a Workflow’s `runId`; a CronCreate schedule.
- **`attachment` records** carry about 30 types.
  The operational ones are `hook_success` and `hook_non_blocking_error` (hook event,
  command, exit code, duration, stdout, stderr), `task_status` (background agents and
  shells), `queued_command` (with a finished subagent’s token and tool-use totals), and
  `remote_session_change` (pull request and commit links).
- **`system` subtypes** include `api_error` (with retry attempt and network details),
  `compact_boundary` (trigger, tokens before and after, duration), `stop_hook_summary`
  (per-hook durations and errors), and `turn_duration`.
- **Session metadata records** (`custom-title`, `agent-name`, `last-prompt`, `mode`,
  `permission-mode`, `pr-link`, `relocated`, `tools-used`, `cost-state`) have no `uuid`
  and are appended again and again through the file; the last one wins.
  `cost-state` is Claude Code’s own cumulative cost, duration, lines changed, and
  per-model usage for the session.
- **Model call records** (`api-request`, `api-request-shape`, `api-request-blob`, since
  about 2.1.295) record each model call’s parameters, delta-encoded against the previous
  call, with system prompt and tool schemas stored once by hash.
  An `assistant` record’s `requestRef` names its call.
- **File-history records** (`file-history-snapshot`, `file-history-delta`, since
  2.1.260) map each tracked path to a backup in `file-history/<sid>/`. The backup name
  is the first 16 hex digits of the SHA-256 of the file’s real path plus `@v<N>`; a
  `null` backup name means the edit created the file.
  Backup modification times are unreliable (some are hard links), so the record’s
  `backupTime` is the time to use.
- **Resumed and forked sessions copy history.** A new file can begin with thousands of
  records whose `sessionId` is another session’s, so cross-session totals must
  deduplicate by `uuid`.

#### Subagents

Each subagent writes its own transcript beside the parent session, with `isSidechain`
true and the parent’s `sessionId`. Its `meta.json` names the agent type, model, effort,
spawn depth, foreground or background, worktree, and the `toolUseId` of the parent’s
call that started it; nested spawns are stored flat in the same directory and linked by
`parentAgentId`. A subagent with no `finished: true` is either running or was cut off.

#### Live State

`sessions/<pid>.json` is the registry of running sessions: process id, session id,
working directory, version, entry point, the desktop app’s `hostSessionId`, the session
name, and `status` (`busy` or `idle`) with its update time.
The set matched the running Claude processes exactly, and a file disappears when its
process exits. The `.key` file beside it holds a peer token and is a secret.
Other live signals are a transcript’s growth, a subagent `meta.json` without `finished`,
and `task_status` attachments.

#### Outside `~/.claude`

Some state Claude Code depends on lives elsewhere, and a full view needs it:

- `~/.claude.json`, not `~/.claude/.claude.json` (a stub), holds per-project settings,
  the last session’s cost and metrics per project, tool, skill, and plugin usage counts,
  and the OAuth account, which is a secret.
- The desktop app’s store under `~/Library/Application Support/Claude/` holds each
  desktop session’s record, linked by `cliSessionId`, and the scheduled tasks’
  schedules, last run times, and skips.
- Background task output is under the per-user temporary directory, and the peer
  messaging sockets are under `/tmp`; both are transient.

#### Retention and Version Drift

Top-level transcripts reach back 28 days, which matches the default cleanup period,
while `history.jsonl`, memory files, and the stale caches are never pruned.
Record types arrive and leave with releases: the version matrix found eight releases
that each introduced types, and several types that stopped after 2.1.280. Claude Code
ships about daily, so a parser has to accept unknown record types and missing fields.

### `~/.codex`: Codex

`~/.codex` held 39 GB, of which `thread_history_1.sqlite` is 11.3 GB, `state_5.sqlite`
1.1 GB, and the rollout files in `sessions/` 9.1 GB. One long-running Codex app-server
process, bundled with the desktop app, writes every live database; it records
`cli_version` 0.166 alpha, newer than the standalone CLI.

#### Rollout Files

`sessions/YYYY/MM/DD/rollout-<timestamp>-<threadId>[_<historyId>].jsonl` is the source
of record for a thread.
Each line is `{timestamp, ordinal, type, payload, metadata?}`, with types
`session_meta`, `turn_context`, `world_state`, `response_item` (messages, reasoning,
function and custom tool calls and outputs, compactions), `event_msg` (item completion,
`token_count`, task start and completion, turn aborts), `token_usage_record`,
`compacted`, and `inter_agent_communication_metadata`.

- **Metering lives only here.** `token_count` carries the account’s rate limits (primary
  and secondary windows with used percent and reset time, credits, plan) and
  `token_usage_record` per-turn and per-thread token usage.
  No database holds either.

- **Rollouts are segmented.** A thread can continue in a second file named with a
  history id after the thread id, whose `session_meta` carries a `history_base` pointing
  back to the first segment.
  Ordinals continue across segments.

- **Rollouts are compressed when idle.** Of 21,300 files, 555 were plain `.jsonl`,
  20,713 were `.jsonl.zst`, 28 were `.jsonl.gz`, and 69 were 2025-era `rollout-*.json`
  files in an older format.
  `threads.rollout_path` keeps naming the uncompressed path.

- **Archived rollouts move** to `archived_sessions`, which can be a symlink to another
  volume.

- **Metering counts twice if read naively.** Each `token_usage_record` is followed by a
  `token_count` whose last usage repeats it, so a total counts one of the two.
  Nothing on disk holds prices, so Codex cost needs a price table the plugin supplies.

- **Turns are bracketed** by `task_started` and `task_complete` (with duration, time to
  first token, and any error), so a plain rollout whose last lifecycle event is
  `task_started` has a turn in flight.

- **`item_completed` is the cleanest structured source** in a rollout since about
  2026-07: command executions with exit code and duration, file changes with unified
  diffs, MCP tool calls, subagent activity, and web searches.
  Reasoning content is encrypted; only summaries are readable.

- **The format changed five times.** 2025-04 rollouts are single JSON documents from the
  TypeScript CLI; 2025-09 files are untyped JSONL; the typed envelope arrived about
  2025-12; `ordinal`, `item_completed`, and `world_state` about 2026-07; and
  `token_usage_record`, multi-agent messages, and segments from 2026-09 on.
  A reader that covers the history needs all five.

- **`originator` is the reliable origin field.** `source` reports `vscode` for desktop
  threads, and 72% of rollouts are children: automatic reviews and spawned subagents.

#### Other `~/.codex` Families

| Path pattern | Format | Write pattern | Joins on |
| --- | --- | --- | --- |
| `session_index.jsonl` | JSONL `{id, thread_name, updated_at}` | Append-only rename log; the last entry wins | Thread id; incomplete, mostly named threads |
| `.codex-global-state.json` | JSON | Rewritten whole by the desktop app | Project assignments, pinned threads, queued follow-ups, worktree cleanup queue, and per-thread permissions |
| `thread-writer-locks/<id>.lock` | Empty lock files | Held open by the app-server | Threads loaded now, not threads running |
| `shell_snapshots/<id>.<ns>.sh` | Bash | One per shell start | Thread id |
| `automations/<id>/automation.toml` | TOML | Rewritten on edit | Automation id, `target_thread_id`, `rrule`, status; no run history |
| `worktrees/<id>/<repo>/` | Git worktrees | Git-managed | A rollout’s `cwd`; many are remnants holding only a marker file |
| `visualizations/YYYY/MM/DD/<id>/` | Mixed artifacts | Created per turn output | Thread id |
| `browser/sessions/<id>.toml`, `computer-use/sessions/<id>.toml` | TOML | Rewritten | Per-thread allowed origins and apps |
| `config.toml`, `rules/default.rules` | TOML; Starlark `prefix_rule` | User and app edits; appended on “always allow” | Trusted projects, hook trust, plugins, MCP servers |
| `auth.json` | JSON with tokens | Rewritten on refresh | Secret |
| `models_cache.json`, `cache/*/<hash>.json` | JSON | Rewritten every few minutes | Model capabilities and context windows; no prices |
| `plugins/cache/`, `skills/`, `vendor_imports/`, `packages/` | Bundles and checkouts | Replaced per version | Plugin and skill names |
| `history.jsonl` | JSONL `{session_id, ts, text}` | Appended by the terminal UI only | Thread id |
| `node_repl/active_execs/`, `process_manager/`, `app-server-daemon/*.pid` | JSON | Written while running, but leaked: every recorded process was dead | None to trust without a liveness check |

Several families look live and are not: daemon pid files and sockets from September,
leaked process records, ambient suggestions idle since June, and temporary directories
never cleaned. A live view must check every process id it reads.

#### SQLite Databases

Codex keeps its catalog and projections in SQLite, in WAL mode.
The `_N` suffix in a file name is a store generation: a store is recreated, not
migrated, when it moves between files, and the schema changed 62 times in about eight
months, so a reader has to check columns rather than assume them.

| Database | Holds | Use for |
| --- | --- | --- |
| `state_5.sqlite` | `threads` (id, rollout path, created, updated, source, originator, model, effort, approval mode, sandbox policy, title, `cwd`, git branch and origin, cumulative tokens, archived), `thread_spawn_edges` (parent to subagent), `thread_attachments` (pull requests, worktrees), dynamic tools, read receipts, projects | The thread catalog and the subagent tree |
| `thread_history_1.sqlite` | `thread_turns` (status, `error_json`, start, completion, duration) and `thread_items` (the app-server’s `ThreadItem` union: reasoning, command execution with exit code and duration, agent and user messages, MCP tool calls, file changes with diffs, web searches, subagent activity) | Timelines, failures by error class, commands, file changes |
| `logs_2.sqlite` | Tracing logs: time, level, target, body, thread, process | Recent warnings and errors; keeps about the last 1,000 rows per thread and per process |
| `goals_1.sqlite` | Thread goals with status, token budget, and usage | Goals |
| `queue_1.sqlite` | Messages queued while a turn runs, with a revision counter | Queued work |
| `memories_1.sqlite` | Memory extraction jobs and outputs | Empty on this machine |
| `sqlite/codex.db` | The desktop app’s own store: its thread catalog, `active_chat_turns`, and `automations` | What the app is running now, and automation schedules |

- **`thread_history` is a projection of the rollouts**, kept current by a byte-offset
  cursor per history id, and it omits token counts, rate limits, turn context, and raw
  model content. It is still often the best copy to read, since it is indexed and
  uncompressed and survives an archived rollout on an unmounted volume.
- **History is keyed by segment.** The second segment’s turns and items are stored under
  its history id, not the thread id; ignoring that makes a busy thread look idle.
- **About 60% of threads are automatic reviews** (`thread_source = guardian_review`), so
  a useful thread list filters by source.
- **`inProgress` turns are not proof of running:** 159 of 160 were orphans from earlier
  crashes. What is running now comes from `codex.db`’s `active_chat_turns`, which the app
  refreshes about every minute, together with recent `updated_at_ms` and file times.
- **Reads are cheap and safe** when they use the indexes: the 50 most recent visible
  threads took 0.1 ms, a thread’s last 20 turns 0.03 ms, and the last 200 log lines 0.16
  ms. Over 1,440 read-only queries per database during active writes, none hit
  `SQLITE_BUSY`. Counting `thread_items` took 10 s and a full scan of `threads` about 20
  s, so a reader must never scan.
  A long-open read transaction stops checkpoints from resetting the WAL, so each read
  must finish promptly.

### Joining the Families

Both agents have a session (Claude) or thread (Codex) identifier that joins almost
everything:

- **Claude Code:** `sessions/<pid>.json` names the session id; the transcript, its
  `subagents/`, `tool-results/`, and `workflows/` directories, `file-history/<sid>/`,
  `session-env/<sid>/`, and telemetry files all carry it; memory files point back to
  their originating session.
  Inside a transcript, `tool_use.id` joins a subagent’s `meta.json`, `requestRef` joins
  a model call, and `messageId` joins file-history records to the prompt that caused
  them.
- **Codex:** `threads.id` names the rollout file, the history rows (through the segment
  rule), spawn edges, attachments, goals, queued items, logs, the desktop catalog,
  automations, and `thread-writer-locks/<id>.lock`. Turn ids join `thread_turns` to
  rollout `turn_context` and `token_usage_record` lines.

### What Answers Each Operational Question

| Question | Claude Code | Codex |
| --- | --- | --- |
| What is running now? | `sessions/<pid>.json` status, checked against the process; growing transcripts; unfinished subagents | `codex.db` `active_chat_turns`; recently updated threads; rollout and WAL modification times |
| Which sessions ran, where, with which model? | Transcript envelopes and metadata records; no index, so a catalog must be built | `state_5.threads`, indexed by recency |
| Tokens and cost per session, model, project, day | `usage` per unique `message.id`; `cost-state` for Claude Code’s own figure | `token_usage_record` in rollouts; cumulative `threads.tokens_used` |
| Rate-limit headroom over time | `quotaLimits` on error stubs only | `token_count.rate_limits` in rollouts |
| Which subagents ran, and what did they cost? | `subagents/*.meta.json` and transcripts; `queued_command.usage` | `thread_spawn_edges`; subagent threads’ own usage |
| Which files changed, before and after? | File-history records and backups; Edit and Write `structuredPatch` | `fileChange` items with diffs |
| Which commands ran, and their exit codes? | Bash `toolUseResult` | `commandExecution` items |
| Which hooks fired or failed? | `hook_*` attachments and `stop_hook_summary`; successful tool hooks leave no record | Not observed |
| Permission decisions | `permissionDecision`, `toolDenialKind` | `approval_mode` and `sandbox_policy` per thread |
| API errors and retries | `system` `api_error`; error stubs | `thread_turns.error_json`; `logs_2` errors |
| Compactions | `compact_boundary` | `contextCompaction` items, `compacted` lines |
| Scheduled work | `scheduled-tasks/` plus the desktop app’s schedule; runs marked `turnOrigin: scheduled` | `codex.db` `automations` and `automations/<id>/automation.toml` |
| Configuration in effect | `settings.json`, `~/.claude.json`, plugins, skills, agents | `config.toml`, rules, skills, plugins |

## Key Insights

- **The files are rich enough; what is missing is an index.** Every question above has a
  source, but Claude Code keeps no session catalog, and both agents spread a session
  across many files. The plugin’s main job is a bounded, incremental catalog that joins
  them, not new parsing.
- **Codex already has the index Claude Code lacks.** Its SQLite catalog answers list and
  timeline questions in milliseconds, and its rollouts are needed only for metering.
  Claude Code’s answers all come from transcripts, so a Claude catalog has to summarize
  each transcript once and update it as the file grows.
- **Both formats drift faster than Metabrowser releases.** Claude Code releases about
  daily and Codex migrates its schema about weekly.
  Parsers must accept unknown types and columns, and the plugin should report what it
  did not recognize, so drift shows up as a count instead of a silent gap.
- **The questions cross the served root.** Live sessions, the desktop apps’ stores, and
  account-wide counters sit outside `~/.claude` and `~/.codex`, and Metabrowser reads
  only inside the root it serves.
- **Secrets sit beside the operational data**: Claude’s peer tokens and OAuth account,
  Codex’s `auth.json`, and environment-derived values in shell snapshots.
  Metabrowser already shows any file it serves, so masking in a view is a convenience,
  not a boundary.

## Options Considered

### Option A: Extend the Built-In `agent-log` Plugin

**Description:** Add adapters and views to the existing built-in plugin, importing core
modules as the built-ins do today.

**Pros:**

- Least new structure.

**Cons:**

- Does not meet the owner’s requirement: the built-ins import private core modules
  (`agent_log/sidekick.py` reads `jsonl_view._JSONL_PARSE_MAX_BYTES`), so nothing shows
  the plugin contract is enough.
- Leaves agent-specific parsing in core (`logutil/parsing.py`), against the rule that
  core stays consumer-agnostic.

### Option B: One `agents` Plugin Using Only the Public Contract (Recommended)

**Description:** A new plugin package inside the Metabrowser distribution, discovered
through the `metabrowser.plugins` entry point exactly as an installed plugin is, that
imports only `metabrowser`’s public API in Python and uses only `window.metabrowser` in
the browser. Inside it, each agent is a provider module behind one interface.

**Pros:**

- The installed-plugin path is the one exercised, so whatever this plugin needs and the
  SDK lacks becomes an SDK addition every plugin gets.
- A test can enforce the boundary by checking imports, and the package can move to its
  own distribution later without changes.
- One plugin can show views across agents, such as everything running now.

**Cons:**

- The SDK gaps below block parts of it until they are filled.

### Option C: One Plugin per Agent

**Description:** Separate `claude-code` and `codex` plugins over a shared helper
package.

**Pros:**

- Each can be released, disabled, or replaced on its own.

**Cons:**

- A cross-agent view needs a third plugin or a host feature, and the shared helper
  becomes a contract of its own.

## Recommendations

### Plugin Structure

Build Option B: a package such as `src/metabrowser_agents/`, registered in
`pyproject.toml` under `[project.entry-points."metabrowser.plugins"]`, shipped in the
same wheel.

- **Boundary:** Python imports only names in `metabrowser.plugin_api.__all__` and
  `metabrowser.__all__`; JavaScript uses only `window.metabrowser`. A test fails on any
  other `metabrowser` import, which is how the plugin proves the contract is enough.
- **Providers:** one module per agent (`claude`, `codex`, later others) implementing a
  small interface: recognize a home directory, list sessions, describe a session, report
  live state, read metering, and register JSONL adapters.
  A cross-agent view iterates providers, so adding an agent adds a module, not a view.
- **Parsers move out of core.** The Claude, Codex, Gemini, and Pi adapters in
  `logutil/parsing.py` move into the plugin and register through `register_log_adapter`,
  and the existing `agent-log` views move with them.
  Every consumer ships in one artifact, so this needs no compatibility layer, only a
  changelog fragment.
- **Object types:** sessions, threads, subagents, and scheduled tasks are natural
  plugin-declared objects under the
  [object data model plan](../specs/active/plan-2026-11-14-object-data-model-and-views.md),
  which already proposes that plugins declare object types and their views.

### Proposed Views

| Surface | What it shows | Built from |
| --- | --- | --- |
| Home overview, for `~/.claude` or `~/.codex` | Running now; recent sessions; today’s tokens and cost; recent errors; scheduled work; parser drift counts | Provider catalog and live state |
| Sessions list | Sessions with project, model, origin (human, scheduled, subagent, review), status, duration, tokens, cost, and filters | Claude catalog; `state_5.threads` |
| Session page | The existing Log timeline plus a subagent tree, files changed with diffs, commands, hooks, permission decisions, compactions, API errors, and pull request links | Transcripts, subagents, file history; `thread_turns`, `thread_items` |
| Usage | Tokens and cost by day, model, and project; Codex rate-limit headroom over time | Catalog metering; rollout `token_count` |
| Configuration | Settings, hooks, permissions, plugins, skills, agents, MCP servers, with secrets masked | Settings and config files |

The diff views the plugin needs already exist: a file-history before and after pair or a
Codex `fileChange` diff can be handed to the diff plugin’s renderer.

### SDK Gaps

| Need | Today | Proposed addition |
| --- | --- | --- |
| Claim a SQLite file | `[[kind]]` rules see text and JSONL only; a plugin can only add a view to `binary` | A binary kind rule matched by extension, basename, or magic prefix |
| A dashboard for one folder | `registerView("folder")` adds a tab to every folder; Overview panels can opt out by returning null | A folder kind claimed by a marker, with its own views |
| A cross-session catalog | No plugin cache location or persistence API | A plugin cache directory and lifecycle in `plugin_api` |
| Live updates | `/api/stream` tails one JSONL file; plugins cannot subscribe to inventory events | A plugin-visible change subscription, or polling data hooks |
| Read zstd | gzip only | zstd through `ArtifactPath`, which needs either Python 3.14 or a vetted dependency under the supply-chain rules |
| Pages not tied to a file, such as “everything running now” | No plugin route-backed kinds; the GitHub plugin uses an internal seam | Route-backed kinds for plugins, as the object data model plan proposes |
| Files outside the served root | Safe-path confines reads to the root | An explicit, user-granted list of companion paths, or serving `~` |

### Evidence and Parity

Every route the plugin adds needs a `--api` golden and parity rows.
Real homes cannot be fixtures, since they hold private data, so the tests need small
synthetic homes: a generated `~/.claude` tree and a generated `~/.codex` with SQLite
databases built by a script from a pinned schema.
Each fixture should include unknown record types and columns, so the drift report is
pinned too.

### Phasing

1. **Fix today’s two gaps** in the existing path: detect current Claude Code transcripts
   beyond line 20 (or by the first record’s shape), and add a Codex rollout adapter.
2. **Create the plugin skeleton** with the boundary test, and move the four adapters and
   the `agent-log` views into it.
3. **Add the Claude Code provider:** the incremental session catalog, live sessions, and
   the session page’s subagent, file-history, hook, and permission sections.
4. **Add the Codex provider:** the catalog over `state_5`, timelines from
   `thread_history`, and metering from rollouts.
5. **Add usage and drift views** over both providers.
6. **Add the SDK features** as each phase needs them, each in the commit that first uses
   it.

## Open Questions

1. **Served root:** should the operator open `~/.claude` and `~/.codex` separately, with
   a dashboard on each, or should Metabrowser serve one root that holds both, such as
   `~`, with the cost of inventorying the whole home?
2. **Companion paths:** may the plugin read `~/.claude.json`, the Claude desktop app’s
   store, and the temporary task directories, which sit outside both homes?
   They hold the live-session and schedule data a full view needs.
3. **Packaging:** a separate top-level package in the same wheel through the entry point
   (recommended), or a directory under `builtin_plugins` with the import-boundary test?
4. **Secrets:** mask known secret fields in the plugin’s views and its `--api` answers,
   knowing that the raw file stays readable through the ordinary file views?
5. **zstd:** wait for Python 3.14 as the floor, or vet a zstd package now?

## References

- [Plugin Authoring](../../plugins.md) and
  [Plugin System](../architecture/arch-plugin-system.md)
- [Reading Agent Logs](../../working-with-agents.md#reading-agent-logs)
- [Live Delivery](../architecture/arch-live-delivery.md)
- [Object Data Model and Views](../specs/active/plan-2026-11-14-object-data-model-and-views.md)
- [Parity Registry](../architecture/arch-parity-registry.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
