- Serving a Claude Code or Codex home, `~/.claude`, `~/.codex`, or a folder holding
  them, now opens on an **Agents** page: every session’s count, size, and place in time,
  the sessions running now, a histogram of session sizes, the most recent sessions, and
  a progress line while a large history is summarized.
  A **Sessions** list beside it filters by agent, origin, status, project, model, and
  start, sorts by any column, pages, and hides automatic reviews until asked
  ([Browsing Agent History](docs/working-with-agents.md#browsing-agent-history)).
- A Claude Code transcript or a Codex rollout now opens on a **Session** view, a header
  with the session’s agent, status, origin, project, models, times, and its parent and
  children, above its events.
  Rollouts Codex has compressed with zstd, which did not open before, open on their own
  Session and Log views, read from Codex’s history store.
  A log that is in no agent home keeps showing the Log it had.
- Event kinds and tool families have one color each, in light and dark, wherever they
  appear: the Log’s badges, the Charts view’s series, and the Session view.
  A plugin that styled its own views with the agent log’s `--agent-log-kind-*` tokens
  now uses `--agent-kind-<kind>-*` and `--agent-tool-<family>-*`
  ([Color and Theming](docs/design-system.md#color-and-theming)).
- The `sessions` route of the `agents` plugin lists a `model` facet, and the `live`
  route names each running session’s source files.
