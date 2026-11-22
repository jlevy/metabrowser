- The built-in `agents` plugin keeps a catalog of the Claude Code and Codex sessions
  under a served folder that is, or holds, a `~/.claude` or `~/.codex` home, and answers
  five routes from it: `/api/plugin/agents/catalog`, `sessions`, `session`, `records`,
  and `live`. A background worker lists every session and then summarizes them, newest
  first, into a private cache directory, so a request returns what is ready with its
  progress and never waits for a full read of your history; `sync=1` waits for it, which
  is what `metab --api` and a script want
  ([Agent Catalog](docs/project/architecture/arch-views-models-routes.md#agent-catalog)).
