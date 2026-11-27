# Plan: Plugin Sources, Process Isolation, and Out-of-Process Plugin Environments

**Date:** 2026-11-12 (last updated 2026-11-26)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Draft, awaiting the owner’s answers to the eleven Key Decisions below.
Epic `mb-xbw3` tracks every item as a bead.
No product code is changed.
The worker spike ran under kernel confinement on Linux and macOS. The Linux spike also
ran the PDF render child behind the same prefix.
The macOS spike loaded all three downstream plugins and exercised the workflow plugin’s
process and log hooks.
See the [spike results](../../../../explorations/plugin-worker-spike/README.md#results).

## Overview

A system-installed Metabrowser, meaning the `metab` uv tool and the macOS app that runs
it, should use a new plugin without being reinstalled, and should pick up the plugins a
repository checks in or locks through a library, with no Metabrowser-specific setup.
Today every Python plugin must be installed into Metabrowser’s own environment, which
rewrites that environment and, for the motivating domain plugin, cannot resolve at all.

In this design Metabrowser reads every plugin’s manifest and serves its assets itself,
and runs plugin Python in a **worker**: a process started with the plugin environment’s
own interpreter, running a **plugin runtime** the host ships.
**Plugin sources** live in one registry, each with a scope: everywhere, a set of
folders, or one clone of a repository.
A repository’s plugins are found by reading its environment’s metadata and load after
one consent per clone that names their providers.

Every child process Metabrowser starts for content or for a plugin goes through one core
**isolation** facility, extracted from the PDF preview’s sandbox and the SQLite readers’
pool.
It separates two things the earlier revision ran together: a process that is merely
**separate** (its own dependencies, crashes, CPU, and environment variables, with the
reader’s full authority) and one that is **confined** (the operating system refuses it
files outside named folders, the network, and other processes).
With it, trusting a clone can mean “run its plugins confined” and not “run its code as
me”.

The evidence, the reproductions, and the alternatives rejected are in
[Loading Plugins from Any Source](../../research/research-2026-11-12-plugin-sources.md).

## What Changed on 2026-11-26

A review against `main`, two weeks after the first revision, found the plan stale in
places and its trust model open in three.
This revision:

- **Adds the isolation layer** ([Isolation](#isolation)) and Key Decision 11, which
  replaces the earlier non-goal “no sandboxing” with confinement by default for a
  repository’s plugins.
- **Fixes what a trust decision binds to.** A clone is identified by a random token
  written under its Git directory, since a device and inode are reused on Linux
  (reproduced); a folder counts as a clone’s worktree only when the clone says so (a
  forged link is reproduced); and a decision binds the environment and each provider’s
  install origin (Key Decisions 2 and 3).
- **States the agent threat** the earlier revision missed: a sandboxed agent that edits
  an approved plugin’s code in a trusted clone (Key Decisions 5 and 11).
- **Drops the second executable.** `metab --present` already refuses every option
  outside its own set, and the documented sandbox exemption is that prefix (Key Decision
  5).
- **Changes the runtime’s import name** to one of its own, shipped as a package
  Metabrowser depends on (Key Decision 1).
- **Makes deadlines fail a call, not a worker,** adds a build stamp between host and
  worker, and corrects the lifeline ([Process Model](#process-model)).
- **Re-baselines on `main`:** the state home, Settings > Plugins, the app’s contract
  file, the SDK at 0.8, built-in adapters in the `agents` plugin, changelog fragments,
  and three Python extension points the first revision never mentioned.
- **Reorders the work** so the registry reaches the app before the adapter rework, and
  moves managed packages out of this plan ([Implementation Plan](#implementation-plan)).

A second review the same day, of the isolation layer, the threats, and the protocol, was
folded in as well:

- **The Linux filter had a hole.** A filter on `socket` alone left `io_uring` open,
  which reached a Unix socket outside every grant; the filter now refuses it, and the
  matrix says what is and is not run
  ([The Enforcement Matrix](#the-enforcement-matrix)).
- **Needs are grants.** The network and further writes are granted under confinement,
  one declared need at a time; `full` is for a plugin that cannot be confined; and where
  the machine cannot confine, a repository’s plugin Python does not load (Key Decision
  11).
- **A watchdog leads each worker’s group,** since a lifeline inside a worker cannot
  promise its end, and a worker is started with `subprocess` and told its pipes’ numbers
  ([Process Model](#process-model)).
- **No interpreter of an undecided source starts, in any mode,** because an
  environment’s `.pth` files run as it starts; and plugin directories are found from
  metadata, without importing ([The Registry](#the-registry)).
- **The facility splits containment from supervision,** records what is enforced so
  every surface prints the same thing, and never downgrades silently
  ([The Facility](#the-facility)).

## Key Decisions

Every decision below is awaiting the owner.
The design in this plan follows each recommendation, so choosing another option changes
the sections named in that decision; the options not chosen stay here with their pros
and cons.

### At a Glance

| # | Decision | Recommendation | Needed before | Hard to reverse? |
| --- | --- | --- | --- | --- |
| 1 | Who supplies the plugin-side runtime | Metabrowser injects it, under an import name of its own | Phase 1 | Yes: every plugin’s imports name it |
| 2 | What a trust decision binds to | The clone, by a token it holds, with its environment and named providers | Phase 4 | No: stricter levels can be added; weakening a released one is a security change |
| 3 | Where plugin code comes from when the browsed folder is elsewhere | Worktrees the clone lists use its environment; sources can name further folders; checked-in plugins without an environment run on an isolated interpreter | Phase 4 | No |
| 4 | Whether Metabrowser sets up a repository’s environment | Report only; a declared command later | Phase 4 | No |
| 5 | Which commands an agent may run outside its sandbox | One executable; `--present` refuses every plugin option by construction; no `--yes` on trust writes | Phase 1 | Somewhat: flag names are read by scripts |
| 6 | The order of the work | Unblock and extract isolation first, then one vertical slice, then the registry | now | No |
| 7 | Where sources and trust decisions live | The state home, read fail-closed | Phase 2 | Yes: moving a released record needs a migration |
| 8 | How many plugin API versions | One, under Cargo’s caret rule, plus a build stamp that is not a version | Phase 0 | Somewhat: splitting later adds a field to every manifest |
| 9 | How widely a worker is shared | One per server, environment, and grant set, subject to provider isolation | Phase 1 | No: a shared worker can sit behind the same client |
| 10 | How log adapters are detected | Declarative predicates in the manifest, proved on the built-in adapters first | Phase 3 | Somewhat: manifests carry the predicates |
| 11 | What a trusted plugin’s Python may do | Confined, with declared needs as grants; where the machine cannot confine, it does not load | Phase 4 | No to tighten; a released grant of full access is hard to take back |

Decisions 6, 8, 1, 5, and 9 are needed before Phase 1’s code; the rest can wait for the
phase named.

### 1. Who Supplies the Plugin-Side Runtime

**The question.** Plugin Python running in its own environment calls a small library
(contained paths, bounded reads, log events) and needs a loop that talks to the host.
Where does that code come from, and what is it called?

**How to think about it.** That code enforces security bounds and is the plugin
contract. What matters is who can fix it, how many versions of it run at once, what a
plugin author has to install, and whether one copy can serve the server, a worker, and
an author’s type checker.
The surface is not small: `metabrowser.plugin_api.__all__` exports 94 names on `main`,
55 of them the table-source API.

**Options.**

- **A. Each plugin environment installs an SDK package and runs its own copy.**
  - Pros: a plugin runs against exactly the SDK it was tested with.
  - Cons: a fix to path or decompression bounds reaches a plugin only when its
    environment relocks; two plugins in one environment must agree on one SDK range; a
    checked-in directory plugin has nothing that installs it; host and worker need a
    negotiated protocol.
- **B. Metabrowser injects its own copy, under an import name of its own.** The runtime
  is a standard-library-only package, `metabrowser_sdk`, published as its own
  distribution that Metabrowser depends on at one exact version.
  The host puts its copy first on a worker’s path.
  - Pros: one implementation serves the server, built-in plugins, workers, and authors’
    type checks and tests; the host’s copy wins in a worker, so a fix reaches every
    plugin with the next Metabrowser; an environment may also install it, for type
    checks, without clashing with anything; `import metabrowser` keeps one meaning.
  - Cons: the three downstream plugins change their imports once; a second distribution
    to version and publish in order; plugin code runs against a newer runtime than it
    was tested with, held by the plugin API gate.
- **C. Metabrowser injects its copy as `metabrowser`.**
  - Pros: nothing to install, and code that imports the documented names runs unchanged,
    as the second spike ran three plugins from an environment holding Metabrowser 0.9.1.
  - Cons: inside a worker `metabrowser` is not the installed package, so anything that
    imports beyond the documented names fails there; a published copy for type checks
    would install a top-level `metabrowser` and cannot share an environment with the
    real one; the same files must import as `metabrowser.x` in a worker and as part of
    the real package in the server.

**Recommendation: B.** The benefit of C was that plugin code runs unchanged, and that
does not survive Phase 3: all three plugins are edited there anyway, to declare their
adapters, drop their Metabrowser pins, and move from SDK 0.5 to the current one.
B is what the repository’s own rule asks for (plugins are upgraded, not accommodated),
and it is the only option where the published copy and the injected copy are the same
package. Choose C if editing the three plugins’ imports is worth avoiding at the cost of
a name that means two things.

**Affects:** The Plugin Runtime, Phase 1, Phase 3’s author harness.

### 2. What a Trust Decision Binds To

**The question.** When the user trusts a repository’s plugins, what exactly is approved,
and what makes Metabrowser ask again?

**How to think about it.** Trust means “code from this place may run”.
The code changes through a pull, a branch from a fork, a new dependency that brings a
plugin, an agent’s edit, or a different repository cloned to the same path.
Each binding asks again on some of those and not others.
Asking too often teaches people to click through; asking too rarely lets new code run
unseen. And a check is only as good as its input: anything a hostile directory can write
about itself is not evidence, which rules out its origin URL, its `.git` file, and any
identity the file system can hand to a different directory later.

**Options.**

- **A. The path,** as VS Code Workspace Trust and `mise trust` do.
  - Pros: the simplest rule; it never interrupts.
  - Cons: anything that can write the tree, add a dependency, or put another repository
    at that path runs code without a prompt.
- **B. The clone, with its environment and named plugin providers.** The clone is
  identified by a random token Metabrowser writes under its Git common directory when it
  is trusted. The decision records the environment’s prefix and, for each approved
  provider, its name and where it was installed from.
  - Pros: asks once per clone, and again when a new provider appears, when a provider’s
    install origin changes (an index package that becomes a Git URL), or when the
    environment moves; a reclone at the same path has no token and asks again; a version
    bump of an approved provider does not ask.
  - Cons: an edit to approved plugin code runs without asking, which Key Decision 11
    answers by limiting what that code can do; Metabrowser writes one small file under
    `.git`; a copy of the whole clone carries the token.
- **C. The content of the plugin set,** as `direnv allow` and mise’s paranoid mode do.
  - Pros: nothing that changed runs unseen.
  - Cons: the example workspace has 10 editable members, so nearly every pull asks, with
    a diff nobody reviews, and prompts people click through protect no one.
- **D. A parent folder, scoped by origin URL.**
  - Pros: the fewest prompts; one decision covers every clone of an organization.
  - Cons: not a boundary.
    Two hand-written files under `.git` make Git report any origin (reproduced), so an
    extracted archive or an agent-made folder under the parent runs code without a
    prompt.

The first revision identified a clone by the device and inode of its Git common
directory. That fails: on ext4, deleting a clone and cloning a different repository at
the same path gave the same device and inode in 5 of 5 rounds (`probes.py identity`),
which `src/metabrowser/home.py` already says of inode numbers.

**Recommendation: B, with three states:** undecided, trusted for the named providers,
and denied. Defer C as an opt-in for repositories that take outside contributions.
Add D only if described as what it is: everything placed under the folder runs code.

**Affects:** Repository Plugins (Decisions), The Registry, the app’s repository bar,
Phase 4.

### 3. Where Plugin Code Comes From When the Browsed Folder Is Elsewhere

**The question.** The folder being browsed is not always where the plugins are
installed. Which environment runs the code?

**How to think about it.** In the owner’s daily use, one checkout holds the environment;
agents work in linked worktrees; runs and data live outside the repository; and some
repositories have no Python environment at all.
What runs should follow where code is installed and trusted, not only what is on screen.
And the link from a folder to its clone must be read from the clone’s side: one
hand-written `.git` file makes Git report any clone’s common directory for any folder
(reproduced).

**Options.**

- **A. Only the browsed repository’s own environment.**
  - Pros: the simplest rule; what you browse is what runs.
  - Cons: every linked worktree needs its own consent and its own environment; data
    outside the repository gets no plugins; a checked-in plugin in a repository without
    an environment has no Python.
- **B. A linked worktree uses its clone’s decision and primary environment.** A folder
  is a clone’s worktree only when the clone’s `worktrees/*/gitdir` names it.
  Checked-in plugin directories and the repository’s plugin settings are read from the
  primary worktree only.
  - Pros: a new worktree works at once, with no sync; code an agent edits in a worktree
    does not run until someone opts in; a folder cannot claim a clone that does not list
    it.
  - Cons: a worktree whose branch changes a plugin shows the primary checkout’s version
    until its author opts in for one command; a bare repository with worktrees has no
    primary, so the user names which worktree holds the environment.
- **C. A source’s scope can name further folders.**
  - Pros: run folders and data outside the repository get its plugins; one registry
    covers every kind of source.
  - Cons: one more field per source, and the user adds each folder once.
- **D. Checked-in plugins with no environment run on an isolated interpreter.**
  - Pros: Python hooks work in a repository with no Python project, and the dependency
    isolation is real: `python -I -S` sees only the standard library (reproduced twice).
  - Cons: those hooks can use only the standard library and the runtime.

**Recommendation: B, C, and D together,** with repository discovery proposing a source
in the one registry rather than being a second mechanism.

**Affects:** Sources and Scopes, Repository Plugins (Discovery, Checked-In Plugin
Directories), Phase 4.

### 4. Whether Metabrowser Sets Up a Repository’s Environment

**The question.** When a clone’s environment is missing or incomplete, does Metabrowser
build it?

**How to think about it.** A missing environment is the commonest reason a discovered
plugin cannot load after a fresh clone.
Building one downloads packages, runs the repository’s build backends, which is code,
and writes into the developer’s checkout; doing it wrong can remove packages the
developer installed.

**Options.**

- **A. Guess a command, such as `uv sync --locked`.**
  - Pros: one click.
  - Cons: wrong for the example repository, which initializes its submodules first and
    then runs `uv sync --all-packages --locked`; the default sync also removes packages
    it did not install; it runs build code from a click.
- **B. Run a command the repository declares,** such as `make install`.
  - Pros: correct for each repository; one click for a teammate.
  - Cons: the consent must cover that command, since it runs arbitrary repository code
    with full access; one more setting for repositories to keep current.
- **C. Metabrowser builds its own environment from the lock, in its cache.**
  - Pros: never touches the developer’s `.venv`.
  - Cons: doubles disk use and downloads for every repository, still runs the build
    backends, and drifts from the environment developers actually use.
- **D. Report only.**
  - Pros: never wrong, and never writes to the checkout.
  - Cons: one manual step after a fresh clone.

**Recommendation: D now, B later.** Whatever is chosen, use the repository’s whole
environment, never a reduced one: the motivating plugin loads the consuming repository’s
own extensions, so a reduced environment renders its processes wrongly.

**Affects:** Repository Plugins (The Clone’s Environment), the app’s repository bar.

### 5. Which Commands an Agent May Run Outside Its Sandbox

**The question.** How does `metab` stay safe to exempt from an agent’s sandbox now that
some modes run plugin code or record trust?

**How to think about it.** The exemption Metabrowser documents is a prefix:
`metab --present *` in Claude Code’s `excludedCommands`, and the matching Codex rule
([Working with Agents](../../../working-with-agents.md)). The skill writes `--present`
first so that the rule matches that mode and nothing else, and `--present` accepts only
its own five options: `metab --present . --plugins-dir X` is refused today (reproduced).
The first revision assumed an exemption of `metab *`, which only an older research note
mentions and which `--remote … --ssh-options` already makes unsafe.

Two questions remain.
The first is whether a new flag could reach plugin code through `--present`. The second
is larger and no command line answers it: a sandboxed agent working in a trusted clone’s
primary checkout can edit an approved plugin’s code, and a server the user already has
open, or one that `--present` starts, then runs it.
No check can tell a person from an unsandboxed process running as the same account.

**Options.**

- **A. Rely on the skill’s wording.**
  - Pros: no code.
  - Cons: nothing holds the property when a flag is added.
- **B. A separate executable, `metab-plugins`, for every mode that runs plugin code
  without a recorded decision, or records one.**
  - Pros: the boundary is visible in the command’s name.
  - Cons: it protects an exemption nobody is told to write; the app must find, verify,
    and declare a second executable in its contract; scripts call two names; and it does
    nothing about code an agent edits in a trusted clone.
- **C. One executable, with the property held by construction.** Plugin-source options
  and trust modes are never in `--present`’s option set, and a test fails if one is
  added.
  - Pros: no new command; the property is checked where the options are defined.
  - Cons: a user who exempts `metab *` against the documentation exempts these modes
    too, as they already exempt `--remote`.
- **D. Trust writes need a person:** a terminal answer, or the app’s confirmation bound
  to the plugin set it showed (`--expect SHA256`), and no `--yes`.
  - Pros: no one-flag self-approval; what was shown is what is approved.
  - Cons: scripts cannot record trust; `--expect` binds what was approved, not who
    approved it, so an unsandboxed agent with a terminal can still answer.

**Recommendation: C and D together.** Answer the larger question with Key Decision 11: a
repository’s plugins run confined, so editing one gains an agent little it did not have,
and the consent and the agents guide say what remains.
Fix `--ssh-options` separately.

**Affects:** CLI and Routes, Trust and Consent, the agents guide, Phase 1.

### 6. The Order of the Work

**The question.** What ships first, and when does the in-process path for third-party
plugins go?

**How to think about it.** The consumers are blocked today.
Building the whole mechanism first lands a coherent system; building a vertical slice
first tests the riskiest pieces (the worker binding, calls back to the host in the
middle of a hook, deadlines) against a real plugin early.
The requirement names the app, and the app passes no flags, so nothing reaches it until
a registry exists.

**Options.**

- **A. Mechanism, then repository trust, then migration.**
  - Pros: the full system lands in one coherent order.
  - Cons: nothing reaches the consumers for three phases, and the risky pieces meet a
    real plugin last.
- **B. Unblock first, then one vertical slice, then adapters, then the registry.** The
  first revision’s order.
  - Pros: dependency ranges help now; the real plugin runs from its own environment
    early.
  - Cons: the app waits behind the adapter rework for a registry it could have had.
- **C. Unblock and extract isolation first, then one vertical slice, then the registry,
  then adapters and the remaining extension points, then repository plugins.**
  - Pros: as B, and the app uses a registered environment as soon as hooks work; the
    isolation facility exists before the first worker is written on it, and the PDF
    preview and SQLite readers prove it first.
  - Cons: one more phase boundary.

**Recommendation: C.** Remove the in-process path for third-party plugins only after the
three plugins have run in workers for a release, and not on Windows until a Windows
worker exists.

**Affects:** Implementation Plan, Rollout Plan.

### 7. Where Sources and Trust Decisions Live

**The question.** Which home holds the registry of sources and the trust decisions, and
how is it read?

**How to think about it.** These records name local paths and authorize code on one
machine. `main` gives both precedents: the recent-targets list, which also names local
paths, lives in the configuration home, and the event log lives in the state home
(`state_directory` in `src/metabrowser/home.py`), which the app already passes to its
servers. What separates them is the cost of a copy: a trust grant synced to another
machine with someone’s dotfiles authorizes whatever is at that path there.
Because the record authorizes code, how an older `metab` reads a newer record matters as
much as where it is.

**Options.**

- **A. The configuration home, beside `config.yml`.**
  - Pros: one place for users to look.
  - Cons: a dotfile sync carries a trust grant to another machine, where the same path
    can hold other code.
- **B. The state home, which exists.**
  - Pros: grants stay on the machine that made them; no new home to resolve, protect, or
    pass from the app.
  - Cons: people clear state to reclaim space, which forgets their sources and asks
    again; a Terminal that sets `XDG_STATE_HOME` and an app launched without it read
    different registries.
- **C. A file in each repository.**
  - Pros: no central record.
  - Cons: served content could write its own trust.
    Not viable.

**Recommendation: B, read fail-closed.** An entry holding a field this `metab` does not
know is not used, and `--doctor` says so, since a newer release may have added the field
to narrow the grant.
`metab --doctor` reports when the state home in a Terminal differs from the one the
app’s servers get, as it already does for the cache and configuration homes.

**Affects:** The Registry, the app’s doctor checks, Phase 2.

### 8. How Many Plugin API Versions

**The question.** What does a manifest’s `sdk_version` cover, and how many version
numbers does a plugin author track?

**How to think about it.** Every version is a gate authors read and the host must keep
honest. Today the number covers the browser SDK only; a break bumps it and refuses every
plugin, and an addition does not change it, so a plugin that needs an addition has no
way to say so and an older host fails inside the plugin instead of at the gate.
The host ships the worker’s code, but not as one indivisible thing: a worker is started
from files on disk each time, so a server that stayed up through an upgrade can start a
worker from the next release’s files.

**Options.**

- **A. One version for the browser SDK and the runtime, under Cargo’s caret rule:**
  additions bump the patch number, breaks bump the minor, and today’s `0.8` reads as
  `0.8.0`.
  - Pros: one number for authors; a plugin can declare the addition it needs and an
    older host refuses it by name; a host accepts every older patch of its own minor.
  - Cons: a Python-only change bumps the number that browser-only plugins declare; every
    addition now needs a patch bump and an entry in the change list.
- **B. Separate browser and runtime versions.**
  - Pros: finer refusals.
  - Cons: two numbers in every manifest, and two change lists.
- **C. Either, plus a negotiated worker protocol version.**
  - Pros: would allow host and worker to ship separately.
  - Cons: they do not ship separately, and a negotiation is a compatibility layer with
    no consumer.

**Recommendation: A, with a build stamp.** The host sends its build in the worker’s
first frame, and a worker started from another build’s files refuses with a message that
says to restart the server.
That is an equality check, not a version to negotiate.

**Affects:** Plugin API Compatibility, Process Model, Phase 0.

### 9. How Widely a Worker Is Shared

**The question.** Does each server start its own worker per plugin environment, or do
servers share one, or does each plugin get its own?

**How to think about it.** This trades memory against shared fate.
A worker measured 61 MB after listing three plugins and 113–121 MB after the large hook,
and the app keeps several folders open, each with its own server.
Plugins that share a worker share its event loop, its memory, and whatever ends it.

**Options.**

- **A. One worker per server, environment, and grant set, started on demand, exiting
  when idle.** Plugins of one environment share a worker when they were granted the same
  things.
  - Pros: a worker serves one root, so plugin caches and root callbacks keep their
    meaning; its lifetime is tied to its server; no new supervisor.
  - Cons: several open folders on one environment cost one worker each; plugins that
    share a worker share a fate, so ending one must be rare.
    A plugin with a need of its own costs a worker of its own.
    Separate workers give providers different authority only if startup and imports
    respect the provider boundary.

- **B. One worker per environment, shared by every server.**
  - Pros: one worker’s memory per environment, however many folders are open.
  - Cons: needs a supervisor outside any server, a root on every call, and cache
    isolation between roots inside plugin code, which plugins do not do today.

- **C. One worker per server and plugin.**
  - Pros: one plugin’s stuck hook cannot touch another’s.
  - Cons: three plugins in one environment cost three workers’ memory and three imports
    of what they share.

- **D. In process.**
  - Pros: no extra process.
  - Cons: the dependency conflicts, GIL contention, and shared crashes this design
    exists to remove.

- **E. Grant authority to the environment as a whole.** The owner approves the
  environment’s effective grants.
  Providers that need different authority use separate environments.
  - Pros: consent covers startup code and imports from the environment.
  - Cons: providers in one environment share its grants.
    Separating them adds setup and maintenance.

**Recommendation: A if Phase 1 demonstrates provider isolation.** Ordinary startup in a
shared environment can execute its `.pth` files and load its packages under each
worker’s grants. Until the acceptance test passes, per-provider grants are a proposal.
If the boundary cannot be demonstrated, return to the owner with E. Keep the call
deadlines in the Process Model and revisit B if open folders use too much memory.

**Affects:** Process Model, the app’s open folders.

### 10. How Log Adapters Are Detected

**The question.** When a JSONL file opens, how does Metabrowser decide which plugin’s
log adapter owns it?

**How to think about it.** Detection runs on every JSONL open and decides the file’s
kind before anything renders, so it must be fast and should not start a process.
On `main` core registers no adapter: the built-in `agents` plugin registers five through
the same `register_log_adapter` a third-party plugin uses, and their detectors test a
value’s type, look inside a nested object, and in one case read a line that is not JSON.
A predicate language that cannot say those things leaves two detection mechanisms in the
host for good.

**Options.**

- **A. Declarative predicates in the manifest,** evaluated by the host, in a language
  that can express the five built-in detectors, which move to it first.
  - Pros: classification never waits on a worker; one mechanism for built-in and
    third-party adapters; a plugin states its detection once.
  - Cons: a predicate language to specify, version, and test, larger than the first
    revision’s six operators; porting the built-in detectors is work with no visible
    change.
- **B. Code detectors, run in the worker.**
  - Pros: any logic.
  - Cons: the first JSONL open starts a worker, 0.3–0.9 s to listed across both spikes,
    and each new file pays a round trip.
- **C. Declarative for third-party plugins, code for built-ins.**
  - Pros: the smallest language.
  - Cons: two mechanisms and two orders to reason about; a worker plugin declares a
    predicate and still passes a code detector to `register_log_adapter`, so its
    detection has two sources of truth.

**Recommendation: A.** If porting the built-in detectors shows the language growing past
what a manifest should hold, fall back to C and say that the two mechanisms are
permanent.

**Affects:** Log Adapters, Phase 3.

### 11. What a Trusted Plugin’s Python May Do

**The question.** When a clone’s plugins are trusted, does their Python run with the
reader’s full authority, or confined to what a plugin needs, and what happens where the
machine cannot confine?

**How to think about it.** The first revision listed sandboxing as a non-goal: a worker
“runs with the user’s privileges, like any program the user installs”.
Three things have changed.
`main` now confines a child process on macOS, for PDF previews of untrusted sources, and
its threat model states the rule: where confinement is required and absent, the work is
refused. Spikes confined the plan’s worker on Linux with Landlock and seccomp, with the
plugin still listing, serving hooks, and calling back to the host, and ran the
repository’s own PDF child behind the same prefix ([Isolation](#isolation)). And without
confinement a per-clone consent that does not bind content hands the reader’s whole
account to anything that can edit an approved plugin or add a `.pth` file to its
environment, a sandboxed agent included (Key Decision 5).

Confinement is not free and not complete.
It needs a platform with a working backend, the plugin’s JavaScript runs in the page
with the page’s authority either way, and a filter is only as good as the doors it
knows: the second revision’s Linux filter left `io_uring` open, which reached a Unix
socket outside every grant until it was closed.
What a data hook does today is read files under the served root and compute, which is
what the default grant allows, and what it lacks (the network, a further folder, a tool)
can be granted one need at a time without giving up the rest.

**Options.**

- **A. Full access.** A worker is separate, not confined, as the first revision had it.
  - Pros: nothing a plugin does today can break; no platform differences.
  - Cons: trusting a clone means “run its code as me”, and so does every later edit to
    that code and every dependency it locks; the consent cannot honestly say less.
- **B. Confined, with declared needs as grants; where no backend works, the Python does
  not load.** A repository’s worker requires confinement.
  The default grant is to read the clone, its environment, and the served folders, and
  to write a cache. A manifest’s `[plugin.needs]` asks for more (the network, a folder, a
  program), and each need is granted under confinement when the user approves it.
  Authority `full` is for a plugin that declares it cannot be confined, or for a user
  who chooses it deliberately with `--authority full`; the bar never offers it.
  Where the machine has no backend, a repository’s plugin Python is refused with
  `no_sandbox`, its manifests, assets, and JavaScript still load, and `--doctor` names
  the missing piece. Sources the user adds by hand prefer confinement and run without it
  where there is none, as an installed plugin does today.
  - Pros: the default consent is narrow enough to give without reading the code, and
    narrower than a typical agent sandbox, so an edit an agent can make runs with less
    authority than the agent has; a need that appears later is what asks again, which is
    a prompt about what code may do and not about what it is; a machine without a
    backend never teaches the reader to click through to full access; it is the rule PDF
    previews already follow.
  - Cons: the macOS results cover one downstream environment and the surveyed hooks.
    Additional plugins may need further grants.
    On a machine without a backend, repository hooks require a deliberate full-authority
    command. The Linux backend needs kernel 5.13.
- **C. As B, but offer `full` in the bar where no backend works.** The second revision’s
  choice.
  - Pros: a repository’s plugins work everywhere after one click.
  - Cons: on exactly the machines that cannot confine, the one-click path grants the
    whole account, and repeats until the click is a habit.
- **D. As B, but `network` or `write` forces `full`.** Also the second revision’s.
  - Pros: two authorities are simple to explain.
  - Cons: a plugin that only needs the network gets the whole account, although both
    platforms can grant outbound IP without opening the worker’s file grants (observed
    on Linux and macOS).
- **E. Full access, bound to content** (Key Decision 2, Option C).
  - Pros: nothing changed runs unseen.
  - Cons: prompts on nearly every pull, which nobody reads.

**Recommendation: B.** The macOS spike loaded all three downstream plugins and ran the
workflow hooks with the default grants.
The consent can name the environment, repository and served files it can read, and the
private scratch folder it can write.
The macOS app’s privacy attribution and the full app stop path still need an app test.

**Affects:** Isolation, Trust and Consent, Repository Plugins (Decisions), Phase 0 and
Phase 4.

## Goals

- Adding, removing, or updating a plugin never reinstalls Metabrowser.
- A plugin’s Python dependencies never conflict with Metabrowser’s or another plugin’s.
- A repository that checks in a plugin, or locks a library that ships one, works for a
  teammate after one consent per clone, its worktrees included, with no
  Metabrowser-specific configuration.
- That consent can be given without reading the plugin’s code, because what the code may
  do is bounded by the operating system and stated in the consent.
- Every child process Metabrowser starts is started one way, and what it is isolated
  from is written down once.
- The macOS app uses the sources that the `metab` it runs uses, and adds only native
  consent and settings.
- Served content runs code only in a clone the user has trusted, and a browser page
  never changes what runs.
- A host release refuses a plugin only when the plugin needs something the host lacks or
  uses something the host removed, and says which.
- Every source, persisted record, and check is a `metab` mode or route with a golden.
- Plugin authors test hooks, adapters, and assets against the real host from their own
  repositories and CI.

## Non-Goals

- Confining plugin JavaScript.
  It runs in the application page and can call every route that page can, whatever the
  worker’s authority; [Threats](#threats) says what that leaves.
- A sandbox that holds against a kernel or sandbox bug, or one for platforms with no
  backend. There, confinement is not offered rather than pretended.
- Plugins for Git sources opened from a URL, pins, or `--untrusted` sessions beyond the
  built-ins and the user’s sources scoped everywhere.
- A plugin marketplace, index, or signature scheme, and installing plugin packages:
  `uv tool install` or any environment the user makes is registered as a source.
  Managed packages (`mb-8ii8`) are no longer part of this plan.
- Streaming data hooks; none exists today.
- Windows. Workers rely on descriptor passing and process groups; the in-process path is
  not removed on Windows until a Windows worker exists.

## Background

[The research brief](../../research/research-2026-11-12-plugin-sources.md) reproduced,
on 2026-11-12:

- discovery imports entry points from the running interpreter only, once, at server
  import;
- `--plugins-dir` plugins lose every data hook and never register their log adapters, so
  adapter-classified kinds fall back to generic JSONL;
- `uv tool install metabrowser --with <plugin>` has no solution, because Metabrowser
  pins `softschema==0.8.1` and the plugin needs `>=0.9.1,<0.10`;
- an in-process overlay of the plugin environment silently binds the plugin to the wrong
  Softschema, and subinterpreters refuse `pydantic_core`.

The startup discovery and extension-point limits still motivate this plan.
`main` now pins a Softschema version in the motivating plugin’s range, so the specific
resolver conflict above is historical.
Testing a compatible range and co-installing across that range stay in Phase 0
(`mb-hi06`).

The downstream application repository is the pattern repository plugins must serve: a uv
workspace whose members include its own two plugin packages and the workflow library,
vendored as a Git submodule.
All three declare `metabrowser.plugins` entry points and load today only when that
workspace’s own `metab` runs from its environment, which is why the workspace locks an
exact Metabrowser.

Two spikes ran against that environment, which holds Metabrowser 0.9.1, from a 0.12.1
host.
The first measured the transport: 0.13–0.17 ms median for a trivial hook and 61–121
MB per worker. The second ran a runtime the host ships, injected ahead of the
environment’s own packages, on descriptors 3 and 4. All three plugins’ code served their
hooks, including two calls back to the host in the middle of one hook, and a handler
past its deadline was killed and replaced in 369–426 ms.

On 2026-11-26 a third round ran on Linux against `main`, with a stand-in plugin that
needs no network (`explorations/plugin-worker-spike/probes.py`; results beside it):

- **Transport by size,** with no polling inside the timing: 0.72 ms at 429,248 bytes,
  4.8 ms at 4 MiB, and 122 ms at 64 MiB, median.
  The first spike’s “10–27 ms on a 429 KB response” included a 20 ms polling sleep and
  is withdrawn.
- **The lifeline** ended a worker 1.8 ms after its request pipe closed while a
  synchronous hook ran, and not at all while an `async def` hook blocked the event loop:
  the worker ran until the hook returned, 7.5 s later.
- **A deadline kill** left another call in flight unanswered and left the hook’s
  subprocess running in the server’s process group.
- **A forked child** of a hook wrote to descriptor 4 and ended the host’s reader.
- **Confined** behind `confine_linux.py`, the same worker listed the plugin, served
  every hook, and made both host calls, while a hook was refused a file outside its
  grants, a write beside it, and a TCP connection; it started in 89 ms against 59 ms.
- **Identity:** the reclone and the forged worktree described under Key Decisions 2 and
  3\.

What `main` has gained since the first revision, and this plan now builds on:

| On `main` | Where | What it changes here |
| --- | --- | --- |
| A sandboxed child for PDF previews, and the rule for when it is required | `builtin_plugins/pdf/preview_isolation.py`, threat model T7 | The isolation facility is an extraction, not an invention |
| A pool of reader processes with deadlines, a kill grace, and a bounded queue | `sqlite_readers.py` | The worker client reuses its supervision |
| The state home | `home.py` (`state_directory`), `ChildEnvironment.swift` | Key Decision 7 adds no home |
| Settings > Plugins in the app, and the app’s declared contract | `PluginsPane.swift`, `apps/macos/metab-contract.toml` | Phase 4 extends a pane and a contract; no fallback for an older `metab` |
| Built-in log adapters registered by the `agents` plugin | `logutil/parsing.py`, `builtin_plugins/agents/adapters.py` | Key Decision 10; unknown names already get the generic parser |
| `[plugin] register`, `[[view]] offer`, and `[[table_source]]` | `plugin_loader/manifest.py` | Three Python extension points a worker must serve or refuse |
| `plugin_cache_directory` and the agent-chart cache | `plugin_api.py` | Host services the runtime must reach |
| `PLUGIN_SDK_VERSION = "0.8"` | `plugin_loader/manifest.py` | The caret rule starts from `0.8.0` |
| Changelog fragments | `changelog.d/` | Every “recorded in `CHANGELOG.md`” below means a fragment |
| The threat model | `arch-threat-model.md` | Repository plugins add threats there, in the same pull request |

The [native macOS app plan](plan-2026-11-10-native-macos-app.md) runs one `metab` server
per folder as a child, from a CLI install, with an allowlisted environment.
Its Phase 5 deferred project-provided plugins to a trust spec; Repository Plugins below
is that spec.

## Design

### Principles

- **Register a source; never install into Metabrowser.** Metabrowser’s environment holds
  Metabrowser. Plugins live in environments beside it.
- **The host owns manifests, assets, and the runtime; workers run plugin code.** The
  server reads every manifest with its own schema and serves static files from the
  plugin directory. A worker is needed only for Python, and its runtime is the host’s.
- **Third-party Python runs out of process.** Built-ins stay in the server.
  Every other Python plugin runs in a worker on its environment’s interpreter.
- **Separate is not confined.** A separate process isolates dependencies, crashes, and
  time. Only a confined one is denied anything, and each consent says which it grants.
- **A repository is browsed before it is trusted.** Discovery reads only metadata, and
  nothing from an undecided clone runs or reaches the page.
- **Nothing the folder says about itself is evidence.** A clone’s identity, a worktree’s
  membership, and where code is loaded from are read from what the user or the clone’s
  own Git directory holds, never from the folder being judged.
- **Nothing the page can reach changes what runs.** Plugin JavaScript shares the page’s
  origin with every other plugin, so no route writes a source or a decision.
- **One representation, every surface.** Sources, decisions, and checks are one model,
  served by `metab --plugins --json`, `metab --doctor --json`, and `GET /api/plugins`.

### Isolation

“Isolation” has meant five different things in this plan and in the code.
This section names them, says which a child process gets, and makes one core facility
provide them.

#### What Isolation Means

| Property | What it protects | How it is held | Is it a security boundary? |
| --- | --- | --- | --- |
| **Dependencies** | The server’s imports from a plugin’s, and one plugin environment’s from another’s | A fresh interpreter started with `-I`, on the environment’s own Python | No |
| **Faults** | The server from a crash, a leak, or a native fault | A separate process, replaced when it dies | No |
| **Time and resources** | The server’s event loop and the machine | A deadline and a kill by the parent; CPU and address-space limits set in the child; the parent’s watch of resident size; a bounded queue that answers `busy` | Against a slow or greedy child, yes; it limits nothing the child is allowed to do |
| **Environment** | Secrets in variables, stray descriptors, and the working directory | An allowlisted environment, `/` as the working directory, no inherited descriptors, standard input from `/dev/null` | Hygiene: the child can still read the files those secrets came from |
| **Authority** | The reader’s files, network, and other processes | The operating system refuses what the policy does not grant: `sandbox-exec` on macOS, Landlock and seccomp on Linux | Yes, with the gaps under [The Enforcement Matrix](#the-enforcement-matrix) |

Two **tiers** follow.
A **separate** child has the first four.
A **confined** child has all five.
The first revision of this plan specified a separate worker and called the result
isolation; a consent for it can honestly say only “runs as you”.

#### What Exists Today

Three children on `main` each start their own way:

|  | PDF render child | SQLite readers | Markdown child |
| --- | --- | --- | --- |
| Where | `builtin_plugins/pdf/preview.py`, `preview_isolation.py`, `render_child.py` | `sqlite_readers.py` | `diff/markdown_projection_worker.py` |
| Lifetime | One per render | A pool of two | One, long-lived |
| Interpreter | The server’s, `-I -B` | The server’s, `-I -c` with a bootstrap | The server’s, `-I -m` |
| Environment | Three variables | Inherited | Inherited |
| Working directory | `/` | `/` | Its module’s folder |
| Process group | Its own session | The server’s | Its own group |
| Deadline | 10 s, then its group is killed | 2 s inside, 1 s more, then killed | 5 s, then stopped and replaced |
| Limits in the child | CPU, no file growth, no core, no fork, address space on Linux | Address space on Linux | None |
| Lifeline | None needed | Standard input closing | Standard input closing |
| Backpressure | A semaphore | A queue of 8, then `busy` | A render cap |
| Authority | `sandbox-exec`, deny by default, on macOS; none on Linux, where an untrusted source’s preview is refused | None | None |

Each choice was measured and is right for its child.
What is missing is that they are one decision made three times, that the only
confinement lives inside a plugin, and that Linux has none.

#### The Facility

A core package, `src/metabrowser/isolation/`, that every one of these and the plugin
worker start through.
It holds no policy of its own, and it keeps two things apart.
**Containment** is what a child may touch.
**Supervision** is how a child is started, watched, and ended.
Git and `gh` take supervision alone; the PDF child takes both.

```python
@dataclass(frozen=True, slots=True)
class Confinement:
    read: tuple[Path, ...] = ()        # beyond the child's own code and the system's libraries
    write: tuple[Path, ...] = ()
    network: Literal["none", "internet"] = "none"
    processes: Literal["none", "confined"] = "none"  # may it start programs; they inherit
    programs: tuple[Path, ...] = ()    # what it may exec when processes == "confined"

@dataclass(frozen=True, slots=True)
class Limits:
    cpu_seconds: int | None = None
    address_space_bytes: int | None = None  # Linux only
    resident_bytes: int | None = None       # watched by the parent, on both platforms
    file_growth: bool = True

Requirement = Literal["required", "preferred", "none"]

def decide(requirement, backend, confinement) -> Enforcement | Literal["no_sandbox"]: ...
async def spawn(argv, *, enforcement, limits, environment, cwd, pass_fds, deadline) -> Child: ...
```

| Module | Holds |
| --- | --- |
| `policy.py` | `Confinement`, `Limits`, `Enforcement`, and `decide`: pure data and the rule |
| `probe.py` | One real probe per backend, run once, replaceable in goldens as `set_sandbox_probe` is |
| `macos.py` | A policy rendered as a profile, generalizing `macos_profile` |
| `linux.py`, `_confine.py` | The Landlock and seccomp launcher: one standalone file, usable as a prefix command and loadable by path by Metabrowser’s own children |
| `child.py` | `spawn`: the group, the watchdog, the deadline, capped reads, reaping by pid |
| `groups.py` | The stop registry, moved out of `git/process.py` and `git/children.py` |

- **A backend is a command prefix.** That is the shape `preview_isolation.Sandbox`
  already has, and the seam takes a second backend as it stands: the repository’s
  unmodified render child drew the suite’s sample PDF behind the Linux prefix, byte for
  byte the bare render, and `isolation_for` answered `Isolation` where today it answers
  `no_sandbox` (`probes.py pdf`). Because it is a prefix, the child can be another
  environment’s interpreter, and the confinement is in place before that interpreter
  starts, which matters: an environment’s `.pth` files run as it starts, and one written
  for the probe was refused its write behind the prefix (`probes.py pth`).
- **`decide` is `isolation_for`, generalized,** with three requirements.
  `required` and no backend: the launch is refused with `no_sandbox`, and the route or
  plugin says so. `preferred` and no backend: the child starts separate, and every
  surface says “not confined”.
  `none`: supervision only.
  There is never a silent downgrade.
- **`Enforcement` records what is actually enforced,** property by property, for the
  backend and kernel at hand.
  `--doctor`, `GET /api/plugins`, and the consent print it, so the three cannot
  disagree, and a kernel that lacks one piece is named, not averaged away.
- **The probe is real.** A backend counts only after a child started under it has run
  and been refused a read and a socket, as the PDF probe starts the real render child
  today.
- **The policy is data,** and each backend renders it.
  A caller never writes a profile or a filter.
- **Supervision is one shape,** and [Process Model](#process-model) states it for a
  worker: `subprocess` with `close_fds`, `pass_fds`, `process_group=0`, and `cwd`; a
  group led by a watchdog that holds a lifeline; a deadline with a grace; reaping by
  pid; output read under a cap; and one stop registry.
  Its constants stay with the callers that measured them.
- **Nothing else starts a process.** A structural test, in the shape of
  `test_only_the_named_modules_start_git`, fails when a module in `src/` outside the
  facility does.

**What the extraction fixes on the way.** The existing children have defects that one
launch removes:

- The SQLite readers inherit the server’s whole environment, stay in its group and
  session, and have only an address-space limit.
- `render_child.py` says `RLIMIT_NPROC` of zero “makes a fork fail” and `RLIMIT_FSIZE`
  of zero “makes any write to a file fail”.
  The first does not hold for root and stops threads for an ordinary account; the second
  leaves truncation, removal, and renaming allowed (the second review’s runs).
  So `Limits` has no process count: a child that may start nothing is refused by the
  filter, which lets threads through (`confine_probe.py`).
- Four kinds of child have four stop paths: Git and `gh` through a registry, the
  Markdown child through `stop_children` and a poll of its parent, the readers through
  standard input, and the PDF child through none.

#### Who Uses It

| Caller | Requirement | Read | Write | Network | Processes |
| --- | --- | --- | --- | --- | --- |
| PDF preview, untrusted source | required | Its code only | Nothing | none | none |
| PDF preview, trusted folder | preferred | The same | Nothing | none | none |
| SQLite readers | none at first, then preferred | The subject’s folder and the pool’s private folder | The private folder | none | none |
| Markdown child | none at first, then preferred | Its code only | Nothing | none | none |
| Git, `gh` | none |  |  |  |  |
| Plugin worker, a repository’s | required | The environment and its base interpreter, the editable roots its `.pth` files name, the runtime, the clone, the served folder and scoped folders, and declared reads | The plugin cache, a private temporary folder, and its own bytecode cache | none unless declared and approved | confined |
| Plugin worker, a source the user added | preferred | The same | The same | As declared | confined |

The extraction changes no behavior for the PDF preview on macOS and gives it a backend
on Linux, where an untrusted source’s card has no image today.
Metabrowser’s own children can confine themselves as they start, with no extra process;
a foreign interpreter needs the prefix.

#### The Enforcement Matrix

What enforces each property, by platform.
The macOS observations are from the
[worker probe](../../../../explorations/plugin-worker-spike/README.md#results) on macOS
26.5.2, Apple Silicon.
The separate PDF preview coverage is in `tests/test_pdf_preview_sandbox.py`. The Linux
column was observed in `confine_probe.py` and `probes.py` on kernel 6.18, Landlock ABI
7, x86-64, as root, which both mechanisms bind like any account.

| Property | macOS, `sandbox-exec` | Linux, Landlock and seccomp | Observed on Linux |
| --- | --- | --- | --- |
| Read a file | A `file-read*` allowlist refused reading and listing outside the grants. File metadata is allowed. | Landlock, kernel 5.13 | Refused outside the grants; that a path exists stays visible |
| Write a file | A `file-write*` allowlist refused writes in read-only grants and outside the grants. | Landlock | Refused in a read-only grant and outside the grants |
| Network: none | TCP connect, UDP send, DNS, and a Unix socket connection refused. Creating a UDP socket succeeded. | The filter fails `socket` and `io_uring_setup`; Landlock adds TCP from 6.7 | TCP, UDP, and a Unix socket by path refused |
| Network: internet | `network-outbound` admitted TCP, UDP send, and DNS. The Unix socket outside the grants remained refused. | The filter admits the two internet families only | TCP and UDP allowed; a Unix socket by path refused |
| Start a program | Default rules allowed a system tool and fork. With `processes: none`, both were refused and threads still worked. | Landlock’s exec right by path; the filter for `fork` and `clone` | With `processes: none`, a tool and a fork refused and a thread started; otherwise a tool runs, confined too |
| Signals and other processes | A signal to the parent was refused. | Landlock scopes signals and abstract sockets from 6.12, and ptrace to its own domain | A signal to the parent refused |
| System services | `getpwuid` needed libinfo. POSIX semaphore creation was refused. The tested hooks completed without either grant. | The keyring, `bpf`, and `perf_event_open` fail in the filter | The keyring call refused |
| Memory | No address-space limit; the parent watches resident size | `RLIMIT_AS`, and the same watch | Not run here |
| Inherited descriptors | `subprocess.Popen(pass_fds=...)` carried both protocol pipes through `sandbox-exec`. A same-number `posix_spawn` dup2 left a close-on-exec pipe closed. | Usable | Usable |
| Leaving the confinement | A nested `sandbox-exec` failed with `EPERM`. | Refused; both survive `exec` and are inherited | Not run here |

**The hole a filter on `socket` alone leaves.** Landlock does not judge a connection to
a Unix socket by its path, and `IORING_OP_SOCKET` makes a socket with no `socket` call.
With `io_uring_setup` left open, a confined child connected to a Unix socket outside
every grant, the kind an SSH agent or a session bus listens on; with it refused, it
could not (`confine_probe.py`, the column “io_uring left open”). This plan’s second
revision had that hole, and the second review found it.
The filter is a list of refusals, so the next such door is a risk this design carries:
`mb-v2m7` decides between this list and a filter that allows only what a Python worker
calls.

What it does not hold:

- **The inherited descriptors are the remaining channel.** For a worker these are the
  protocol pipes, so the host checks every call a worker makes and bounds every frame
  ([Protocol](#protocol)).
- **A granted folder is granted whole.** A confined worker can read every file in the
  clone and the served folder, including ones no plugin needs.
- **macOS privacy grants.** The profile refused reads outside its grants in the CLI
  probe. Whether the installed app’s privacy grants reach the worker and when TCC checks
  a denied read remain open.
- **A program started in a session of its own** outlives a group kill, unless the policy
  refuses new processes.
- **Linux before 5.13,** a kernel with Landlock turned off, an architecture the filter
  does not know, and Windows have no backend.
- **`sandbox-exec` is deprecated by Apple** and is what its own tools still use; the
  probe finds out on each machine, and a macOS that drops it leaves no backend.

Cost on Linux: the prefix adds one interpreter start, about 20 ms to a trivial child and
to a worker’s start, and 37 ms to one PDF render (`results/` in the spike folder).
The [macOS result](../../../../explorations/plugin-worker-spike/README.md#results)
records both sets of startup timings.
The PDF probe took 0.10 to 0.16 s on macOS.

#### What a Manifest Declares

A plugin states what it needs beyond the default grants, and the consent shows it:

```toml
[plugin.needs]
read = ["~/.config/workflow"]   # further folders to read
write = []                      # further folders to write
network = "internet"            # none (the default) or internet
run = ["git"]                   # programs beyond its own interpreter; they run confined too
environment = ["WORKFLOW_HOME"] # variables passed to the worker
unconfined = false              # true: it cannot run confined, and says so alone
```

- **Every need is a grant under `confined`,** the network and further writes included: a
  worker ran with the internet families allowed and everything else still refused
  (`confine_probe.py`). Per-host rules are not offered, since neither platform enforces
  them.
- **The grant is the intersection of what is declared and what was approved.** A need
  that appears in a later version is refused until approved, with a line in the bar
  (“workflow now asks to use the network”); nothing asks on a version bump that declares
  nothing new. So what asks again is a change in what the code may do, not a change in
  the code.
- **`unconfined = true`** is for a plugin that cannot run confined at all.
  It is shown alone, is never granted by the bar’s Trust button, and loads only under
  authority `full` (Key Decision 11).
- **A denial reads as one.** The runtime catches a refused access at the hook’s boundary
  and says that the worker is confined and which need to declare.
  In author mode an audit hook logs each file, connection, and program a hook asked for,
  which is the list to declare.
- The table is read by the host from the manifest, never from the worker, and the
  manifest is found without importing anything ([The Registry](#the-registry)).

What confinement breaks for a plugin that declares nothing, by reading and not yet
measured on the three plugins: configuration under the home directory, library caches
written there (the worker’s `XDG_CACHE_HOME` and `TMPDIR` point inside its write grant),
SQLite opened read-write in the served folder, Git writing its index, and
`multiprocessing` where programs are refused.

#### How It Fits the macOS App

- **Process groups.** The app stops a folder by signalling its server’s process group
  (`ServerSupervisor`). A child that leads its own group is not in it, so the server
  stops its children when it is told to stop, and each child’s lifeline ends it when the
  server is killed outright.
  The watchdog must hold the server lifeline in a separate process, so a worker blocked
  in native code cannot hold it.
  The macOS watchdog probe confirmed the test group exited after its server was killed.
  A live app test still needs to stop a folder and check that no worker remains.
- **Privacy grants.** A worker with authority `full` is a descendant of the app.
  Which app identity macOS uses to decide privacy access for the worker remains to be
  measured. Test with the distribution-signed app and a synthetic protected file.
  First demonstrate that an app-approved read reaches the intended child.
  Keep the system setting fixed, run the confined worker with and without a grant for
  that file, and record the read result and any prompt.
  The existing CLI probe only established the refusal outside the sandbox’s file grants.
- **Signing and the hardened runtime.** Nothing is added to the signed bundle.
  `sandbox-exec` is the system’s, and the worker is the plugin environment’s
  interpreter, a separate executable.
  An ad-hoc signed, hardened-runtime Swift launcher started a host whose confined worker
  served its hooks. The installed app’s full launch and privacy path remains to be
  exercised.
- **A sandboxed `metab`.** An outer macOS sandbox refused a nested `sandbox-exec`, and
  the PDF probe reported no backend.
  A clone trusted as `confined` loads no plugin Python when the backend is unavailable.
  That is the safe answer, and `--doctor` says why.
  On Linux both mechanisms stack, so a worker confined inside an agent’s sandbox is
  narrower still (inferred from the kernel’s documentation, not run).

### Sources and Scopes

Every source has a kind and a scope.
The scope says which servers use it.

| Kind | How it arrives | Scope | JavaScript | Python |
| --- | --- | --- | --- | --- |
| Built-ins | the release | everywhere | yes | in the server |
| Entry points in Metabrowser’s environment | whoever installs into it | everywhere | yes | in the server until Phase 5, then a worker on Metabrowser’s interpreter |
| A directory | `metab --plugins-add DIR` | everywhere, or named folders | yes | in a worker on an isolated interpreter |
| An environment: a venv, a uv project’s, or a uv tool’s | `metab --plugins-add PATH` | everywhere, or named folders | yes | in a worker on that environment |
| A repository clone | proposed by discovery, decided by the user | that clone, the worktrees it lists, and named folders | yes | in a worker on the clone’s primary environment, confined unless the user chose `full` |
| `--plugins-dir DIR` | the operator, for one command | that process | yes | none |
| `--plugin-env PATH`, `--plugin-repo` | the operator, for one command | that process | yes | in a worker |

- **Precedence.** Later rows win a plugin-name collision, and `--doctor` reports every
  collision. A repository source may not take a built-in plugin’s name; the other sources
  keep today’s rule, where a later plugin replaces an earlier one by name.
- **Environment identity.** An environment is its prefix, the directory holding
  `pyvenv.cfg`. Its interpreter, in a uv environment, is a symlink to the shared base
  Python, so it identifies nothing.
  Two entries with one prefix are one source.
- **Python floor.** The runtime runs on Python 3.12 and later, Metabrowser’s own floor,
  and is tested on an interpreter other than the host’s. The floor is read from
  `pyvenv.cfg`, without running the interpreter; `--doctor` refuses an older environment
  and says why.

### The Registry

`plugins.yml` lives in the state home (Key Decision 7).

- It is a record with the Softschema contract `metabrowser:PluginSources/0.1`. Unlike
  `config.yml` it is read **fail-closed by entry**: an entry with a field this `metab`
  does not know is kept on a write and not used, because several Metabrowser versions
  can share one home and a newer one may have added the field to narrow a grant.
  `--doctor` names each entry it did not use and the release that wrote it.
- `metab` writes it by atomic replace under the home’s lock.
- It names code to run, so it is read through the home’s verified reader with sharing
  refused rather than repaired, and `--doctor` says why a refused registry was not used.
- Serving reads it when it exists and never creates the home.
  Serving already imports the home module on `main`, for the recent-targets list.

```yaml
softschema:
  contract: metabrowser:PluginSources/0.1
  envelope: plugins
plugins:
  sources:
    - id: workflow
      kind: environment
      environment: ~/src/workflow/.venv
      authority: full
      scope: everywhere
      added_at: 2026-11-12T10:00:00Z
      added_by: 0.14.0
    - id: app
      kind: repository
      decision: trusted
      authority: confined
      clone: ~/src/app
      clone_token: 5f0c1e7a9b2d4c6e8a1b3d5f7092a4c6
      environment: ~/src/app/.venv
      origin: github.com/example-org/app
      providers:
        - name: app-viewer
          from: editable:app-viewer
          directory: app-viewer/src/app_viewer/plugin
          granted: {}
        - name: workflow-lib
          from: editable:vendor/workflow-lib
          directory: vendor/workflow-lib/src/workflow/plugin
          granted: {network: internet}
      folders: [~/data/app-runs]
      decided_at: 2026-11-12T10:05:00Z
    - id: stranger
      kind: repository
      decision: denied
      clone: ~/src/stranger
```

- **`clone_token`** is 128 random bits that the trust mode writes to
  `<common directory>/metabrowser/clone-token`, owner-only, and records here.
  A clone matches a decision only when its path and its token both do.
  A reclone has no token; a hostile archive cannot hold the right one; a copy of the
  whole clone to another path does not match the path.
  Git ignores files it does not know under its directory, and nothing is written to the
  working tree.
- **`environment`** is the prefix the decision approved.
  A different prefix, whether the repository’s settings named a new one or the old one
  moved, is undecided until approved.
- **`providers[].directory`** is the plugin directory the decision approved, and a
  directory the repository’s `dirs` setting adds is a provider like any other: a
  directory that changes or appears asks.
- **`providers[].granted`** is what was approved of that provider’s declared needs.
  A worker gets what is both declared now and granted here.
- **`providers[].from`** is where the distribution was installed from, as its
  `direct_url.json` or its index records it, relative to the clone where it is inside
  it. A provider whose `from` changes is treated as new.
- **`origin`** is shown, normalized, for the user to read, and binds nothing.
- A denied clone records only its path, so a reclone at a denied path stays quiet;
  denial grants nothing, so its identity needs no strength.

**Listing.** A provider’s plugin directory is found from its metadata, without importing
it. A wheel’s `RECORD` lists every file it owns, its `manifest.toml` among them; an
editable install’s `RECORD` lists a `.pth` file whose path line is the source root, and
the plugin directory is the `manifest.toml` with an `index.js` beside it under the entry
point’s package there.
That is what uv writes for both, and a locator of that shape found both in under a
millisecond with no provider module imported (`probes.py locate`). So a manifest, its
hooks, and its needs are known before consent, a JavaScript-only packaged plugin never
starts a worker, and a cold start imports nothing.
Only where the metadata does not say, a `.pth` that is code or an install with no
`RECORD`, is an entry point imported to ask, in a worker and after the decision.
What is cached, in the cache home and keyed by the environment’s fingerprint (its
`pyvenv.cfg`, the base interpreter’s identity, and the modification times of
`site-packages`, each `*.dist-info`, and each `*.pth`), is only those imported answers.

### The Plugin Runtime

The runtime is `metabrowser_sdk`: a standard-library-only package, published as its own
distribution, that Metabrowser depends on at one exact version (Key Decision 1).

- **One copy, four uses.** The server and built-in plugins import it;
  `metabrowser.plugin_api` re-exports it, so `main`’s documented imports keep working in
  process; a worker gets the host’s copy first on its path, whatever the environment
  holds; and an author’s environment may install it to type-check and test against.
- **What it holds.** One implementation of each thing the host and plugins must agree
  on, which is every name `metabrowser.plugin_api.__all__` exports on `main` and
  `CLIError`:
  - the inventory identity codec, moved out of `inventory_engine.contract`;
  - the path helpers and `register_root_callback`, bound to the worker’s subject;
  - `ArtifactPath` and the content error family (`gz_io` and `content_errors`, already
    standard library only);
  - the content reader and its types, which in a worker call the host, so they read a
    Git pin and keep the host’s bounds;
  - `LogEvent`, `LogParser`, `register_log_adapter`, `registered_log_adapters`,
    `create_parser`, and `detect_adapter`;
  - the table-source protocol, its types, cell and token helpers, and bounds;
  - host services: the agent-log chart projection, which in a worker is a call to the
    host; its memo, which a worker keeps for itself; `jsonl_parse_max_bytes`; and
    `plugin_cache_directory`, which answers the folder the host made and granted;
  - the worker loop, `HookRequest`, and `HookResponse`.
- **Bound two ways.** In the server the runtime’s host-facing functions call the
  server’s own. In a worker they call the host over the protocol.
  A fixture plugin runs both ways in the suite and its transcripts must match, so the
  two bindings cannot drift.
- **Hooks.** A hook takes a request and returns a response or a JSON-compatible value,
  and may be `async`. `HookRequest` provides `method`, `query_params`, `headers`,
  `path_params`, `body()`, and `json()`. A Starlette response is accepted by its
  `status_code`, `body`, and `raw_headers`. A streaming or file response is refused with
  a message.

Entry points still installed into Metabrowser’s own environment run in process until
Phase 5, through the same package, so nothing binds them differently during the
transition.

**Extension points a worker serves, and when.**

| Extension point | Phase | In a worker |
| --- | --- | --- |
| `[[data_hook]]` | 1 | A call per request |
| `[plugin] register` | 1 | Imported as the worker starts, on the host’s `register` |
| Log adapter parsers | 3 | Batched parse calls, one parser per stream |
| `[[view]] offer` | 3 | Designed in Phase 3 from a measurement: it runs for every folder page and text file today, which a worker started on demand cannot answer without a wait |
| `[[table_source]]` | 3 | The five source methods as calls, and `read_window` as a host call |

Until an extension point’s phase, `--doctor` refuses a worker plugin that declares it,
by name, and the plugin’s other parts load.

### Process Model

A worker is a child of the isolation facility, with a protocol on top.

- **Proposed worker grouping** (Key Decision 9). One worker serves one server and one
  root. Providers in the same environment with the same grants can share a worker.
  Provider-specific grants require the startup and import controls in the Phase 1
  acceptance test.
- **Started on evidence.** A worker starts at the first hook call or parse for one of
  its plugins, or when the server first classifies a file into a kind one of them owns.
  It exits after an idle period that Phase 1 sets from measurements.
  An open live stream does not hold it: a live stream is at most 2 MiB, so re-priming a
  parser in the next worker is cheap.
- **How it is started.** With `subprocess`, as every other child is: `close_fds`,
  `pass_fds` for its pipes, `process_group=0`, and `cwd="/"`. The proposed launch begins
  with
  `[confinement prefix] <watchdog> <interpreter> -I -X pycache_prefix=<its cache> <runtime>/worker.py <request fd> <reply fd>`.
  The `-I` flag still permits startup code installed in the environment.
  This command needs additional startup and import controls before it can support
  provider-specific grants.
  The pipes’ numbers are arguments, not fixed descriptors: raw `posix_spawn` closes
  nothing it was not told to, cannot set a working directory, and a fixed number
  collides with whatever the host already has there.
- **The bytecode cache** goes under Metabrowser’s cache home, so nothing is written into
  the plugin environment and a foreign interpreter compiles the runtime once.
  Each worker’s cache is its own write grant and no other worker’s: bytecode one worker
  writes is code the next one to read it runs.
- **A watchdog leads the group.** The group’s leader is not the worker but a small
  trusted program, the confinement launcher or `/bin/sh`, which holds a lifeline pipe
  from the server, starts the worker, and kills its own process group when the lifeline
  ends or the worker exits.
  A lifeline inside the worker cannot promise that: a worker whose hook sat in native
  code holding the interpreter lock was still running 2 s after its request pipe closed,
  and a worker that does exit leaves the programs it started.
  The watchdog ended a target that ignores signals, and that target’s child, within half
  a second of the server’s kill (`probes.py lifecycle` and `watchdog`). The worker’s
  reader also exits at end of file; that is the fast path, not the guarantee.
- **The server learns a worker is gone by waiting on its pid,** never from end of file
  on the reply pipe, which a forked child can hold open.
- **Signals.** SIGINT is not ignored.
  A worker outside the server’s group never receives Ctrl-C, and an ignored signal is
  inherited by every program a plugin starts.
- **Standard streams.** Descriptor 0 is `/dev/null`, descriptor 1 is moved to 2, and 2
  is a pipe the host drains under a cap into the server’s log, under the source id.
- **An allowlisted environment.** A worker gets `HOME`, `USER`, `LOGNAME`, `TZ`, the
  locale and proxy names, the server’s `PATH`, `PYTHONNOUSERSITE=1`, a private `TMPDIR`
  and `XDG_CACHE_HOME`, and the names its plugins declare.
  This is hygiene: only confinement keeps a plugin from the file a key came from.
- **An import guard.** The worker installs a finder that fails `import metabrowser` with
  a sentence naming `metabrowser_sdk`. Without it a plugin that has not moved would bind
  silently to whatever Metabrowser its environment holds, with no root, which is what
  the brief’s Option G did.
- **Changes under a running worker.** A worker’s generation is its environment’s
  fingerprint and the stamp `asset_stamps.py` already computes for each plugin
  directory, compared at most once in an interval Phase 1 measures, off the event loop
  and never per call. The fingerprint alone does not see an edit to an editable plugin’s
  source, which is all three of the motivating plugins.
  Python outside a plugin’s directory changes only at a worker restart, and the page
  says so when a plugin’s JavaScript is newer than its worker.
- **Repeated failure.** Three failed starts in a row, then a cool-off, as the Markdown
  child has. A kill at a hard deadline counts against the hook, not the environment.

#### Protocol

One multiplexed stream each way, over the two pipes.
This is the specification a golden session and the fault tests hold; the table of
operations grows as phases add them.

1. **Framing.** `u32 header length | u32 body length | header, one JSON object | body`,
   as the Markdown child frames.
   Both lengths are known before anything is parsed, so no read is unbounded.
   A header is at most 64 KiB and a request body 1 MiB; the response bound is a constant
   Phase 1 measures (64 MiB took 122 ms and held a small call behind it for 31 ms in one
   run and 153 ms in another, so a large reply goes in chunks other frames may pass).
2. **The reply pipe is untrusted input.** A frame past a bound, a header that does not
   parse, or an id the host did not issue ends the worker’s group and never raises in
   the host’s reader. The spike’s reader died on both a malformed frame and an unknown
   id.
3. **Handshake.** The host sends `hello {build, root, subject, cache_dir, scratch}`. The
   worker answers `ready {build, python, pid}`, or `wrong_build` and exits (Key Decision
   8). The start has a deadline.
   The host does not trust a worker’s own word that it is confined: the prefix fails
   closed before `exec`, and a test reads `NoNewPrivs` and `Seccomp` from `/proc`.
4. **Calls.** `call {id, plugin, hook, method, query, headers, deadline_ms}` and a body.
   Every handler, `async` or not, runs off the thread that reads the pipe and off the
   loop that dispatches, so a blocking `async def` hook stalls only the handlers’ loop.
   The runtime refuses its own oversized response before sending it, so an honest
   overrun is an error answer and never a protocol fault.
5. **Cancellation.** `cancel {id}` cancels a coroutine and marks a synchronous handler’s
   budget expired, the `Budget` table sources already use.
   A client that goes away cancels, and the host answers at once; it never ends a
   worker.
6. **Deadlines, two levels,** as the SQLite readers have.
   At the deadline the call is cancelled and answered with the degraded `plugin_error`
   envelope. At the deadline plus a grace, with the handler still running, the group is
   killed, calls past their own deadlines fail, a `GET` in flight that is not past its
   own is sent once more to the replacement, and the refusal is kept for that plugin,
   hook, and query for a time, so a reloading page cannot loop kills.
   Today’s in-process hooks have no deadline, and the motivating hook took 1.8–2.6 s
   under load, so the default must clear what real hooks take.
7. **Backpressure.** Calls in flight per worker are capped, with a short queue, then
   `busy`, as the readers and the Markdown child answer theirs.
   The host’s writes do not block; a write stuck past its deadline is a fault.
   A worker’s calls to the host are capped per call and refused once that call has
   ended.
8. **Streams.** `stream.open {sid, adapter}` and `stream.lines {sid}`; the host keeps
   each cursor. A new worker gets `open` and a replay up to the cursor with its events
   discarded.
9. **Memory.** The host reads a worker’s resident size on an interval.
   Past a soft bound it recycles the worker when idle; past a hard bound it kills the
   group. `RLIMIT_AS` is a backstop on Linux only, since address space is not memory.
10. **Host calls are checked** against the calling worker’s root, subject, and grants on
    the host, whatever the worker’s runtime already checked: under confinement the pipes
    are the worker’s only way out.

| Direction | Operation | Phase | Purpose |
| --- | --- | --- | --- |
| Host to worker | `hello` | 1 | Bind the root and check the build |
| Host to worker | `register` | 1 | Import the plugins’ register modules |
| Host to worker | `call`, `cancel` | 1 | Run a data hook; cancel one |
| Host to worker | `ping` | 1 | The handlers’ loop still answers |
| Host to worker | `locate` | 1 | Import an entry point to find its plugin directory, only where the metadata does not say |
| Host to worker | `stream.open`, `stream.lines` | 3 | A stream’s parser, and a batch of its lines |
| Host to worker | `offer`, `table` | 3 | View offers and table-source methods |
| Worker to host | `content.*` | 1 | The content reader, by a handle the host keeps for that call |
| Worker to host | `charts.project` | 1 | The agent-log chart projection, which is the built-in plugin’s code |
| Worker to host | `detect` | 3 | Adapter detection, which the host owns |

The chart memo (`lookup_agent_charts`, `remember_agent_charts`) is kept in the worker.
As a host call it would let one worker plant a payload that another plugin’s view
serves.

#### Threats

The rows this plan adds to the [threat model](../../architecture/arch-threat-model.md).
That document requires a change to a policy to name the threat it answers, or add one,
in the same pull request, so each row lands there with the code that answers it.

| Actor | What it can do | The answer | What remains |
| --- | --- | --- | --- |
| A repository the reader browses | Write every byte of the tree: `.git`, `pyproject.toml`, a tracked `.venv`, `.metabrowser/` | Nothing from an undecided clone runs, in any mode: no interpreter of its environment starts. Discovery reads data only, each file and the walk bounded. A clone is known by its token, and membership is read from the clone’s side | The bar is a prompt, and prompts get clicked; what it grants by default is confined |
| A dependency the clone locks | Run code as the environment’s interpreter starts (`.pth`) and at import, without being a plugin provider | Confinement is in place before the interpreter starts; the consent says that everything in the environment runs, not only the listed providers | Under `full`, it runs as the reader |
| A plugin’s author, later | Ship a new version of an approved provider: Python and JavaScript | The grant is what was approved, so a version that needs more asks; the lock pins the version | JavaScript reads the served folder and can send it anywhere the page can |
| A sandboxed agent in the clone | Edit approved code, the clone’s settings, perhaps `.venv`; run `metab --present` outside its sandbox | The default grant is narrower than an agent’s sandbox: read the clone, write a cache, no network. The decision binds the environment and each plugin directory. `--present` takes no plugin option | Under `full`, an edit runs as the reader; a terminal can answer a prompt |
| Another local account | Write group- or world-writable paths; call the loopback server | The ownership rule, on the paths code is loaded from; the state home is owner-only | Hooks answer any local caller, as the server has no authentication |
| Plugin JavaScript | Call any route of the page’s origin, other plugins’ hooks included | No route writes a source or a decision, and none writes under an environment, a plugin directory, `.metabrowser/`, or `pyproject.toml`; the chart memo is per worker | Another plugin’s hooks, the `gh`-backed ones among them: accepted, and stated in the consent |
| A worker, against the server | As the same account: loopback HTTP, `/proc`, ptrace, signals | Confined: sockets refused, signals and ptrace scoped, `/proc` ungranted. Every host call is checked and every frame bounded | Unconfined, there is no boundary; memory up to the bounds |
| A request | Carry a path that leaves the root | The runtime’s identity codec, and the host’s check of every host call | None known |
| A hook’s response | Serve HTML that runs on the application origin | Hook response headers | A hook that sets its own permissive policy |
| An upgrade under a running server | Pair an old host with new runtime files | The build stamp | None known |
| A copied or older registry | Carry a grant to another machine, or lose a narrowing field | The state home; entries read fail-closed | A state home copied by hand |

### Hook Response Headers

A hook can serve another site’s HTML, as the data-room plugin serves captured pages, and
`/api` accepts a same-origin or typed navigation, so headers decide whether that HTML
runs scripts on the application origin.

- **The list comes from an inventory.** A test collects every header a built-in hook
  sets or reads and fails when the policy would drop one.
  On `main` that includes `Content-Encoding` on the diff hook’s stored gzip body and
  `x-metabrowser-verified` on the pull-request hooks, both of which the first revision’s
  list refused.
- **Passed through:** `content-type`, `content-encoding`, `content-disposition`,
  `content-language`, `content-range`, `accept-ranges`, `cache-control`, `etag`,
  `last-modified`, `vary`, `server-timing`, the `x-metabrowser-*` names, and every
  header that restricts: `content-security-policy`, `x-content-type-options`,
  `referrer-policy`, `x-frame-options`, `permissions-policy`, and the
  `cross-origin-*-policy` family.
- **Refused:** headers that widen access or move the client (`set-cookie`,
  `access-control-*`, `location`) and, for a worker’s hook, anything not listed.
- **Added by the host:** `X-Content-Type-Options: nosniff` on every hook response.
  Active worker documents such as HTML, SVG, and XML also receive a separate enforcing
  CSP from the host on every response.
  The host policy sandboxes the document and denies scripts and external loads.
  A hook’s own CSP can further restrict it.
  Test direct navigation and embedding in a browser.
  Check the known raw HTML preview’s inline styles and data images before fixing its
  host policy. The
  [macOS research](../../research/research-2026-11-12-plugin-sources.md#macos-follow-up)
  records why the host owns this restriction.
- **Request headers passed to a worker:** `accept`, `accept-encoding`, `content-type`,
  `content-length`, `range`, `if-none-match`, `if-modified-since`, and
  `x-metabrowser-pin`.
- **Two steps.** Worker hooks get the policy with the worker, in Phase 1. Applying the
  refusals and the default policy to in-process hooks, built-ins included, is its own
  change with its own changelog fragment, because it can change what an existing
  plugin’s HTML does.

### Log Adapters

Detection moves into the manifest, so classifying a file need not wait on a worker (Key
Decision 10):

```toml
[[log_adapter]]
name = "batch"
detect = { key = "event", equals = "batch_start" }

[[log_adapter]]
name = "rollout"
detect = { all = [
  { key = "type", in = ["session_meta", "response_item"] },
  { key = "payload", type = "object" },
] }

[[log_adapter]]
name = "banner-first"
detect = { any = [
  { key = "type", equals = "init" },
  { line_prefix = "YOLO mode" },
] }
```

- The three declarations above are examples of the language, not the built-in ones.
- `detect` is a predicate over each of a stream’s first 20 lines, built from `equals`,
  `in`, `prefix`, `has`, `type`, `all`, and `any` on a parsed object, with dotted keys
  for a nested value, and `line_prefix` for a line that is not a JSON object.
  The last three are what the built-in detectors need that the first revision’s language
  lacked.
- **The built-in adapters move first.** The `agents` plugin declares its five in this
  language, and a test holds each declaration to its old detector over the plugin’s
  fixtures before the detector is deleted.
  Then there is one mechanism.
- **One source of truth.** A declared adapter registers its parser with
  `register_log_adapter(name, parser_factory=...)`; the `detector` argument goes with
  the code detectors, in the SDK break that carries this.
  `detect_adapter` in a worker asks the host.
- **Order** stays as on `main`: discovery order, built-ins first, each detector
  recognizing only its own format.
  A name already declared cannot be claimed, and two plugins claiming one is a
  `--doctor` error.
- **The JSONL paths change order.** `/api/file` and the pin content routes parse the
  whole file and then classify from the parse summary.
  Each will detect from the head first, classify, and only then parse, in the owning
  worker for a worker plugin’s adapter.
- **Parsing stays the plugin’s code,** batched, one parser per stream id in the owning
  worker, for a file view and a live stream alike.
- **The wire shape is measured first,** paired: today’s in-process pipeline and the
  proxied one on the same machine and log, back to back.
  The first spike’s proxied parse cost 2.5–3.5 times the bare parse; the in-process
  figure it was compared with came from another session under another load and decides
  nothing.

### Plugin API Compatibility

- **One version.** `sdk_version` in the manifest names the plugin API, browser SDK and
  runtime together (Key Decision 8), and follows Cargo’s caret rule for `0.x`: a version
  is `0.MINOR.PATCH`, an addition bumps PATCH, and a break bumps MINOR. The host accepts
  a manifest with its MINOR and a PATCH no greater than its own, and refuses a newer
  PATCH as needing a newer Metabrowser.
  Today’s `0.8` reads as `0.8.0`, so no manifest changes when the rule lands.
- **Gate before the schema.** The gate reads `sdk_version` from the raw TOML before the
  manifest model validates, because the model forbids unknown fields: an older host
  would otherwise report a newer manifest’s `[[log_adapter]]` as a schema error instead
  of naming the Metabrowser version it needs.
- **Changes are data.** `plugin_loader/sdk-changes.toml` records each version’s
  additions, changes, and removals by surface name.
  A refusal names the changes between the plugin’s version and the host’s, and a test
  fails when the current version has no entry.
- **No deprecation window by default.** A break bumps MINOR and the plugin updates, as
  the repository’s rule has it.
  A surface keeps working past its removal only for a consumer named in
  `sdk-changes.toml`, with a `--doctor` note, and for one release.
- **The build stamp is not a version.** It is the host’s exact build, compared for
  equality in `hello`; nothing negotiates.
- `AGENTS.md`, the Standing Compatibility Answers, and a changelog fragment change in
  the same pull request as the gate.

### Repository Plugins

A repository carries plugins in two ways, and discovery finds both with no
Metabrowser-specific file:

- **Its own plugin:** a package in its Python project (in the downstream application
  repository, two workspace members declaring `metabrowser.plugins` entry points), or a
  directory checked in under `.metabrowser/plugins/<name>/`.
- **A library’s plugin:** any distribution in the clone’s environment that declares a
  `metabrowser.plugins` entry point, from an index or, like the workflow library, from a
  vendored submodule. The clone pins it as it pins anything, in `uv.lock` or a gitlink.

#### Discovery

For a folder server, never a Git source opened from a URL, a pin, a mirror, or an
`--untrusted` session, and again whenever a server’s subject changes:

1. **The clone.** The served folder never says which clone it belongs to.
   A folder belongs to a recorded clone when its resolved top level is that clone’s
   path, or the clone’s `worktrees/<name>/gitdir` names the `.git` file at that top
   level, or the folder is under one of the record’s `folders`. A `.git` file or a
   `commondir` in the served folder is never read for this: three forgeries, a `.git`
   file naming the clone’s Git directory, one naming one of its worktrees, and a `.git`
   directory holding only `HEAD` and `commondir`, each made Git report the trusted
   clone, and the clone held a back-pointer to none (`probes.py identity`). A worktree
   moved by hand leaves a stale back-pointer and is undecided until
   `git worktree repair`. For a clone with no record, discovery finds the nearest `.git`
   directory at or above the served folder and no higher than the home directory, to
   propose it. The server’s existing repository context answers only for GitHub origins
   and checks no ownership, so it is not used.
   Outside Git, a folder has no clone and repository plugins do not apply; its plugins
   are added as a directory or an environment.
2. **The environment.** The nearest uv project or workspace root at or above the served
   folder in the clone’s primary worktree, preferring one with `[tool.uv.workspace]`,
   and its `.venv`; or a `.venv` with `pyvenv.cfg` at the primary worktree’s top level;
   or what `[tool.metabrowser.plugins] environment` there names.
   A linked worktree uses its clone’s primary environment, so a new worktree needs no
   sync and edits in it do not run until its author opts in for one command
   (`metab --plugin-repo --plugin-dev`). A bare repository has no primary worktree, so
   the trust mode asks which worktree holds the environment and records it.
3. **The providers.** Read as data: each `*.dist-info/entry_points.txt` for the
   `metabrowser.plugins` group, with its `direct_url.json`; each workspace member’s
   `pyproject.toml`, so a provider is known before the environment exists; and each
   `.metabrowser/plugins/*/manifest.toml` in the primary worktree.
   A provider is a distribution or a checked-in directory, shown with its version and
   where it was installed from.
   Nothing in that metadata tells the repository’s own plugins from a library’s (the
   brief), so the consent lists providers, not owners.
4. **Optional settings**, which no repository needs by default, in
   `[tool.metabrowser.plugins]` of the primary worktree’s root `pyproject.toml`, or in
   its `.metabrowser/config.toml`: `environment`, `exclude` by provider name, and
   further plugin `dirs`. They are data from the clone, so they can only propose: an
   `environment` or a directory they name is undecided until approved.

For an undecided clone discovery runs in serve mode only, after first paint, reads a
bounded number of distributions and plugin directories, escapes every name it shows, and
is not cached. The bounds are set from a measurement of real environments (31 ms for 127
distributions in the brief) and recorded beside their constants.
For a decided clone its result rides on the listing cache.

#### Decisions

| Decision | What is recorded | What happens automatically |
| --- | --- | --- |
| Undecided, the default | nothing | The page shows a bar naming the providers found, and `--plugins` and `--doctor` list them as undecided. No interpreter of the clone’s environment starts, in any mode, `--doctor` and `--plugins` included, since starting one runs its `.pth` files; and no plugin JavaScript, style, asset, kind, or view is served. |
| Trusted | the clone’s path and token, its environment, its normalized origin for display, each approved provider with its origin, the authority, and any further folders | Every server for a folder in the clone, a worktree it lists, or a further folder loads the approved providers’ plugins: manifests, assets, JavaScript, and a worker on the clone’s primary environment, confined unless the authority is `full`. Version bumps and pulls take effect at the next worker start without asking. A new provider, a changed origin, or a moved environment is reported in the bar and loads only once approved. |
| Denied | the clone’s path | Nothing loads, and nothing is reported beyond `--plugins --json`. |

- **One decision per clone.** The worktrees it lists share it, and a reclone at the same
  path is undecided again.
- **Review lists what the metadata says,** which is nearly everything.
  Before trust, the bar and `metab ROOT --plugins-trust` show each provider’s name,
  version, origin, and plugin directory; the environment; the grant on offer and, in one
  sentence, what it allows; and each plugin’s hooks, adapters, and declared needs, read
  from the manifest its metadata locates.
  A provider whose directory the metadata does not give is shown by name, with the note
  that its manifest is read only once it is trusted.
- **What was shown is what is approved.** A trust write takes a terminal answer, or the
  app’s confirmation, which runs `metab ROOT --plugins-trust --expect SHA256` with the
  hash it displayed; the mode refuses when the set no longer matches.
  The hash covers the clone’s path, the environment’s prefix, the authority, and each
  provider’s name, version, origin, plugin directory, and declared needs, and no file
  contents. There is no `--yes`.
- **Commands:** `metab ROOT --plugins-trust [--authority confined|full]`,
  `--plugins-deny`, `--plugins-untrust`, and `--plugins-scope-add ID FOLDER`.
- **Never trusted:** a Git source opened from a URL, a pin, a mirror, an `--untrusted`
  session, and a clone inside Metabrowser’s cache home.
  Repository plugins come only from a working tree and its environment, never from a
  revision a pull-request page or pin shows, so reviewing a pull request in Metabrowser
  never runs the plugin code it changes.
- **Deferred:** content-bound decisions, as direnv makes, and parent-folder decisions
  (Key Decision 2).

#### The Clone’s Environment

- **Present:** used as it is, the whole environment; Metabrowser never writes to it.
- **Missing or incomplete:** discovery compares the providers the workspace members
  declare with those the environment holds, and the bar and `--doctor` name the missing
  ones and say to set up the environment the way the repository documents.
  No command is guessed (Key Decision 4).
- **Outside the clone:** a `.venv` whose prefix resolves outside the clone, an editable
  install whose source is outside it, or a `.venv` tracked by Git is named in the
  consent. Under `confined` an import from outside the grants fails, and the provider is
  listed as needing a declared `read` or full access.

#### Checked-In Plugin Directories

A directory under `.metabrowser/plugins/<name>/` in the primary worktree is a provider
like a distribution.
Its Python runs in the clone’s worker, each plugin’s modules loaded from its own
directory under a package name of its own, so two plugins’ `sidekick.py` neither collide
nor shadow the environment’s modules.
In a clone with no environment, its hooks run in a worker on Metabrowser’s base
interpreter started with `-I -S`, where only the standard library and the runtime are
importable (Key Decision 3). This is the case where the consent is the only gate, since
no `uv sync` has already run the repository’s code, and where `confined` matters most.

#### For Libraries That Ship a Plugin

- Declare a `metabrowser.plugins` entry point, and import the runtime as
  `metabrowser_sdk`.
- Do not depend on `metabrowser` at run time.
  A consumer’s lock then never carries an exact Metabrowser for the plugin’s sake, as
  the downstream workspace’s does today.
  `metabrowser-sdk` may be a development dependency, for type checks and tests; it has
  no dependencies of its own.
- The consumer’s lock or gitlink decides the plugin version.
  A consumer that wants none of a library’s plugins lists it in `exclude`.

#### One Convention for Repository Extensions

The workflow library finds its own extensions through entry points in the running
environment, and its design document describes walking up to the uv workspace root for
members that are not installed (see the brief).
One convention serves both tools:

1. A repository’s extensions are entry points of its locked environment, one group per
   tool.
2. A tool running inside that environment reads them with `importlib.metadata`. A tool
   running outside it, as a system Metabrowser does, finds the environment by walking up
   to the workspace root, no further than the Git top level, and reads the metadata as
   data before running anything.
3. Content that is not a package lives under a dot directory named for the tool, and
   per-repository settings under `[tool.<name>]`.
4. Nothing from a repository runs until the user decides to trust it.

This plan changes only Metabrowser.

### Trust and Consent

| Source | Who adds it | How it is approved | Authority |
| --- | --- | --- | --- |
| A directory or environment | the account owner, with `metab --plugins-add` | it shows what the metadata declares, starts no interpreter first, and asks on a terminal | confined where the machine can, and said plainly where it cannot |
| A repository clone | discovery proposes; the account owner decides | the bar or `metab ROOT --plugins-trust`, as above | `confined`, required; `full` only by declaration or by `--authority full` |
| Per-command flags | whoever runs the command | the command line; nothing is recorded | as a source the user added; `--plugin-confined` requires it |

- **What each consent says.** `confined`: “These plugins, and everything in this clone’s
  environment that starts with them, may read this clone, its environment, and the
  folders you browse with them, and write only their own cache.
  They cannot use the network or start other programs.”
  Then each provider’s declared needs in plain words, such as “workflow asks to use the
  network”, and: “Their JavaScript runs in Metabrowser’s page.”
  `full`: “These plugins, and everything in this clone’s environment, run as you: they
  can read and change anything your account can, and so can anyone who can edit their
  code, an agent working in this clone included.”
  The environment is named because starting its interpreter runs its `.pth` files,
  whichever distribution they belong to, so the listed providers are not the boundary of
  what runs.
- **Only the owner records anything.** The state home is owner-only, with the
  configuration home’s checks on every directory above it.
- **The ownership rule.** Before a source is recorded or decided, and again before each
  worker starts, the environment’s prefix, its base interpreter, each plugin directory,
  each folder a `.pth` path line names, and the clone’s top level and common directory
  must be owned by the user or root and not writable by other accounts.
  All of those are read from metadata before any interpreter starts; a check made after
  a worker says `hello` would come after its `.pth` code had run.
  The app’s `ExecutableTrust` refuses any group-writable path, which would refuse an
  environment built on a Homebrew Python and, where a default umask makes a user’s own
  directories group-writable, most clones; `mb-5qw0` surveys real layouts and settles
  the group rule before Phase 4. The rule exists once, in the home module, and the app’s
  Swift check stays the app’s.
- **No route writes a source or a decision.** Plugin JavaScript can call any same-origin
  route, so a write route would let a JavaScript-only plugin register Python.
  Every write is a `metab` mode with a golden, and the read model is a route, so no
  surface lacks a transcript.
- **The read route shows no local paths.** `GET /api/plugins` names sources by id and
  shows locations relative to the served root or `~`; full paths appear only in
  command-line output.
- **Served content cannot opt itself in.** A `.env` file cannot name a source or record
  a decision, the repository’s own settings can only propose, an undecided clone is only
  reported, and `metab --present TARGET` changes nothing.
- **Agents.** `--present` accepts no plugin option (Key Decision 5), and a test holds
  that. [Working with Agents](../../../working-with-agents.md) gains the sentence the
  `full` consent carries, and recommends that an agent work in a linked worktree, whose
  code a trusted clone does not run.
- `SECURITY.md`, the threat model, and the trust section of `docs/plugins.md` describe
  the served root as never a plugin source; all three change in the pull request that
  lands repository plugins.

### Lifecycle

- **Add, remove, and decide** are `metab` modes.
  Until reload lands, a change to sources or manifests takes effect at the next server
  start; a Python-only change takes effect at the next worker start (Process Model), and
  `--doctor` and `GET /api/plugins` show when each worker started.
- **Update** is whatever updates the environment: `uv sync` or the repository’s own
  setup in a clone, or `uv tool upgrade`.
- **The author’s loop.** `metab ROOT --plugin-repo --plugin-dev` watches the plugin’s
  source tree and restarts its worker on a Python change; JavaScript and styles are
  served from disk, so a page reload shows them; a manifest change needs a server
  restart until reload lands.
- **A subject that changes.** A server whose root moves to a folder in another clone, or
  to a Git source, restarts, until reload exists to swap repository-scoped sources in
  place.
- **Reload without a restart (Phase 5).** The registry becomes a generation the server
  swaps whole, with `/plugin-static/`, the classifier, and the derived caches keyed by
  generation. The server watches `plugins.yml`, environment fingerprints, and manifests,
  debounced, emits `plugins-changed`, and an open page offers to reload.
  Data hooks keep one registered route each, so the parity registry’s rows stay as they
  are.

### The macOS App

The app keeps its rule: `metab` owns the data, the app owns platform behavior.

- **Settings > Plugins exists.** It lists `metab --plugins --json` today
  (`PluginInventory.swift`, the `plugins` command in `apps/macos/metab-contract.toml`).
  This plan adds `sources` to that answer and the declared keys the pane reads, and the
  actions below. The change follows the app’s contract rule: the declaration, its golden,
  and a changelog fragment in one commit, a minor release of `metab`, and a raised
  `MetabRequirement.minimumRelease`. There is no path for an older `metab`: the version
  floor refuses it.
- **Add…** opens a panel, runs `metab --plugins-add --dry-run --json PATH`, which reads
  metadata and imports nothing, and shows a native confirmation with the environment,
  the providers, the authority and its sentence, and the hash; confirming runs
  `metab --plugins-add --expect SHA256 --json PATH`. Remove runs `--plugins-remove`. The
  actions are native because they are writes no page may reach.
- **The repository bar** appears when a folder’s server reports an undecided clone or a
  new provider: “This clone provides 3 plugins: …”, with Trust, Review, and Not Now.
  Trust grants `confined` with the defaults; Review shows the consent and each
  provider’s declared needs to approve.
  The bar never offers `full`. Where the machine cannot confine, it says that these
  plugins’ Python will not run here and names the command that grants full access.
  Not Now lasts for the window and is not recorded.
  When the environment is missing it says so and what the repository documents; it runs
  no setup.
- **One set of homes.** The app passes the state home’s variables as it was launched
  with them, as `main` chose for the configuration home.
  A user who exports `XDG_STATE_HOME` only in a shell profile gets one registry in
  Terminal and another in the app; `metab --doctor` reports that, as it reports the
  cache and configuration homes today (`STORAGE_OVERRIDES` in `cli/doctor.py`). The
  first revision’s plan to read these from the login shell is withdrawn, since `main`
  decided against it and pins the decision in `tests/test_macos_app_pins.py`.
- **Applying a change.** Until reload lands, after a change the app offers to restart
  the servers it affects, through the path it uses after an upgrade.
- **Supervision, privacy grants, and signing** are under
  [How It Fits the macOS App](#how-it-fits-the-macos-app).
  The open-folder memory counts a server’s workers, and their idle exit returns that
  memory (113–121 MB each, measured).

### Remote Sessions

`metab --remote HOST --path ROOT` runs the remote host’s `metab`, so the remote host’s
built-ins, sources, decisions, and confinement backend apply.
The local registry does not travel, and `--remote` forwards no per-command sources; a
short-lived remote host loses its decisions with it.
The `--remote` wrapper gives the remote command `/dev/null` as stdin and no terminal, so
a trust write there cannot ask through it: the page’s bar names
`ssh -t HOST metab ROOT --plugins-trust`, and Phase 5 forwards `--plugins` and
`--doctor`, and runs the trust mode over a terminal-allocating SSH session.

### Diagnostics

- `metab --plugins --json` gains `sources`: id, kind, scope, decision, authority,
  location, environment prefix, Python version, listing freshness, providers, plugins,
  worker state, and problems.
- `metab --doctor` checks each source: the floor, from `pyvenv.cfg`; the ownership rule;
  the confinement backend and why there is none; the worker starts; each listed manifest
  passes the schema and the gate, with the change list on a refusal; each hook and
  parser imports; each declared adapter has a parser; collisions are reported.
  Without a root it stays rootless; given a root, it also reports that root’s clone, its
  decision, its missing providers, and why each plugin is or is not loaded.
  It starts no interpreter of an undecided source, a worker only for a recorded one, and
  closes every worker it starts.
- `GET /api/plugins` serves the same model to the page and to `--api`.
- `metab ROOT --show PATH` names the source and the process that own the selected kind.

### CLI and Routes

One executable.
The options that name a source for one command, and the modes that record
one, are `metab`’s own; none is in `--present`’s option set, and a test fails if one is
added (Key Decision 5).

| Surface | Kind | Golden |
| --- | --- | --- |
| `metab --plugins [--json]`, `--plugin NAME`, `--doctor [ROOT]` | read-only modes | sources, decisions, authorities, and problems on a fixture registry |
| `GET /api/plugins` | route | the fixture registry, with no absolute path |
| `metab --plugin-env PATH` | per-command source | a fixture environment’s hook through `--api`, an adapter kind through `--show` |
| `metab ROOT --plugin-repo [--plugin-dev] [--plugin-confined]` | per-command decision | a fixture clone’s hook through `--api`, confined and not |
| `metab --plugins-add PATH [--dry-run] [--expect SHA256]`, `--plugins-remove ID`, `--plugins-scope-add ID FOLDER` | writes `plugins.yml` | add, dry run, a set changed after the dry run, remove, refusal of a shared registry and of an environment another account can write |
| `metab ROOT --plugins-trust [--authority A] [--expect SHA256]`, `--plugins-deny`, `--plugins-untrust` | writes a decision | each decision on a fixture clone, a new provider, a changed origin, a moved environment, a reclone at the same path, a listed worktree, a forged worktree, refusal on a Git source |
| `metab --present` with any of the above | refusal | each option refused by name |
| `metab --plugins-reload` (Phase 5) | control socket | a reload after a registry change |

Each new route lands with its row in the
[Parity Registry](../../architecture/arch-parity-registry.md), which
`devtools/check_parity.py` reads, and in
[Views, Models, and Routes](../../architecture/arch-views-models-routes.md).
The page’s repository bar is a functional row with a browserless session.
Flag names are proposals.

### Workflows

**An author adds a plugin to a repository.** As a package: a workspace member with a
`metabrowser.plugins` entry point and its `plugin/` directory, then the repository’s
usual setup; `metabrowser-sdk` is a development dependency at most.
Without packaging: `.metabrowser/plugins/<name>/` with a manifest, `index.js`, and a
`sidekick.py` if it needs hooks.
The author’s clone is already trusted, so the bar reports the new provider once, and
after approval `metab . --plugin-repo --plugin-dev` gives the inner loop described under
Lifecycle.

**A teammate clones the repository and opens it**, in the app or with `metab <repo>`.
Discovery finds the providers and the bar lists them.
If the environment is missing, the bar says so and names the setup the repository
documents. After Trust, the plugins load, confined, at the next start of the folder’s
server. Later opens, and every worktree the clone lists, ask nothing.
A run folder outside the clone gets the same plugins once the teammate adds it to the
clone’s scope.

**A pull request changes the plugin.** In Metabrowser’s pull-request pages the changed
plugin never runs, since plugins load from a working tree and never from a revision a
page shows. A local checkout of the branch in a linked worktree runs the primary
checkout’s plugin, not the branch’s, until the reviewer opts in for one command.
Checked out in the primary worktree of a trusted clone, the branch’s plugin runs, with
the clone’s authority; a provider the branch adds asks first.

**An agent works in a trusted clone.** In a linked worktree, nothing it edits runs.
In the primary checkout, an approved plugin it edits runs at the next worker start with
the clone’s authority.
With the default `confined` grants, its Python can read the clone, its environment, and
the served folders. Network access requires an additional grant.
Its JavaScript runs in the page.
Under `full`, its Python runs as the user, which is why `full` is never the default.

**A library releases a new plugin version.** Nothing changes for a consumer until its
lock moves: a pull request upgrades the library or advances the submodule, CI validates
it, and after the merge each teammate’s environment update changes the fingerprint.
An approved provider’s new version from its approved origin does not ask.
A version that needs a newer plugin API is refused with the Metabrowser version it
needs, and the other plugins still load.

**CI validates the plugin.** After the repository’s own setup:

```shell
uvx --from metabrowser==0.14.0 metab . --plugin-repo --doctor --json
uvx --from metabrowser==0.14.0 metab . --plugin-repo --api '/api/plugin/<name>/<route>?path=<fixture>'
uvx --from metabrowser==0.14.0 metab . --plugin-repo --show <fixture>
```

`--doctor` fails on a refused manifest, an unimportable hook, or a missing parser; the
other two are golden transcripts of the plugin’s routes and kinds.
Adding `--plugin-confined` runs the same checks confined, on a runner whose kernel has a
backend, which tells an author before a user finds out that a hook reaches outside its
grants.
A library that publishes wheels also builds its wheel, installs it into a scratch
environment, and runs `metab --plugin-env <that environment> --doctor`.

## Implementation Plan

Each phase is one stack of pull requests to `main`.

### Phase 0: Unblock and Extract

Independent pull requests, each useful on its own:

- [ ] Declare a compatible range for Softschema (`softschema>=0.8.1,<0.10`), keep the
  exact version in `uv.lock`, record the newer end as an audited first-party selection,
  and add a CI job that installs beside a package needing it.
  KPress stays exact, as [Development](../../../development.md#dependencies) says it
  must (`mb-hi06`). The workflow library carries a Softschema override until a release
  does this.
- [ ] The isolation facility: move the launch, the limits, the backend probe, and the
  rule out of `builtin_plugins/pdf/preview_isolation.py` into `metabrowser.isolation`,
  with containment and supervision apart, and start the PDF render child, the SQLite
  readers, the Markdown child, Git, and `gh` through it.
  It fixes the defects listed under The Facility: the readers’ inherited environment,
  the limits that do not do what their comments say, and four stop paths.
  No behavior changes for the PDF preview on macOS (`mb-e7t8`).
- [ ] The Linux backend: the Landlock and seccomp launcher behind the same probe, with a
  test that shows each refusal as `tests/test_pdf_preview_sandbox.py` does on macOS, and
  previews of untrusted PDFs on Linux as its first user (`mb-v2m7`).
- [x] Run the macOS worker spike against the three downstream plugins and record the
  default grants, process and network behavior, and prefix cost (`mb-gmut`).
- [ ] Confirm privacy attribution and restricted reads through the installed macOS app.
  After the worker and its fixture child report ready, stop the folder and verify they
  both exit. Repeat with a killed server and a worker blocked in native code so the
  watchdog has to act (`mb-gmut`).
- [ ] The plugin API gate: one version, Cargo’s caret rule, read from the raw TOML,
  `sdk-changes.toml`, and refusals that name the changes (`mb-jn5e`).
- [ ] Hook response headers for in-process hooks, from an inventory test of the built-in
  hooks (`mb-x1j5`).
- [ ] `metab --doctor` reports a state home that differs between a Terminal and the
  app’s servers (`mb-eazg`, rewritten).

### Phase 1: A Real Plugin’s Hooks from Its Own Environment

- [ ] The runtime package, `metabrowser_sdk`: the identity codec, `ArtifactPath`, the
  content errors, the table-source protocol, and the host-service seams moved into it,
  `metabrowser.plugin_api` re-exporting it, its own distribution, and an import boundary
  test (`mb-3q4e`).
- [ ] The worker client on the isolation facility: the protocol and its bounds, the
  build stamp, deadlines that fail a call, the hard limit and heartbeat, the lifeline,
  backpressure, restarts, idle exit, logs, and the fault tests (`mb-nes2`).
- [ ] Per-command environment sources: `--plugin-env PATH`, the listing cache, manifests
  and assets served by the host, proxied hooks, the content reader’s host calls,
  `--doctor`’s checks, and the test that `--present` refuses each (`mb-8pg5`).
  Acceptance: the motivating plugin’s hooks, at the current SDK version, served from its
  own environment under a uv tool install, with no change to its Python beyond the
  runtime’s import name.
- [ ] One fixture plugin run in process and in a worker with matching transcripts, and a
  CI job where the worker’s interpreter is not the host’s (`mb-sbjf`).
- [ ] Before offering provider-specific grants, verify controlled interpreter startup
  and provider loading with two fixture providers in one environment that have different
  grants. Include an environment startup hook and an import across providers.
  Verify that a provider’s code cannot run under the other provider’s exclusive grants,
  including during startup.
  If this boundary cannot be demonstrated, bring the environment-wide option in Key
  Decision 9 back to the owner (`mb-p62c`).

### Phase 2: The Registry Reaches the App

- [ ] The registry in the state home, read fail-closed, with scopes, added directories
  and environments, `GET /api/plugins`, and the `sources` model (`mb-mo66`).
- [ ] The app’s Settings > Plugins shows sources and gains Add and Remove, with the
  contract declaration, its golden, and the raised version floor (`mb-mtpe`).

After this phase an app user registers a plugin environment once and its hooks work in
every folder, which is the requirement’s first half.

### Phase 3: Adapters, the Remaining Extension Points, and the Three Plugins

- [ ] `[[log_adapter]]` with declarative detection, the built-in adapters ported to it,
  the reordered JSONL paths, parsing in the owning worker for file views and live
  streams, stream re-priming, and the wire shape from a paired measurement (`mb-b11t`).
- [ ] View offers and table sources in a worker, designed from a measurement of what an
  offer costs per folder page (`mb-i6i6`).
- [ ] The three downstream plugins declare their adapters, import `metabrowser_sdk`,
  drop their exact Metabrowser pins, and are verified from their own environments
  (`mb-uas1`).
- [ ] The author harness: `metabrowser-sdk` as a development dependency, a fixture that
  runs the real worker, the startup scripts and on-demand bundles served as data for
  browser harnesses, and the CI pattern above (`mb-fiju`).

### Phase 4: Repository Plugins, Confined

- [ ] A survey of real environments and clones against the ownership rule, which settles
  how it treats group-writable paths (`mb-5qw0`).
- [ ] Repository discovery, per-clone decisions bound to a clone token, an environment,
  and providers with their origins, worktrees by the clone’s back-pointer, further
  folders, missing-provider reports, the bar’s model, and the `SECURITY.md`, threat
  model, agents guide, and `docs/plugins.md` changes (`mb-nkc3`).
- [ ] Authority: the manifest’s `[plugin.needs]`, the grant as what is both declared and
  approved, the consent’s wording, a worker confined to its grants, `full` only by
  declaration or by command, and `no_sandbox` where no backend exists.
  Bind grants to providers only after the Phase 1 isolation check passes.
  The alternative is environment-wide grants, subject to the owner’s decision
  (`mb-p62c`).
- [ ] Checked-in `.metabrowser/plugins/` directories, with their Python in the clone’s
  worker or on an isolated interpreter (`mb-wpq3`).
- [ ] The app’s repository bar, with its contract entries (`mb-qoh1`).

### Phase 5: Live Lifecycle, Remote Sessions, and One Path

- [ ] Reload without a restart (`mb-0e0i`).
- [ ] Remote sessions forward `--plugins` and `--doctor`, and the trust mode over a
  terminal (`mb-9i2l`).
- [ ] After the three plugins have run in workers for a release, entry points in
  Metabrowser’s own environment move to a worker on its interpreter, and the in-process
  path for third-party plugins goes, except on Windows (`mb-qdp4`).

Managed package environments (`mb-8ii8`) are deferred out of this plan: an environment
the user makes with uv and registers does the same job without a fourth home or an
installer inside Metabrowser.

## Testing Strategy

- **A fixture plugin environment built offline.** A standard-library venv whose plugin
  is installed by writing its `dist-info` and a `.pth` file, as `probes.py` in the spike
  does, so no test needs a network or a build backend.
  It holds one hook, one adapter, one view, and one register module.
- **A fixture clone.** A Git repository with a uv workspace holding a plugin member, a
  distribution from outside the clone, a `.metabrowser/plugins/` directory, a linked
  worktree, and a forged one.
- **Isolation.** For each backend, a child that is refused each row of the enforcement
  matrix and allowed the same attempt bare; the rule’s table with a backend of the
  test’s choosing, so it is the same on every platform; a launch refused with
  `no_sandbox` where confinement is required and absent.
- **The runtime and protocol.** A golden session of normalized frames between the host
  and the real worker, and fault tests: a worker that exits mid-call, a hook past its
  deadline with another call in flight, a blocking `async def` hook, the hard limit, a
  header past its bound, garbage on the reply pipe from a forked child, a hook that
  leaves a subprocess, SIGINT, an oversized body, a worker-to-host call in the middle of
  a hook, the request pipe closing while a hook blocks, and a worker started from
  another build’s files.
- **The doors of the confinement.** A socket through `io_uring`, a fork and a thread
  with programs refused, the internet families with the network granted, and a `.pth`
  line that tries to write, each as `confine_probe.py` and `probes.py pth` run them; and
  a test that reads `NoNewPrivs` and `Seccomp` of a running worker from `/proc`.
- **Supervision.** The watchdog ends a target that ignores signals, and its child, when
  the server is killed; a worker whose hook holds the interpreter lock in native code; a
  hook that forks, and one that uses `multiprocessing`; an inherited ignored signal; and
  the host noticing a dead worker whose forked child still holds the reply pipe.
- **No interpreter before a decision.** For an undecided clone and for a dry run of add,
  every mode, `--doctor` and `--plugins` included, with an environment whose `.pth` file
  leaves a mark if it ever runs.
- **Membership and identity,** each a named test: the three forgeries, a `.git` file
  naming the clone’s Git directory among them; a worktree moved by hand; a reclone at
  the same path; and a changed plugin directory or `dirs` entry.
- **The import guard.** `import metabrowser` in a worker fails with the sentence that
  names `metabrowser_sdk`.
- **Conformance.** One fixture plugin’s `--api` transcripts in process and in a worker,
  equal; and on an interpreter other than the host’s.
- **Goldens through `metab`.** Every row of the CLI and Routes table.
- **Headers.** The inventory of built-in hooks; a hook returning HTML with and without
  its own policy, through the proxy and in process; the refused headers.
- **Records and decisions.** The registry’s contract; an entry with an unknown field
  kept and not used; refusal of a shared registry; serving never creating a home; for
  each decision and authority, exactly what loads and what is reported; a new provider;
  a changed origin; a moved environment; a reclone at the same path; a listed worktree
  running the primary environment’s code; a forged worktree staying undecided;
  `--expect` refusing a changed set; the ownership rule; no repository plugins on a Git
  source, a pull-request page, or under `--untrusted`; an undecided clone whose page
  requests no plugin asset; and `GET /api/plugins` naming no absolute path.
- **Compatibility.** The caret rule’s table; the gate refusing a newer manifest by
  version, not by schema; `sdk-changes.toml` covering every version.
- **Performance.** Phase 1 records worker start, listing, memory, hook overhead by
  response size, and the cost of the confinement prefix, with the spikes’ probes; Phase
  3 records end-to-end log parsing against today’s in-process pipeline, paired.
- **The app.** `ShellCore` tests for settings and launch commands, the contract golden,
  and the signed-app privacy and shutdown tests in
  [How It Fits the macOS App](#how-it-fits-the-macos-app).
- **Downstream acceptance.** Start the three providers from their own environments with
  both the uv tool and the installed app.
  Check hook response parity, adapter output, and served assets.
  Use the macOS spike’s synthetic hook cases, add the workflow report routes, and verify
  the host’s active-document policy in a browser.

## Rollout Plan

- Phase 0’s extraction changes no behavior on macOS; the Linux backend gives untrusted
  PDFs a preview there, and the header change for in-process hooks carries its own
  changelog fragment.
- Phase 1 and Phase 2 change no existing plugin’s behavior: entry points keep loading in
  process, and the new sources are additive.
  A changelog fragment records the gate’s rule.
- Phase 3 carries the SDK break that retires code detectors, with the built-in manifests
  in the same commit.
- Phase 4 changes nothing for a clone until the user decides; the first open shows the
  bar.
- Phase 5 removes the in-process path for third-party plugins only after a release with
  all three running in workers.
- Each change to what the app reads of `metab` is a minor release and raises the app’s
  version floor.

## Open Questions

- The eleven Key Decisions above, each awaiting the owner.
- Whether the installed app attributes privacy access to its descendants and ends the
  entire worker group when it stops a folder (`mb-gmut`).
- Whether the Linux filter stays a list of refusals or becomes a list of what a Python
  worker may call; the first is what the spike ran and what `io_uring` got past.
- Whether a page that loads a non-built-in plugin’s JavaScript should carry
  `connect-src 'self'`, which would keep that JavaScript from sending the served folder
  elsewhere.
- The names `metabrowser_sdk` and `metabrowser-sdk`, `metabrowser.isolation`,
  `.metabrowser/`, `[tool.metabrowser.plugins]`, and every flag.
  Publishing a second distribution brings release mechanics: versioning, publish order,
  and its first-party entry.
- The idle-exit period, the default deadline, the hard limit, the heartbeat, the cap on
  calls in flight, and the response bound, each from a measurement.
- Whether plugin JavaScript should ever be limited to its own plugin’s routes, which
  would need a boundary the page does not have.
- A Windows worker.
- Whether the workflow library adopts the same repository convention.

## References

- Research:
  [Loading Plugins from Any Source](../../research/research-2026-11-12-plugin-sources.md),
  [Native macOS App for Metabrowser](../../research/research-2026-11-08-macos-app-packaging.md)
- Plans: [Native macOS app](plan-2026-11-10-native-macos-app.md)
- Architecture: [Threat Model](../../architecture/arch-threat-model.md),
  [Plugin System](../../architecture/arch-plugin-system.md),
  [The macOS App’s Contract with metab](../../architecture/arch-app-contract.md)
- Guides: [Plugin Authoring](../../../plugins.md),
  [Working with Agents](../../../working-with-agents.md),
  [Compatibility and Legacy Code](../../../development.md#compatibility-and-legacy-code),
  [supply-chain security](../../../../SUPPLY-CHAIN-SECURITY.md)
- Code: `src/metabrowser/plugin_loader/`, `src/metabrowser/plugin_api.py`,
  `src/metabrowser/builtin_plugins/pdf/preview_isolation.py`,
  `src/metabrowser/sqlite_readers.py`,
  `apps/macos/Sources/ShellCore/Runtime/ChildEnvironment.swift`,
  `explorations/plugin-worker-spike/`
- [Cargo’s caret requirements](https://doc.rust-lang.org/cargo/reference/specifying-dependencies.html#caret-requirements),
  [Landlock](https://docs.kernel.org/userspace-api/landlock.html)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
