# Plan for Operational Views of Claude Code and Codex

**Date:** 2026-11-19

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Draft for the owner’s review.
It builds on the
[agent home visibility research brief](../../research/research-2026-11-19-agent-home-visibility.md),
which surveys every file format under `~/.claude` and `~/.codex` and recommends an
`agents` plugin built only on the public plugin contract.
Bead `mb-d7q6` tracks the research; this plan’s beads are created when the owner accepts
it. [Open Questions](#open-questions) lists what the owner decides.

## The Owner’s Words

On 2026-11-19, after the research brief:

> Let’s also design from first principles what the operational visibility for Claude
> Code or Codex should be, including what the key things to keep aware of:
> 
> for all of history
> 
> - total number of sessions
> - sizes of sessions (maybe a histogram?)
> - timelines of these sessions (maybe a visual if we know, ordered by timeline and
>   scrollable somehow?)
> - tallies of model usage, token usage, etc.
> - logs to drill down on each and browse
> 
> for very recently active or live
> 
> - sessions
> - current events
> 
> and for all logs, historic and live
> 
> - tallies of all kinds of records, divided by type
> - color coding each type in a consistent design system across pages
> - coloring and showing tool usage rollups
> - performance on each kind of record, including time/latency reports
> 
> anything else? let’s make sure this is designed to give full visibility, and that this
> framework could be used to give a consistent UI for both Claude and Codex.
> There are things that are specific to Claude or Codex.
> We could put those too.

Then:

> we could use urollup as a tool for this and enhance it as needed to do rollups.
> For example, Metabrowser could work normally, but if it has that installed, it would
> have much faster roll-up of usage stats and token stats.

And:

> Let’s think of how to implement this in phases so the basic features all work, and
> then the more detailed stats are supported in phases as we implement them.

## Overview

An operator running coding agents needs to answer six questions at a glance and then
drill down from any answer to the records behind it:

1. **What is running now, and what is it doing?**
2. **What ran, when, where, and for how long?**
3. **What did it consume?** Tokens, by model, project, and day, and rate-limit headroom.
4. **What did it do?** Records by kind, tools by family, files changed, commands run.
5. **What was slow or failed?** Latency by record kind and tool, errors, retries,
   denials.
6. **Can I trust these numbers?** Which sources were read, which were skipped, and which
   record shapes the parsers did not recognize.

This plan designs one set of views that answers them identically for Claude Code and
Codex. Each agent is a provider that maps its own files onto one shared model.
The views read only that model.
Agent-specific facts, such as Claude Code’s file history or Codex’s rate-limit windows,
appear as provider sections.
A view shows such a section only when the provider supplies it.

The work ships in five phases.
Phase 1 makes the basic surfaces work end to end: the catalog, the home page, the
session list, the session page, and what is running now.
Each later phase adds one family of detailed statistics to surfaces that already exist.

## Goals

- One home page, session list, session page, timeline, and statistics vocabulary for
  both agents, so a reader who learns one agent’s views can read the other’s.
- Every number drills down to the sessions and records it counts.
- One color per record kind, used everywhere that kind appears: Log badges, tally bars,
  chart series, timeline segments, and live events.
- Live and historic data use the same model, so the live views need no special cases.
- Whole history stays fast.
  A cached per-session summary means a restart re-reads only what changed.
  When `urollup` is installed, usage and token rollups use it.
- Every route has a `metab --api` equivalent and a golden, per the parity rules in
  `AGENTS.md`.

## Non-Goals

- **Acting on an agent:** no stopping sessions, editing settings, approving permissions,
  or sending prompts. The views are read-only.
- **Sending data anywhere.** Everything stays on the machine.
- **Pricing in the first phases.** Cost needs a maintained price table.
  That is an open question, and `urollup` plans one.
- **Other agents now.** Gemini and Pi keep today’s Log view.
  The provider interface is designed so they can be added later as providers.

## Background

The research brief establishes the facts this plan relies on:

- Current Claude Code transcripts and Codex rollout files are not recognized by today’s
  `agent-log` plugin.
- Codex compresses most idle rollouts with zstd, which Metabrowser cannot read yet.
- Codex keeps an indexed thread catalog in `state_5.sqlite`, while Claude Code has no
  index, so its catalog must be built.
- Tokens must be deduplicated: Claude Code writes one assistant record per content block
  and copies history on resume and fork.
  Codex has cumulative and per-turn counters that must not be added together.
- Live state must be checked against running processes, since both agents leave stale
  pid files and orphaned in-progress turns.
- Indexed SQLite reads are cheap; scans are not.

`urollup` is a first-party Rust CLI built to produce trustworthy token and usage reports
from Claude Code and Codex logs.
It reconciles copied, resumed, and overlapping history, so each request is counted once.
Version 0.1 provides `report`, `daily`, and `sessions` with JSON output.
Its design plans portable, mergeable summaries.
On 2026-11-19, the copy installed on the survey machine, built 2026-09-16, refused
whole-history runs over 512 MiB of decoded input.
A build of its current checkout has no such limit, and `urollup sessions --all` read the
survey machine’s whole history in 60 s with eight workers:

- Discovery took 4 s.
- Codex ingest took 42 s, over 21,323 sources, most of them compressed.
- Claude Code ingest took 12 s, over 2,402 sources.

So neither engine can roll up whole history on every page load.
Metabrowser must cache per-session results, and `urollup` needs an incremental mode
before it can stand behind a live page.

## Design

### The Shared Model

Every provider maps its files onto these entities:

| Entity | Claude Code | Codex |
| --- | --- | --- |
| **Home** | `~/.claude` | `~/.codex` |
| **Session** | One transcript (`sessionId`) | One thread (`threads.id`), across its segments |
| **Child session** | A subagent transcript, joined by `agentId` and `toolUseId` | A spawned thread, joined by `thread_spawn_edges` |
| **Turn** | A user prompt to the end of the agent’s response | A `thread_turns` row or a `turn_context` span |
| **Record** | A transcript line | A rollout line or a `thread_items` row |
| **Model request** | Assistant records sharing one `message.id` | A response with its `token_usage_record` |
| **Tool call** | A `tool_use` and its `tool_result` | A function or command call and its output |

A session carries the same fields for both agents:

- **Identity:** agent, session id, title, parent session, and children.
- **Origin:** human, scheduled, subagent, automatic review, or automation.
- **Place:** project (the working directory) and git branch, where recorded.
- **Time:** start, end, active time, and waiting time.
- **Size:** bytes on disk, records, turns, and model requests.
- **Models used**, and **status:** running, finished, failed, or unknown.

Waiting time is the time between the end of a turn and the next prompt.
It is shown apart from active time, so a session left open overnight does not look slow.

### Record Kinds

The record kind is the one vocabulary every tally, color, and latency report uses.
Each provider maps its raw record types onto a fixed set of normalized kinds and keeps
the raw type for drill-down:

| Kind | Meaning | Claude Code examples | Codex examples |
| --- | --- | --- | --- |
| `prompt` | Input from the user or a schedule | `user` with text | `user_message`, user `response_item` |
| `text` | The agent’s visible output | `assistant` text block | `agent_message` |
| `thinking` | Reasoning | `thinking` block | `reasoning` |
| `tool-call` | A tool invoked | `tool_use` | `function_call`, `exec_command_begin` |
| `tool-result` | A tool’s output | `tool_result` | `function_call_output`, `exec_command_end` |
| `subagent` | A child session started or finished | Task `tool_use`, subagent meta | spawn edges, collaboration items |
| `file-change` | A file written, with a diff | Edit and Write patches, file history | `fileChange` items |
| `metering` | Token or rate-limit accounting | `usage`, `cost-state` | `token_count`, `token_usage_record` |
| `control` | Permission, hook, and approval events | `permissionDecision`, hook attachments | approvals, sandbox decisions |
| `context` | Session setup and context management | `system` init, `compact_boundary` | `session_meta`, `turn_context`, compactions |
| `error` | A failure | `api_error`, error stubs | `error_json`, error events |
| `unknown` | A record the provider does not recognize | any new type | any new type |

A tally of records has two levels: the kind, then the raw types under it.
The provider’s mapping table is a value in code, and a golden pins it.
`unknown` is never silently dropped: it feeds the drift report under
[Trust and Health](#trust-and-health).

Tools are grouped by family the same way: shell, read, edit, search, web, MCP (as
`mcp:<server>.<tool>`), subagent, and other.
The provider maps each tool name to a family and keeps the name for drill-down.

### One Color System

Color carries one meaning on these pages: **the record kind**, or **the tool family** in
tool views.

- Each kind gets shell tokens: `--agent-kind-<kind>-bg` and `-text` for badges, and
  `-fill` for chart series, tally bars, and timeline segments.
  Tool families get `--agent-tool-<family>-*`.
- These replace the `agent-log` plugin’s private `--agent-log-kind-*` tokens.
  Review A1 on jlevy/metabrowser#622 found two pairs of those hard to tell apart in a
  chart.
- `tests/test_design_vocabulary.py` gains two checks.
  Every `-text` token must reach 4.5:1 contrast on its `-bg` in both themes, and every
  pair of `-fill` tokens must differ by at least a minimum perceptual distance.
  That minimum is a value in code, set from a measurement.
- The agent and the origin are shown as labels and icons, never as color.
  A page that mixes Claude Code and Codex then reads the same way as a page with only
  one.
- Status (running, failed) uses the existing `--status-*` and `--badge-*` tokens.

### Latency

Each latency is defined once and computed the same way for both agents:

| Measure | From | To |
| --- | --- | --- |
| **Model latency** | The record that triggers a model request (a prompt or a tool result) | The first record of the response |
| **Model request duration** | The same start | The last record of the response |
| **Tool latency** | A tool call | Its result, joined by call id |
| **Turn duration** | A prompt | The end of the turn |
| **Waiting time** | The end of a turn | The next prompt |

A recorded duration is used where the agent writes one, such as a Codex turn’s or
command’s duration.
Otherwise the duration is inferred from timestamps, and reports label
it as inferred.

Distributions are stored as fixed log-spaced histograms.
Merging two histograms is exact, so per-session summaries add up to any group (day,
project, model, kind, or tool) without keeping raw values.
Percentiles are read from the merged histogram, accurate to within one bucket.
The bucket bounds are a value in code.

### Surfaces

All surfaces are views of the `agents` plugin.
Each is backed by a route that `metab --api` reaches.

- **Agents home.** One page for a served home, and one for a root that holds both homes.
  - Totals: sessions, sessions running now, records, tokens, and size on disk.
  - A **live strip** of running sessions, each with its project, model, current record
    kind, and the age of its last record.
  - Sessions per day, a histogram of session sizes (log-spaced, by bytes or by turns),
    and the most recent sessions.
  - Later phases add usage, record-kind, and tool panels.
- **Session list.** Sortable columns: agent, title, origin, project, model, start,
  duration, turns, size, tokens, errors, and status.
  - Filters by agent, origin, project, model, status, and date range.
  - Automatic reviews are hidden by default, since they are most Codex threads.
- **Session page.** A header with the session’s identity, origin, place, time, size,
  models, and status. Tabs:
  - **Log:** today’s Log timeline, now recognized for both agents and colored by kind.
  - **Stats:** record tallies, tool rollup, and latency.
  - **Children:** the subagent tree, with each child’s size, duration, and tokens.
  - **Changes:** files changed, with diffs through the diff plugin’s renderer.
  - **Raw**, plus provider sections such as Claude Code’s hooks and permissions or
    Codex’s goals and queued messages.
- **Timeline.** A horizontal time axis with one lane per project.
  - Sessions are bars, with their children nested under them.
  - It scrolls and zooms from hours to months, and keeps only the visible window in the
    page.
  - At close zoom, a bar breaks into turns colored by record kind.
  - Clicking a bar opens its session.
  - The rendering technique (DOM, SVG, or canvas) and its bounds are set from a Chrome
    measurement, per [rendering large content](../../../large-content-rendering.md).
- **Live events.** One merged, following tail of new records across running sessions,
  colored by kind.
  - It can pause, filter by agent, session, or kind, and open any record in its session.
- **Usage.**
  - Tokens by day, stacked by model.
  - Tallies by model, project, origin, and agent.
  - Input, output, cache read, and cache creation shown apart, so cache efficiency is
    visible.
  - Codex rate-limit headroom over time.
- **Records and tools.** Across all history or a filtered set:
  - Record tallies by kind and raw type, over time.
  - The tool rollup: calls, errors, and latency percentiles per family and tool.
  - Latency reports per kind, each with its slowest instances linked.
- **Errors.** API errors, tool errors, failed turns, hook failures, and permission
  denials, grouped by class, with counts over time and links to each.
- **Configuration.** Settings, hooks, permissions, plugins, skills, agents, MCP servers,
  scheduled tasks, and automations, with known secret fields masked.
- **Health**, under [Trust and Health](#trust-and-health).

### What Else Full Visibility Needs

Beyond the owner’s list, these are needed to answer the six questions:

- **Errors and retries**, since a session can finish while most of its requests failed.
- **Rate-limit headroom** for Codex, and Claude Code’s quota errors, since running out
  stops work.
- **Concurrency:** how many sessions and subagents run at once, from the timeline.
- **Cache efficiency:** cache reads compared with fresh input.
  It is often the largest lever on token use.
- **Context growth and compactions**, which explain slow and expensive late turns.
- **Subagent attribution:** what a parent session cost including its children, without
  counting a child twice.
- **Active time and waiting time**, kept apart.
- **Files changed, commands run, and pull requests** a session produced, from file
  history, `fileChange` items, and Codex thread attachments.
- **Permission prompts and hook outcomes**, which show where a person had to step in.
- **Scheduled and automated runs**, kept apart from interactive ones.
- **Disk use and retention** per family, since subagent transcripts dominate
  `~/.claude`.
- **Trust:** drift, skipped sources, and the engine behind each number.

### Agent-Specific Sections

The shared model covers most of each agent’s data.
What remains appears as provider sections.
A provider declares which sections it supplies, and a view lists a section only when it
is declared.

- **Claude Code:**
  - File-history versions with before-and-after diffs.
  - Hook firings and failures, and permission decisions with denial kinds.
  - Claude Code’s own `cost-state` figure, next to the computed one.
  - Workflow runs, and desktop scheduled tasks.
  - Memory files with their originating session.
- **Codex:**
  - Rate-limit windows over time.
  - Reasoning effort, approval mode, and sandbox policy per thread.
  - Automatic reviews (`guardian_review`) as their own origin.
  - Goals with budgets, and queued messages.
  - Automations with their schedules.
  - Thread attachments (pull requests and worktrees), and recent warnings and errors
    from `logs_2`.

### Trust and Health

A Health page, and a line on the home page, report:

- Every source read, with its size.
- Every source skipped, and why: compressed, over a limit, or outside the served root.
- Counts of `unknown` records, and of SQLite columns the provider did not expect, by raw
  type and by agent version, so a new release that changes a format shows up the day it
  lands.
- Catalog freshness, and which engine produced each measure: the built-in Python engine
  or `urollup` with its version.

### Engines and the Catalog

Each provider exposes these operations:

- **Discover** the sessions in a home.
- **Summarize** one session into a fixed-schema summary.
- **Stream** a session’s normalized records.
- **Report live state**, checked against running processes.

A summary holds the session fields, two-level record tallies, tool rollups, latency
histograms, deduplicated token totals by model, child ids, error counts, and drift
counts.

**The catalog** stores one summary per session, keyed by source path, size, modification
time, and parser version.

- A startup or a change re-summarizes only sessions whose key changed.
  A growing live transcript is re-read from its last offset.
- Every aggregate is a merge of summaries, so the home page never reads a transcript.
- The catalog needs a plugin cache directory, which the research brief lists as an SDK
  gap.
- For Codex, the catalog starts from `state_5.sqlite` through indexed reads, so Phase 1
  needs no rollout and no zstd.

**The built-in engine** is Python in the plugin, and it always works.

**`urollup`** accelerates the measures it owns when it is installed:

- **Detection:** at startup the plugin looks for `urollup` on `PATH`. If its version
  meets a floor, which is a value in code, usage and token measures come from its JSON
  (`sessions` and `daily`).
- **Fallback:** when it is absent, too old, or fails, the built-in engine computes the
  same measures, and Health shows which engine ran.
- **Doctor:** `metab doctor` reports `urollup`’s presence and version, following the
  [command-line dependencies plan](plan-2026-11-18-cli-dependencies-and-doctor.md).
- **Equality:** a test runs both engines on the synthetic homes and requires identical
  usage numbers, so having `urollup` installed changes speed, never results.

Planned `urollup` additions, which let Metabrowser take more from it:

- An incremental mode, which re-reads only changed sources.
- Per-session record-kind tallies, tool rollups, and latency histograms in the same
  shape as the plugin’s summary.
- A versioned JSON contract for that summary.
- Its planned mergeable summaries, so a summary from another machine can be added in.

`urollup` is first-party, so these are ordinary feature work in its repository.
Each lands there before Metabrowser relies on it.

### Routes and Parity

The plugin adds data-hook routes for these surfaces:

| Route | Returns |
| --- | --- |
| `catalog` | Homes, totals, freshness, and engine |
| `sessions` | Filtered, sorted session rows |
| `session` | One session’s summary and provider sections |
| `stats` | Tallies, tool rollups, and latency for a filter and a grouping |
| `usage` | Token tallies for a filter and a grouping |
| `timeline` | Sessions and turns in a time window |
| `live` | Running sessions and records since a cursor |
| `health` | Sources, skips, drift, and engines |

Parity requirements:

- Every route gets a `metab --api` golden over synthetic homes and a row in the
  [Parity Registry](../../architecture/arch-parity-registry.md).
- The timeline’s zoom-and-scroll state machine and the live tail’s follow-and-pause
  state machine run browserlessly against the production JavaScript, with golden
  sessions.
- Only paint is browser-only.

## Implementation Plan

Every phase is usable on its own.
Each later phase adds statistics to the surfaces the earlier phases built.

### Phase 1: Basic Visibility

- [ ] Fix today’s two gaps in the existing path:
  - Recognize current Claude Code transcripts past line 20.
  - Add a Codex rollout adapter for plain `.jsonl` rollouts.
  - Give `agent-log` a `[[kind]]` rule for the `codex` adapter.
- [ ] Create the `agents` plugin package and its import-boundary test.
- [ ] Make adapter detection registry-driven, and move the four adapters and the
  `agent-log` views into the plugin.
- [ ] Define the shared model, the provider interface, the record kinds, and each
  provider’s mapping table.
- [ ] Add the record-kind color tokens and their contrast and distinctness checks.
  Use them in the Log view’s badges and in the Charts view.
- [ ] Build the catalog with the plugin cache directory (an SDK addition).
  Use it in the Claude Code provider, and in the Codex provider over `state_5.sqlite`.
- [ ] Build the agents home: totals, sessions per day, the size histogram, recent
  sessions, and the live strip.
- [ ] Build the session list and the session page’s header and Log tab.
- [ ] Add a synthetic-home generator, and goldens for `catalog`, `sessions`, `session`,
  and `live`.

**Done when:** opening either home shows every session with its size and time, what is
running now, and any session’s log, all colored by record kind.

### Phase 2: Timeline and Live Events

- [ ] Measure timeline rendering in Chrome, and set the technique and its bounds from
  the measurement.
- [ ] Build the timeline with nested children and the per-turn breakdown at close zoom.
- [ ] Build the live events tail.
- [ ] Add the `timeline` and `live` cursor goldens, and the browserless state-machine
  sessions.

**Done when:** all history scrolls as a timeline, and new records from running sessions
appear in one tail.

### Phase 3: Usage and Tokens

- [ ] Add deduplicated token tallies to the summary, with the Claude Code and Codex
  deduplication rules from the research brief.
- [ ] Build the Usage page and the home page’s usage panel.
- [ ] Add Codex rate-limit headroom.
- [ ] In `urollup`, add the incremental mode.
  Then add `urollup` detection, the version floor, the fallback, the doctor check, and
  the engine-equality test to Metabrowser.
  Until the incremental mode lands, use `urollup` only to fill the catalog in the
  background.
- [ ] Add the `usage` goldens.

**Done when:** tokens by model, project, origin, and day are correct with or without
`urollup`, and faster with it.

### Phase 4: Records, Tools, and Latency

- [ ] Add two-level record tallies, tool rollups, and latency histograms to the summary.
- [ ] Build the session page’s Stats tab, the Records and Tools page, and the Errors
  page.
- [ ] Add the tool-family color tokens.
- [ ] Add the `stats` goldens.
- [ ] In `urollup`, add the same tallies and histograms, so the accelerator covers them.

**Done when:** every record kind and tool has counts, errors, and latency percentiles,
for one session or any group, each linked to its slowest instances.

### Phase 5: Agent-Specific Depth and Trust

- [ ] Add the Children and Changes tabs.
- [ ] Add the provider sections listed under
  [Agent-Specific Sections](#agent-specific-sections).
- [ ] Build the Configuration page with secret masking.
- [ ] Build the Health page and the drift report.
- [ ] Read zstd rollouts and transcripts, as the owner decides under
  [Open Questions](#open-questions).

**Done when:** every family the research brief lists that answers an operator question
has a view, and Health accounts for every source.

## Testing Strategy

- **Synthetic homes:** a generator builds a `~/.claude` and a `~/.codex`, including
  SQLite databases, from pinned schemas.
  Each covers every record kind, resumed and forked history, a subagent tree, a live
  session, and `unknown` record types.
  Real homes hold private data, so they are never fixtures.
- **Goldens:** a `metab --api` golden for every route, and a golden for each provider’s
  mapping table.
- **Engine equality:** both engines run on the synthetic homes and must give identical
  usage numbers.
- **Browserless state machines** for the timeline and the live tail.
- **Chrome measurements** set the timeline and tail bounds, recorded beside their
  constants.
- **Design checks:** the contrast and distinctness tests for the kind and tool tokens.

## Open Questions

The research brief’s open questions still stand: the served root, companion paths,
packaging, secret masking, and zstd.
This plan adds:

1. **Cost:** show estimated cost from a price table, and if so, whose table?
   `urollup` plans one.
2. **`urollup` floor:** which release should be the minimum, and should `metab doctor`
   suggest installing it when it is absent?
3. **Default filters:** hide Codex automatic reviews and Claude Code subagents from the
   session list by default, and show them as children instead?
4. **Retention:** should the Health page suggest pruning old subagent transcripts, or
   only report their size?

## References

- [Agent home visibility research brief](../../research/research-2026-11-19-agent-home-visibility.md)
- [Plugin Authoring](../../../plugins.md)
- [Parity Registry](../../architecture/arch-parity-registry.md)
- [Rendering large content](../../../large-content-rendering.md)
- [Command-line dependencies and doctor plan](plan-2026-11-18-cli-dependencies-and-doctor.md)
- [Design System](../../../design-system.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
