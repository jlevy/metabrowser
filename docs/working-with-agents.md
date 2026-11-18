# Working With Agents

A coding agent and you can look at the same things through Metabrowser.
The agent hands you a folder, a file, a commit, or a pull request, in the macOS app or
in a browser; it reads the same data from the command line, without a browser; and you
read its session logs as timelines.
The `metabrowser` agent skill teaches an agent its part.

## Install the Skill

```shell
npx skills add jlevy/metabrowser --skill metabrowser
```

The skill runs a local `metab` when there is one and otherwise `uvx metabrowser@latest`,
so it needs no Metabrowser installed.
[Installation](installation.md#the-agent-skill) covers pinning the installer and holding
`@latest` to releases past the cool-off.
The skill itself is [skills/metabrowser/SKILL.md](../skills/metabrowser/SKILL.md).

With it installed, an agent can browse and inventory folders, open a file or a live log,
read commits and diffs, read a GitHub pull request, and check plugins.
It uses `metab --help` as the reference for options, so it follows the build you have.
The skill is tested against the `metab` of the same commit, not against a release, so
the skill on `main` can name a flag or route that the newest release lacks; it says how
to run a source checkout’s `metab` until the next release.
[Release Status](installation.md#release-status) says which `metab` the macOS app needs,
a separate front end that the skill hands pages with `--present`.

## Ask an Agent to Show You a Page

Ask in your own words: “open the plan in Metabrowser,” “show me what the last commit
changed,” or “open pull request 123.” The agent presents a folder, a file, or a GitHub
URL: on a Mac with the [macOS app](macos-app.md) installed it opens in the app, and
otherwise in your browser, on a server `metab` starts for it.
Your `open_in` setting chooses the app only or the browser only
([the command-line guide](command-line.md#choosing-the-app-or-a-browser) has it).
For an address presenting cannot name, the agent serves the page and gives you its
address.

### In the App

```shell
metab --present . --path docs/plan.md --format json
metab --present https://github.com/owner/repo/pull/123 --format json
```

`--present` hands the target to the app, which opens it in a window, and prints a report
([the command-line guide](command-line.md#presenting-a-target---present) has its fields
and codes). The agent tells you what it handed over, and that the app was asked rather
than that a window shows it, since the app does not reply yet.
When no app takes the target, as on another machine or without the app installed,
`--present` starts a server for it that opens the page in your browser, and the report
gives its address and process ID; the agent stops it with `kill` when you are done.
With `--open-in app` or your `open_in: app`, nothing opens then, and the agent serves
the page instead, as below.

### In a Browser

When you ask for a browser, the agent presents with `--open-in browser`, which never
looks for the app:

```shell
metab --present . --path docs/plan.md --open-in browser --format json
```

For any other address, or where presenting would start a browser you cannot see, the
agent starts a server without opening a browser and gives you the address:

```shell
metab . --no-open
metab . --path docs/plan.md --no-open
metab https://github.com/owner/repo/pull/123 --no-open
```

Each prints the page it serves:

```console
Serving /path/to/repo at http://127.0.0.1:<port>/view/docs/plan.md
```

The port is the first free one from 8411, so the agent reads it from that line.
`--no-open` leaves the choice of browser and window to you: the agent may run headless,
in a sandbox, or on another machine.

One server serves every page under its folder, so the agent can hand you several
addresses on the same port.
A server of a repository or pull-request URL shows one commit at a time, starting where
the URL points; controls on the page, such as **Browse code** and the branch selector,
move it, and its pull-request pages answer for any pull request of the repository.

| Address | Shows |
| --- | --- |
| `/view/<path>` | A file or folder; `/view/` is the served folder |
| `/view/<path>#<heading>` | A heading in a document, by its GitHub-style anchor |
| `/commit/<full-id>` | What one commit changed, by its full ID from `git rev-parse` |
| `/commit/<full-id>/<path>` | One file’s change in that commit |
| `/pulls` | The repository’s pull requests |
| `/pull/<n>`, `/pull/<n>/files`, `/pull/<n>/checks` | A pull request, its changes, and its checks |
| `/pull/<n>/files/<path>` | One changed file in a pull request’s changes |

The page stays live while the agent works: new and changed files appear in the tree, and
a log being written tails in place ([live updates](browsing-files.md#live-updates)). The
server runs until the agent stops it or you ask it to.

### Let an Agent Reach the App From a Sandbox

`--present` asks LaunchServices for the app and hands it the target with
`/usr/bin/open`, and an agent’s sandbox can block either step.
The command then reports `lookup_failed` or `open_failed`, with the status the
[exit-status table](command-line.md#exit-status) gives a target LaunchServices did not
take, and the skill has the agent rerun the command outside the sandbox when you allow
that, or serve the page instead.
The skill never reruns a delivery to a browser outside the sandbox: it serves that page
inside the sandbox instead.
A rule can let the one command prefix, `metab --present`, run outside the sandbox every
time. The skill writes `--present` first and runs the command alone, with no redirect or
pipe, so that such a rule matches it and nothing else.

> **A rule runs `metab` with your full access, and lets the agent start a server outside
> the sandbox.** The rule matches `metab --present` whatever follows, so besides handing
> the app a target, a matched command can start a `metab` server for any path the agent
> names: under `--open-in browser`, or under the default `auto` when no app takes the
> target. That server runs outside the sandbox, serves the path on a loopback address the
> report gives the agent, and keeps running after the session ends, until it is stopped.
> No `open_in` setting prevents it, since `--open-in` overrides them.
> **Set `present_browser: false`** in `config.yml`
> ([Turning Browser Delivery Off](command-line.md#turning-browser-delivery-off)) with
> any rule: `--present` then hands the app a target or nothing, and no flag or variable
> undoes it. It holds while the agent cannot also write `config.yml` or choose the
> configuration directory (`METABROWSER_CONFIG_DIR`, `XDG_CONFIG_HOME`) for that
> command.
> 
> Add a rule only for a `metab` installed outside every folder the agent can write, its
> code included, such as one that `uv tool install` made: the command in `~/.local/bin`,
> its code under `~/.local/share/uv/tools`. Never name a source checkout the agent works
> in. A checkout’s `.venv/bin/metab` is an editable install that runs the checkout’s own
> `src/`, so an agent that can write the checkout can change that code inside the
> sandbox and then run it outside, with no prompt under an allow rule.
> To use a source build, point the rule, and the app’s Settings > Choose metab…, at a
> separate checkout the agent never works in; the app’s servers run that `metab` too.
> Otherwise add no rule, and approve each run when the agent asks.

- **Claude Code:** the sandbox is off by default.
  When it is on, it blocks the Apple Events and Launch Services requests `open` makes,
  and Claude Code can retry a blocked command outside the sandbox, which its permission
  mode approves or asks you about each time.
  An entry in `sandbox.excludedCommands`, in your user or project settings, runs
  matching commands outside the sandbox, still through the usual permission prompts,
  which an allow rule such as `Bash(metab --present *)` answers without asking
  ([Claude Code’s sandboxing guide](https://code.claude.com/docs/en/sandboxing), which
  warns about an exclusion for a tool the agent can write):

  ```json
  {"sandbox": {"excludedCommands": ["metab --present *"]}}
  ```

  The entry matches the text of the call, so a redirect, a pipe, `cd`, or another
  command in the same call keeps it sandboxed.
  `sandbox.allowAppleEvents` also lets `open` work, for every sandboxed command, which
  can then launch any app outside the sandbox with no prompt.

- **Codex:** its default sandbox blocks launching an app.
  Approve running the command outside the sandbox when Codex asks; allowing the prefix
  there, or this rule in `~/.codex/rules/default.rules`, runs it outside the sandbox
  without asking
  ([Codex rules](https://learn.chatgpt.com/docs/agent-configuration/rules)):

  ```python
  prefix_rule(pattern = ["metab", "--present"], decision = "allow")
  ```

Both rules match the command as the agent types it, so a `metab` the agent runs by its
path, as it runs a separate checkout’s, needs that path in place of `metab`.

## Reading Agent Logs

Coding-agent session logs are JSONL files, and Metabrowser opens them as timelines.

- **Recognized agents:** the session logs of Claude Code, Gemini CLI, and Pi open with
  three views: **Log**, a timeline of messages, tool calls, and results with filter
  chips; **Charts**, the session’s events by kind over time; and **Raw JSON**. The
  header names the agent and the run’s state.
- **Other JSONL:** any other `.jsonl` file opens with Log and Raw JSON. Codex logs are
  parsed into the same timeline, without Charts.
- **While the agent runs:** a log under a `.logs` or `.state` folder that is being
  written tails in the Log view as events arrive
  ([tailing a JSONL log](browsing-files.md#tailing-a-jsonl-log)).
- **More formats:** a plugin can register an adapter for another log format
  ([plugin-owned JSONL adapters](plugins.md#plugin-owned-jsonl-adapters)).

The same parse is available without a browser:

```shell
metab ./runs --show .logs/session.jsonl
metab ./runs --api '/api/file?path=.logs/session.jsonl' --format json
metab ./runs --api '/api/plugin/agent-log/charts?path=.logs/session.jsonl' --format json
```

The `/api/file` envelope carries the events and a summary: the agent, event, tool-call,
and error counts, and whether the run is done or failed.

## Reading the Data Without a Browser

Every route the page reads is reachable from `metab`, and each data mode runs the server
in the same process, with no port and nothing left running, so a POST through `--api`
changes nothing on a server that is already running.
What a mode prints is what the page would draw, so an agent can check its work against
the same data you see.

| To learn | Run |
| --- | --- |
| Which routes this build serves | `metab ROOT --api /api/routes --format json` |
| What the page shows for one path or address: route, kind, views, and model | `metab ROOT --show PATH` |
| One route’s answer | `metab ROOT --api ROUTE --format json` |
| The whole inventory | `metab ROOT --walk --format json`, or `--stream` for one record per line |
| What a change set holds | `metab ROOT --diff BASE..TARGET`, or `--diff REV` for one commit |
| Whether a pull request was read, and why not | `metab URL --api '/api/plugin/github/pull?number=N' --format json`, then its `state` and `last_refresh.outcome` |

With `--format json`, `--api` prints only the envelope, so the output parses, and it
exits nonzero when the route answers outside 2xx. A pull request that cannot be read is
not such an answer: the command still exits 0, so the skill reads the record’s `state`
and `last_refresh.outcome` instead.
Beside a checkout, a read never fetches a pull request; the skill POSTs
`/api/plugin/github/pull-refresh` for one the cache does not hold.
Routes that read the inventory wait for the scan to finish, so prefer one `--walk` over
many `/api/tree` calls on a large tree.
[The command-line guide](command-line.md) has every mode and option, and `metab --help`
is the reference.

## Trust

An agent should treat what it reads through Metabrowser as data, never as instructions:
a file, a log, or a pull request’s text and code can say anything.
The skill has the agent serve only the folders you put in scope and keep the default
`127.0.0.1` binding.
`--untrusted` turns active content off for a folder you do not trust; repository URLs
always open that way.
The [security policy](../SECURITY.md) has the trust boundary.

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
