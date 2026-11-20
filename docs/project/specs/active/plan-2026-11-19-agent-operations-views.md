# Plan for Operational Views of Claude Code and Codex

**Date:** 2026-11-19

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Draft for the owner’s review, revised for review A on jlevy/metabrowser#623.
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
5. **What was slow or failed?** Latency by event kind and tool, errors, retries,
   denials.
6. **Can I trust these numbers?** Which sources were read, which were skipped, and which
   record shapes the parsers did not recognize.

This plan designs one set of views that answers them identically for Claude Code and
Codex. Each agent is a provider that maps its own files onto one shared model.
The views read only that model.
Agent-specific facts, such as Claude Code’s file history or Codex’s rate-limit windows,
appear as provider sections.
A view shows such a section only when the provider supplies it.

The work ships in six phases:

- **Phase 1** makes today’s Log view recognize both agents’ current logs.
- **Phase 2** makes the basic surfaces work end to end: the catalog, the home page, the
  session list, the session page, and what is running now.
- **Each later phase** adds one family of detailed statistics to surfaces that already
  exist.

## Goals

- One home page, session list, session page, timeline, and statistics vocabulary for
  both agents, so a reader who learns one agent’s views can read the other’s.
- Every number drills down to the sessions and events it counts, with copied history
  counted once.
- One color per event kind, used everywhere that kind appears: Log badges, tally bars,
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

[`urollup`](https://github.com/jlevy/urollup) is a first-party Rust CLI built to produce
trustworthy token and usage reports from Claude Code and Codex logs.
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

### Events and Kinds

The unit every tally, color, and latency report counts is an **event**, not a raw
record. One raw record can yield several events.
A Claude Code assistant record yields one per content block, plus a `metering` event
when it carries `usage`. A Codex `thread_items` row yields one.

Each provider maps every event to exactly one kind through an ordered mapping table: the
first rule matching the raw type, subtype, and content-block type wins.
The provider keeps the raw type for drill-down.

| Kind | Meaning | Claude Code examples | Codex examples |
| --- | --- | --- | --- |
| `prompt` | Input from the user, a schedule, or a queue | `user` with text, `queue-operation` enqueue | `user_message`, user `response_item` |
| `text` | The agent’s visible output | `assistant` text block | `agent_message` |
| `thinking` | Reasoning | `thinking` block | `reasoning` |
| `tool-call` | A tool invoked, including a subagent spawn or a file edit | `tool_use` block | `function_call`, `exec_command_begin`, `fileChange` |
| `tool-result` | A tool’s output | `tool_result` block | `function_call_output`, `exec_command_end` |
| `metering` | Token, request, or rate-limit accounting | `usage` on an assistant record, `cost-state`, `api-request*` | `token_count`, `token_usage_record` |
| `control` | Permission, hook, and approval events | `permissionDecision`, hook attachments | approvals, sandbox decisions |
| `context` | Session setup, titles, state, and context management | `system` init, `compact_boundary`, `attachment`, `custom-title`, `last-prompt`, `agent-name`, `file-history-snapshot` | `session_meta`, `turn_context`, `world_state`, compactions |
| `error` | A failure | `api_error`, error stubs | `error_json`, error events |
| `unknown` | An event no rule matches | any new type | any new type |

Subagent spawns and file changes are tool calls.
Their tool family (`subagent` or `edit`) and the provider sections set them apart, so
they never count twice.

Each provider’s mapping table is a value in code.
A golden pins it, along with a classification of every raw type the research survey
observed. A tally has two levels: the kind, then the raw types under it.
`unknown` is never silently dropped; it feeds the drift report under
[Trust and Health](#trust-and-health).

Tools are grouped by family: shell, read, edit, search, web, MCP (as
`mcp:<server>.<tool>`), subagent, and other.
The provider maps each tool name to a family and keeps the name for drill-down.

### One Color System

Color carries one meaning on these pages: the event kind, or the tool family where tools
are rolled up.

- The `agents` plugin’s stylesheet defines `--agent-kind-<kind>-bg` and `-text` for
  badges, and `-fill` for chart series, tally bars, and timeline segments.
  It defines `--agent-tool-<family>-*` the same way.
  They live in the plugin, not the shell, because the plugin boundary keeps domain
  styles out of core. They are built from the shell’s palette tokens.
- They replace the `agent-log` plugin’s private `--agent-log-kind-*` tokens.
  Review A1 on jlevy/metabrowser#622 found two pairs of those hard to tell apart in a
  chart.
- The design checks in `tests/test_design_vocabulary.py` extend to the `agents` package.
  - Every `-text` token must reach 4.5:1 contrast on its `-bg` in both themes.
  - Kinds and tool families form one palette, since the Records and Tools page shows
    both. Every pair of `-fill` tokens in it must differ by at least a minimum perceptual
    distance, which is a value in code set from a measurement.
- The agent and the origin are shown as labels and icons, never as color.
  A page that mixes Claude Code and Codex then reads the same way as a page with only
  one.
- Status (running, failed) uses the shell’s `--status-*` and `--badge-*` tokens.

### Latency

Each measure is defined once.
Where the two agents’ records cannot support the same definition, the difference is
named, and reports label it.

| Measure | From | To | Claude Code | Codex |
| --- | --- | --- | --- | --- |
| **Event latency by kind** | The previous event in the session | This event, counted under this event’s kind | From timestamps | From timestamps |
| **Model latency** | The event that triggers a model request (a prompt or a tool result) | The first event of the response | Time to the first complete content block, since records are written per block | The same, plus time to first token where the agent records it, shown apart |
| **Model request duration** | The same start | The last event of the response | Inferred | Inferred, or recorded where a duration is written |
| **Tool latency** | A tool call | Its result, joined by call id | Includes any wait for a person’s permission; the wait is split out when a permission record times it | Recorded command durations where present |
| **Turn duration** | A prompt | The end of the turn | Inferred | Recorded in `thread_turns` |
| **Waiting time** | The end of a turn | The next prompt | Inferred | Inferred |

Event latency by kind answers the owner’s question of performance per record kind.
The gap before each event is attributed to the kind of that event.
The gap before a `prompt` is waiting time, not latency, so it is kept out of the latency
report.

Distributions are stored as fixed log-spaced histograms, each with an exact count, sum,
minimum, and maximum.
Merging is exact, so per-session summaries add up to any group (day, project, model,
kind, or tool) without keeping raw values.
Means and maxima are exact.
Percentiles come from the merged histogram, accurate to within one bucket.
The bucket bounds are a value in code.

### Copied History and Ownership

Both agents copy history: Claude Code on resume and fork, and Codex across segments.
Counting per session is not enough, because a resumed session repeats requests that its
original session already counted.

- **Ownership rule:** every model request and event belongs to the first session that
  wrote it. That is the earliest timestamp, and the ties are broken by session id.
- **Ownership index:** the catalog keeps an index from each request’s identity (Claude
  Code’s `message.id` and record `uuid`, and Codex’s response and item ids) to its
  owning session.
- **Replays:** Claude Code records naming another `sessionId` are resumed replays.
  The provider follows the rules `urollup` documents in its
  [Claude Code](https://github.com/jlevy/urollup/blob/main/docs/formats/claude-code.md)
  and [Codex](https://github.com/jlevy/urollup/blob/main/docs/formats/codex.md) format
  notes.
- **Totals:** a summary counts owned and copied events separately, and every aggregate
  sums only owned ones.
  A session page shows both, so a resumed session explains its size.
- **Parents and children:** a parent’s total including children adds each child once,
  through the ownership rule.

### Drill-Down

Every number links to what it counts:

- An aggregate cell is a filter.
  Opening it runs the `sessions` route with that filter.
- Summaries keep locators: a session id, plus a byte offset or an item id.
  They keep one for every error, and for the slowest events of each kind and tool, up to
  a bound that is a value in code.
- The `records` route streams one session’s normalized events, filtered by kind, tool,
  or locator. A slowest-instance link opens the session’s Log at that event.

### Surfaces

All surfaces are route-backed pages of the `agents` plugin, which is the SDK addition
named in Phase 2. Each is backed by a route that `metab --api` reaches.

- **Agents home.** One page for each home under the served root, and a combined page
  when the root holds both.
  - Totals: sessions, sessions running now, events, tokens, and size on disk.
  - A **live strip** of running sessions, each with its project, model, current event
    kind, and the age of its last event.
  - Sessions per day, a histogram of session sizes (log-spaced, by bytes or by turns),
    and the most recent sessions.
  - Later phases add usage, event-kind, and tool panels.
- **Session list.** Sortable columns: agent, title, origin, project, model, start,
  duration, turns, size, tokens, errors, and status.
  - Filters by agent, origin, project, model, status, and date range.
  - Automatic reviews are hidden by default, since they are most Codex threads.
- **Session page.** A header with the session’s identity, origin, place, time, size,
  models, and status. Tabs:
  - **Log:** the Log timeline, colored by kind.
    Claude Code’s comes from the transcript.
    Codex’s comes from `thread_history`, which is indexed and uncompressed, so it needs
    no zstd.
  - **Stats:** event tallies, tool rollup, and latency.
  - **Children:** the subagent tree, with each child’s size, duration, and tokens.
  - **Changes:** files changed, with diffs through the diff plugin’s renderer.
  - **Raw**, a link to the source file’s own view, and the provider sections, such as
    Claude Code’s hooks and permissions or Codex’s goals and queued messages.
- **Timeline.** A horizontal time axis with one lane per project.
  - Sessions are bars, with their children nested under them.
  - It scrolls and zooms from hours to months, and keeps only the visible window in the
    page.
  - At close zoom, a bar breaks into turns colored by event kind.
  - Clicking a bar opens its session.
  - The rendering technique (DOM, SVG, or canvas) and its bounds are set from a Chrome
    measurement, per [rendering large content](../../../large-content-rendering.md).
- **Live events.** One merged, following tail of new events across running sessions,
  colored by kind.
  - It polls the `live` route with a cursor, so it needs no change-subscription API.
  - It can pause, filter by agent, session, or kind, and open any event in its session.
- **Usage.**
  - Tokens by day, stacked by model.
  - Tallies by model, project, origin, and agent.
  - Input, output, cache read, and cache creation shown apart, so cache efficiency is
    visible.
  - Codex rate-limit headroom over time.
- **Records and tools.** Across all history or a filtered set:
  - Event tallies by kind and raw type, over time.
  - The tool rollup: calls, errors, and latency percentiles per family and tool.
  - Event latency by kind, each with its slowest instances linked.
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
- Counts of `unknown` events, and of SQLite columns the provider did not expect, by raw
  type and by agent version, so a new release that changes a format shows up the day it
  lands.
- Catalog progress and freshness, per measure family.
- Which engine produced each measure family: the built-in Python engine, or `urollup`
  with its version.

### Engines and the Catalog

Each provider exposes these operations:

- **Discover** the sessions in a home.
- **Summarize** one session into a summary.
- **Stream** a session’s normalized events.
- **Report live state**, checked against running processes.

A summary is split into **measure families**, each with its own schema version:

- **Session:** identity, origin, place, time, size, models, status, and children.
- **Usage:** owned and copied token totals by model, and rate-limit samples.
- **Events:** two-level tallies, tool rollups, latency histograms, locators, and errors.
- **Drift:** unknown types and columns.

A later phase adds a family without invalidating the families already cached.

**The catalog** stores each session’s summary in a plugin cache directory, keyed by
source path, size, modification time, and family version.

- **Fast pass:** a stat walk of Claude Code’s projects, reading each transcript’s first
  and last records, plus indexed reads of Codex’s `state_5.sqlite`. It gives every
  session’s count, size, times, project, and title.
- **Summary pass:** this runs in the background, newest sessions first.
  The home page shows how many sessions are summarized, and a view that needs a family
  shows the sessions that have it.
- **Incremental updates:** a startup or a change re-reads only sessions whose key
  changed. A growing live transcript is re-read from its last offset.
- **A new family**, or a new version of one, triggers one background pass for that
  family only.
- **Merging:** every aggregate is a merge of summaries under the ownership rule, so no
  page load reads a transcript.
- **Cold-start bounds:** Phase 2 measures the fast pass and the summary pass on whole
  history, and records the figures beside the constants that bound them.

**The built-in engine** is Python in the plugin, and it always works.

**`urollup`** ([repository](https://github.com/jlevy/urollup)) is a first-party Rust CLI
that already reconciles copied history and reads zstd.
It accelerates the usage family when it is installed:

- **Unit:** one engine produces a measure family for the whole catalog.
  Engines are never mixed within a family, and Health names the engine.
- **Detection:** at startup the plugin looks for `urollup` on `PATH`. If its version
  meets a floor, which is a value in code, the usage family comes from its incremental
  JSON output. If it is absent, too old, or fails, the built-in engine computes the
  family.
- **Incremental mode first:** whole history took 60 s, so Metabrowser does not call
  `urollup` until it has an incremental mode, which Phase 4 adds there first.
- **Equality:** the synthetic homes come with hand-computed expected usage, written from
  the fixture’s construction.
  Both engines must match those numbers, so neither engine is the other’s reference, and
  having `urollup` installed changes speed, never results.
- **CI:** CI installs a pinned `urollup` release with `uv tool install`. As a
  first-party package, it is outside the 14-day cool-off, so the equality test always
  runs. Phase 4 therefore follows `urollup`’s first published release.
- **Doctor:** `metab doctor` gains an optional-dependency report, which names
  `urollup`’s presence, version, and floor.
  It follows the
  [command-line dependencies plan](plan-2026-11-18-cli-dependencies-and-doctor.md),
  which covers required dependencies only.

Later, `urollup` can also produce the events family in the same shape, and its planned
mergeable summaries can add in a summary from another machine.
Each addition lands in `urollup` before Metabrowser relies on it.

### SDK Additions

Each addition lands in the commit that first uses it:

| Addition | First needed by |
| --- | --- |
| Registry-driven adapter detection, with the reserved built-in names removed | Phase 2, moving the adapters |
| An exported JSONL parse limit or bounded-read helper in `plugin_api` | Phase 2, the import-boundary test |
| A plugin cache directory and its lifecycle | Phase 2, the catalog |
| Route-backed plugin pages, as the object data model plan proposes | Phase 2, the home, list, and session pages |
| Read zstd through `ArtifactPath` | Phase 4, Codex rollout usage |

The live views poll data-hook routes with a cursor, so they need no change-subscription
API. A home is a route-backed page, not a folder kind, so the folder-kind gap the
research brief lists is not needed.

### Routes and Parity

| Route | Returns | Phase |
| --- | --- | --- |
| `catalog` | Homes, totals, size-histogram buckets, progress, freshness, and engines | 2 |
| `sessions` | Filtered, sorted session rows | 2 |
| `session` | One session’s summary, children, and declared provider sections | 2 |
| `records` | One session’s normalized events, by kind, tool, or locator | 2 |
| `live` | Running sessions, and events since a cursor | 2 |
| `timeline` | Sessions and turns in a time window | 3 |
| `usage` | Token tallies for a filter and a grouping | 4 |
| `stats` | Event tallies, tool rollups, and latency for a filter and a grouping | 5 |
| `errors` | Errors grouped by class, with locators | 5 |
| `changes` | One session’s file changes, with diffs | 6 |
| `config` | Configuration, with secrets masked | 6 |
| `health` | Sources, skips, drift, and engines | 6 |

- Every route gets a `metab --api` golden over the synthetic homes, a row in the
  [Parity Registry](../../architecture/arch-parity-registry.md), and an entry in
  [the views, models, and routes map](../../architecture/arch-views-models-routes.md),
  all in the phase that adds it.

- The timeline’s zoom-and-scroll state machine and the live tail’s follow-and-pause
  state machine run browserlessly against the production JavaScript, with golden
  sessions.

- Three behaviors are exempt as paint only:
  - The timeline’s geometry on canvas or SVG.
  - Chart painting.
  - The live tail’s scroll anchoring.

  Each needs a stated reason and a focused Chrome test in the registry.

## Implementation Plan

Every phase is usable on its own.
Phase 1 puts value in users’ hands at once, Phase 2 builds the basic views, and each
later phase adds one family of statistics to those views.
Each phase that changes what a user or plugin author sees carries a changelog fragment.

### Phase 1: Recognize Every Log

- [ ] Recognize current Claude Code transcripts by their record shapes, not only by an
  `assistant` record in the first 20 lines.
- [ ] Add a Codex rollout adapter for plain `.jsonl` rollouts.
- [ ] Give `agent-log` a `[[kind]]` rule for the `codex` adapter.
- [ ] Add a changelog fragment.

**Done when:** current Claude Code transcripts and plain Codex rollouts open with the
Log and Charts views.
These are fixes in core’s existing path.
Phase 2 carries them into the plugin unchanged.

### Phase 2: Basic Views

- [ ] Land the Phase 2 SDK additions.
- [ ] Create the `agents` plugin package and its import-boundary test.
- [ ] Move the four adapters and the `agent-log` views into the plugin.
- [ ] Define the shared model, the event kinds, and each provider’s mapping table, with
  their goldens.
- [ ] Add the kind color tokens and their design checks, and use them in the Log and
  Charts views.
- [ ] Build the catalog’s fast pass, and its summary pass for the session and drift
  families. Measure both on whole history.
- [ ] Build the agents home, the session list, the session page’s header and Log tab,
  and the live strip.
- [ ] Add the synthetic-home generator and the goldens for the Phase 2 routes.

**Done when:** opening a served home shows the following, all colored by event kind:

- every session, with its size and time;
- what is running now;
- any session’s log, for both agents, including compressed Codex rollouts through
  `thread_history`.

### Phase 3: Timeline and Live Events

- [ ] Measure timeline rendering in Chrome, and set the technique and its bounds from
  the measurement.
- [ ] Build the timeline, with nested children and the per-turn breakdown at close zoom.
- [ ] Build the live events tail.
- [ ] Add the `timeline` golden, the `live` cursor goldens, and the browserless
  state-machine sessions.

**Done when:** all history scrolls as a timeline, and new events from running sessions
appear in one tail.

### Phase 4: Usage and Tokens

- [ ] Add zstd reading, as the owner decides under [Open Questions](#open-questions).
  This is a prerequisite: rollouts are Codex’s only per-request token and rate-limit
  source, and most of them are compressed.
- [ ] Add the ownership index and the usage family.
- [ ] Build the Usage page and the home page’s usage panel, including Codex rate-limit
  headroom.
- [ ] In `urollup`, add the incremental mode and publish a release.
  Then, in Metabrowser, add `urollup` detection, the version floor, the
  optional-dependency doctor report, the CI install, and the equality test.
- [ ] Add the `usage` goldens.

**Done when:** tokens by model, project, origin, and day match the hand-computed numbers
with or without `urollup`, and are faster with it.

### Phase 5: Events, Tools, and Latency

- [ ] Add the events family: two-level tallies, tool rollups, latency histograms, and
  locators.
- [ ] Build the session page’s Stats tab, the Records and Tools page, and the Errors
  page.
- [ ] Add the tool-family color tokens to the palette check.
- [ ] Add the `stats` and `errors` goldens.

**Done when:** every event kind and tool has counts, errors, and latency percentiles,
for one session or any group, each linked to its slowest instances.

### Phase 6: Agent-Specific Depth and Trust

- [ ] Add the Children and Changes tabs.
- [ ] Add the provider sections listed under
  [Agent-Specific Sections](#agent-specific-sections).
- [ ] Build the Configuration page with secret masking.
- [ ] Build the Health page and the drift report.
- [ ] Add the `changes`, `config`, and `health` goldens.

**Done when:** every family the research brief lists that answers an operator question
has a view, and Health accounts for every source.

## Testing Strategy

- **Synthetic homes:** a generator builds a `~/.claude` and a `~/.codex`, including
  SQLite databases, from pinned schemas.
  Real homes hold private data, so they are never fixtures.
  The homes cover:
  - every event kind and every observed raw type;
  - resumed and forked history;
  - a Codex thread with a second segment;
  - a subagent tree;
  - a live session, plus a stale pid file and orphaned `inProgress` turns that must not
    read as running;
  - unknown record types and unexpected SQLite columns.
- **Hand-computed expectations** for usage and tallies, written from the fixture’s
  construction.
- **Goldens:** a `metab --api` golden for every route, and a golden for each provider’s
  mapping table.
- **Engine equality:** both engines match the hand-computed usage.
- **Browserless state machines** for the timeline and the live tail.
- **Chrome measurements** set the timeline and tail bounds, recorded beside their
  constants.
- **Design checks:** contrast, and pairwise distinctness across the kind and tool-family
  palette.

## Open Questions

From the research brief, two of these now block a phase.
Each has a proposed default:

1. **Served root (blocks Phase 2):** the proposed default serves each home on its own,
   and shows the combined home when the served root holds both.
2. **zstd (blocks Phase 4):** wait for Python 3.14 as the floor, or vet a zstd package
   now?

The brief’s other questions also still stand: companion paths, packaging, and secret
masking. This plan adds:

3. **Cost:** show estimated cost from a price table, and if so, whose table?
   `urollup` plans one.
4. **`urollup` floor:** which release should be the minimum, and should `metab doctor`
   suggest installing it when it is absent?
5. **Default filters:** hide Codex automatic reviews and Claude Code subagents from the
   session list by default, and show them as children instead?
6. **Retention:** should the Health page suggest pruning old subagent transcripts, or
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
