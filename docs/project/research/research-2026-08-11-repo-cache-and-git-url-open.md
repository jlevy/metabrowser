# Research: Repo Cache and Open-from-Git-URL

**Date:** 2026-08-11

**Author:** Joshua Levy (with LLM assistance)

**Status:** Complete

## Overview

Today `metab` serves a directory that already exists on disk.
This research asks what it would take to accept a Git URL instead:

```shell
metab https://github.com/owner/repo
```

Metabrowser would clone the repo into a purgeable local cache, then serve it like any
other directory. The motivating claim is that reading someone else’s code in a local
browser can be faster and less limited than reading it on github.com, and that the same
capability makes the Metabrowser skill useful to an agent that has been asked to look at
a repo it does not have.

Two properties make this more than a convenience wrapper around `git clone`:

- **History comes for free later.** The Git diff epic (`mb-ypme`) and its history
  browsing phase (`mb-8bjd`) assume a real repository.
  A cached clone satisfies that assumption, so a URL-opened repo eventually gets blame,
  log, and content-at-revision without any URL-specific work.
- **The cache is reusable.** Unlike an API-backed viewer, the bytes land in a directory
  that grep, an editor, and an agent can all read.

The decision this research supports is whether to build the feature, and if so which
clone strategy, cache layout, and purge policy to commit to.

## Questions to Answer

1. Which clone strategy gives a fast first render without breaking the history browsing
   already on the roadmap?
2. What should the cache look like on disk, and how does it get purged?
3. What is the CLI and skill surface, and how is a URL distinguished from a path?
4. Does something already do this, and is GitHub Desktop a better answer?
5. What changes when the served tree is code someone else wrote?

## Scope

Covered: clone strategy benchmarks, cache layout and eviction, Git preflight and
authentication, the CLI and skill surface, and the trust consequences of serving a
fetched tree.

Not covered: the design of the history browsing UI itself (see
`research-2026-07-17-web-diff-viewer-architecture.md`), non-Git version control, and any
hosted or multi-user deployment.
Everything here assumes the existing single-user localhost model.

## Findings

### The two halves of this feature both exist; the join does not

A survey of the space found mature prior art for each half and nothing that combines
them.

For the cache half, [ghq](https://github.com/x-motemen/ghq) (MIT, actively maintained)
is the established tool.
It clones into `~/ghq/<host>/<owner>/<repo>`, supports `--shallow` and `--partial`, and
offers `ghq rm --dry-run` for cleanup.
Its layout is the de-facto convention.
It has no browsing UI at all; the intended pairing is `ghq list | fzf` and then `cd`.

For the local-UI half, [klaus](https://github.com/jonashaag/klaus) (ISC) is the closest
Python neighbor — `pip install klaus` serves local repos with syntax highlighting and
ctags navigation — and `git instaweb` is built into Git.
Neither can fetch from a URL; both take a path to a clone you already have.

Tools that do accept a URL discard the result.
[gitingest](https://github.com/coderamp-labs/gitingest) clones with
`--single-branch --no-checkout --depth=1` into a temp directory, produces a flat text
digest, and then deletes the clone, so every re-read re-clones.
[Repomix](https://github.com/yamadashy/repomix) does the same into a system temp dir.
Both target LLM ingestion rather than reading, and the digest for a small repo such as
`psf/requests` is already around 170k tokens.

The pattern that practitioners actually use is a hand-rolled persistent clone.
This repository’s own `tbd checkout-third-party-repo` shortcut instructs agents to clone
into a gitignored `attic/` directory, check out the tag matching the lockfile, and reuse
the checkout across sessions — with the explicit rationale that “GitHub blocks scraping,
results are messy, and you lose full codebase context.”
That is direct evidence for the premise, and evidence that the workflow is currently
being reinvented per project.

### GitHub Desktop is not the thing to beat

GitHub Desktop ([desktop/desktop](https://github.com/desktop/desktop), MIT, actively
maintained) has no file browser.
Its interface is a Changes list for the working tree, a History list of commits and
their diffs, and branch and PR management.
There is no tree view of the repository’s files and no way to open an arbitrary
unchanged file; the answer to “let me read this file” is an *Open in External Editor*
menu item that launches VS Code.

It is also a mildly negative example on the storage axis.
It performs a full clone with no depth control in the UI, and its default location on
macOS is `~/Documents/GitHub`, which is typically iCloud-synced — a long-standing
complaint ([issue #3970](https://github.com/desktop/desktop/issues/3970)). There is no
preference for a default clone path; it remembers the last directory used
([issue #2106](https://github.com/desktop/desktop/issues/2106)).

So GitHub Desktop is a Git-operations GUI, not a source-reading one.
The real competition is different:

- **github.dev** (press `.` on any repo) is zero-install and one keystroke away.
  It does not clone; it reads through the GitHub API over a virtual filesystem.
  Documented limits include no terminal, no debugging, and degraded language
  intelligence because most language servers do not understand the virtualized
  environment. Every file read is a network round-trip, and offline use is impossible.
- **github.com code search** requires being logged in even for public repos, indexes
  only the default branch, excludes files over 350 KiB, truncates lines over 1,024
  characters, and excludes non-UTF-8 and vendored files.
- **DeepWiki and gitmcp.io** are free and instant for agents, but answer questions about
  a repo rather than handing over the source.

The differentiators that survive that comparison are: works offline, needs no login, has
no file-size or default-branch limits, keeps all branches and full history, and leaves
bytes on disk that other tools can use.

### Clone strategy: blobless plus background backfill

This is the central technical finding, and it inverts the obvious answer.

The obvious answer is `--depth=1 --single-branch`, which is the fastest clone by a wide
margin. But history browsing is already on this project’s roadmap, and a depth-1 clone
cannot serve it. Measurements below were taken on macOS with Git 2.50.1 over a
residential connection; clone times vary with network conditions by roughly a factor of
two between runs, so read them as ratios rather than absolutes.

Clone cost, `pallets/flask` (small) and `django/django` (large):

| Strategy | flask time | flask `.git` | django time | django `.git` |
| --- | --- | --- | --- | --- |
| Full | 6.5 s | 13 MB | 108.9 s | 294 MB |
| `--filter=blob:none` (blobless) | 2.8–5.3 s | 5 MB | 16.5 s | 82 MB |
| `--filter=tree:0` (treeless) | 6.0 s | 4 MB | — | — |
| `--depth=1 --single-branch` | 1.6 s | 1 MB | 4.6 s | 14 MB |

History operations on each `flask` clone, against `src/flask/app.py`:

| Operation | Full | Blobless | Treeless | Shallow |
| --- | --- | --- | --- | --- |
| `git log --oneline -20 -- <file>` | 0.07 s | 0.03 s | **36.5 s** | 0.02 s, 1 commit only |
| `git blame` (cold) | 0.21 s | **22.9 s** | **fails** | **exits 0, wrong answer** |
| `git show HEAD~50:<file>` | ok | ok | ok | **fails** |

Three strategies are eliminated by that second table:

- **Treeless** (`--filter=tree:0`) is unusable.
  A path-limited log took 36.5 seconds because every commit’s tree must be fetched
  individually, and blame fails outright.
  Worth stating explicitly because `scalar clone` uses partial clone with sparse
  checkout by default, which is similarly hostile to a file browser.
- **Shallow** cannot show history, and it fails in the worst possible way.
  `git blame` on a depth-1 clone **exits 0 and returns a wrong answer**: every line is
  attributed to the single graft-boundary commit, where a full clone attributes the same
  file across 23 distinct commits.
  A silently wrong answer is worse than an error for a history-browsing feature, and it
  disqualifies shallow independently of any performance argument.
  Deepening later is also not a cheap repair: `git fetch --unshallow` on the django
  clone took 90 seconds, more than cloning it fully in one step.
- **Plain blobless** looks good until the first blame, which took 22.9 seconds cold
  because Git fetches missing blobs one round-trip at a time.
  Warm it is 0.05 s. That first-blame cliff is a bad experience and it recurs for every
  file the user visits.

The resolution is `git backfill`, added in Git 2.49, which bulk-fetches the missing
blobs in batches instead of one at a time:

| Repo | Blobless clone | `git backfill` | `.git` after | Blame after |
| --- | --- | --- | --- | --- |
| flask | 2.8 s | 4.2 s | 14 MB | 0.02 s |
| django | 16.5 s | 99.3 s | 275 MB | 0.68 s |

Clone blobless, serve immediately, and run `git backfill` in the background.
The user starts browsing after 2.8 s on flask and 16.5 s on django instead of 6.5 s and
108.9 s — a 2.3x and 6.6x improvement in time-to-first-render — and by the time they
reach for history the repository is complete.

Be honest about what this does and does not buy.
Backfill is **not** cheaper in total: it is equal to or more work than a plain full
clone, and an independent run measured the gap as wide as 123 s versus 53 s on django.
The entire win is in ordering.
If the backfill is not genuinely moved off the critical path, a full clone is strictly
better, so backgrounding it is a correctness requirement of this design rather than a
refinement.

One qualification from Stolee’s guidance, which applies directly: *“If you are a
developer focused on a single repository and your repository is reasonably-sized, the
best approach is to do a full clone.”* For small repos, blobless adds machinery for
little gain. A size threshold — full clone below it, blobless above — is worth
considering rather than applying one strategy everywhere.

This ordering also matches what the tool is for.
Metabrowser’s first screen is a file tree and a rendered file, and both need trees but
almost no blobs. Blobless clone delivers exactly the objects the first screen needs and
defers exactly the ones it does not.

### Serving a fetched repo is a trust change, not just a path change

Everything Metabrowser serves today is a directory the user chose and, in the common
case, wrote. A URL-opened cache is the first case where the served tree is code an
arbitrary third party wrote, fetched automatically.
That is a category change and it couples this feature to work already in flight.

The active HTML rendering and trust-model epic (`mb-wyd4`) is building exactly the
machinery this needs: sandboxed `/raw` responses (`mb-cun0`), a capability set and an
`--untrusted` profile (`mb-vib1`), and sandboxed HTML preview (`mb-4x15`). A repo opened
from a URL should default to the untrusted profile.
Without it, opening a stranger’s repository means rendering their HTML, SVG, and
Markdown in a browser tab that shares an origin with a local API. **This feature should
not ship before `mb-vib1`.**

Clone-time exposure is narrower than it first appears, and two common worries are
unfounded.
Hooks are not transmitted by clone: a fresh clone’s `.git/hooks` contains only
`*.sample` files, verified directly for both HTTPS and local-path transports.
Repository config is likewise not cloned, so `core.fsmonitor`, `credential.helper`,
`core.sshCommand`, and `.gitattributes` filter drivers cannot execute on a fresh clone —
filter drivers are defined in config, which the repo cannot supply.

That said, **“cloning is safe” has been falsified repeatedly**, so it should be treated
as a property of a *patched* Git rather than of Git in general.
CVE-2024-32004 was arbitrary code execution during local clones; CVE-2024-32002 achieved
RCE through case confusion on macOS and Windows filesystems, and required
`--recurse-submodules`; CVE-2024-32465 exists precisely because *“it is supposed to be
safe to clone untrusted repositories.”* A further batch was fixed in 2.50.1 and its
backports. Git version is a security dependency here, which strengthens the case for a
floor and for surfacing the detected version.

The remaining items each have a cheap answer:

- **Symlinks** are the most direct risk and the one that needs no Git bug at all — a
  repo can simply contain `escape.txt -> ../../../../etc/passwd`, and Git will restore
  it faithfully. Two independent defenses apply, and both should be used.
  Metabrowser’s existing helpers already handle it, checked rather than assumed:
  `_safe_path` in `paths_safe.py` resolves the joined path and rejects anything not
  contained in the root using `relative_to` rather than a string prefix, every walker
  scans with `follow_symlinks=False`, and the inventory rewalk refuses both targets
  resolving outside the root and symlinked directories.
  On top of that, cloning with `-c core.symlinks=false` materializes symlinks as plain
  text files containing the target path, which is both harmless and arguably more
  informative in a file browser.
- **Submodules** are the one place a repo controls what gets fetched, via URLs in
  `.gitmodules`, and they are the precondition for CVE-2024-32002. Pass
  `--no-recurse-submodules` explicitly and set `-c fetch.recurseSubmodules=false`;
  surface submodule directories as empty and let the user opt in.
- **`.git/` must not be served.** It holds `config`, `logs/`, and `packed-refs`, and if
  a user ever cloned with an embedded token the credential sits there in plaintext.
  Exclude it explicitly, including case variants such as `.GIT`, since macOS and Windows
  filesystems are case-insensitive.
- **Do not enable `transfer.fsckObjects`.** This is the obvious hardening move and it
  breaks cloning real repositories — Flask itself fails with
  `zeroPaddedFilemode: contains zero-padded file modes`, because legacy objects
  routinely trip strict fsck.
  The security value is low for a browsing tool and the false-positive rate is not
  acceptable.
- **Restrict transports.** The classic clone-URL escape, `ext::sh -c '…'`, is already
  blocked by default (`protocol.ext.allow` defaults to `never`, verified), but the URL
  parser should allowlist schemes before Git ever sees the string, and the clone should
  pass `-c protocol.allow=never` with explicit `https` and `ssh` allowances.
  Arguments must go through `subprocess` list form with a `--` separator, and inputs
  beginning with `-` rejected, since an option-shaped URL was CVE-2017-1000117.
- **Size** is unbounded, and Git has no built-in guard against tree bombs.
  Blobless helps incidentally — the bomb’s blobs are never fetched — but the checkout
  still expands. A subprocess timeout, a per-repo size cap that aborts and removes the
  temp directory, and the walker’s existing inventory limits are the practical guards.
- **`safe.directory`** ownership checks, already flagged in the diff research, apply
  here too and need a deliberate policy and a clear error.

### Git preflight: never prompt, and never guess why a clone failed

Two things about invoking `git` from a tool that is about to open a browser tab turn out
to matter more than they look.

**Never let Git prompt, and never let it hang.** Without suppression, a private or
misspelled URL makes Git block on an interactive username prompt — for a command whose
next step is starting a server and opening a browser, that is a hang with no visible
cause. `GIT_TERMINAL_PROMPT=0` is necessary but not sufficient: it does not suppress the
Windows credential manager, and it does not stop a GUI passphrase dialog on desktop
Linux or macOS. The full recipe also needs `GIT_ASKPASS` and `SSH_ASKPASS` neutralized,
`SSH_ASKPASS_REQUIRE=never`, `GCM_INTERACTIVE=never`, a `GIT_SSH_COMMAND` carrying
`-o BatchMode=yes -o ConnectTimeout=10`, plus `stdin=DEVNULL` and a wall-clock
subprocess timeout, which no environment variable substitutes for.

Credentials themselves need no handling — the user’s existing helper (`osxkeychain`,
`gh auth setup-git`, or an SSH agent) supplies them, and Metabrowser should never read,
store, or pass a token.
The critical corollary is that hardening must **add** to the environment with `-c` flags
rather than suppress config files.
`GIT_CONFIG_GLOBAL=/dev/null` is tempting for sandboxing an untrusted clone and it
silently breaks every private-repo clone; on macOS `GIT_CONFIG_NOSYSTEM=1` is worse,
because `osxkeychain` is configured in a packager-shipped *system* gitconfig.
Similarly, `GIT_SSH_COMMAND` must not add `-F /dev/null`, which would break every user
whose `IdentityAgent` lives in `~/.ssh/config`.

**A missing repo and a private repo are indistinguishable — but only once you have
credentials.** With a working helper, both return the identical message:

```
remote: Repository not found.
fatal: repository 'https://github.com/owner/repo.git/' not found
```

Worth being precise about the mechanism, because it is commonly misstated.
The same-404-for-both policy is a **REST API** behavior.
Over the git protocol GitHub returns **401** with
`www-authenticate: Basic realm="GitHub"` for both a nonexistent and an inaccessible
repo, which is why an unauthenticated clone never reaches “not found” at all — it asks
for a username instead.
So there are two distinct failure shapes to handle, and every one of them exits 128,
meaning the exit code carries no diagnostic information and stderr must be matched:

| Situation | Message to match |
| --- | --- |
| No credentials at all | `could not read Username for … terminal prompts disabled` |
| Credentials, repo missing *or* private | `remote: Repository not found.` |
| Expired or invalid token | `Invalid username or token.` |
| SSH with no usable key | `Permission denied (publickey).` |
| Network | `Could not resolve host` |

The message for the ambiguous case must name both possibilities rather than picking one,
and two free local signals narrow it considerably: `gh auth status --json hosts` exposes
token scopes, and a missing `repo` scope is a common cause of “not found” on a repo that
does exist.
Probing the REST API is not worth a round trip, since unauthenticated it 404s
for both cases.

> Could not read `owner/repo`. It either does not exist, or your account cannot see it —
> GitHub returns the same response for both.
> Check the URL, then try `gh auth login`.

**Version detection should degrade, never refuse.** The `git version ` prefix is a
stability contract in Git’s own source, but everything after it is vendor-defined:
`2.50.1`, Apple’s `2.39.5 (Apple Git-154)`, `2.44.0.windows.1`, and `2.55.GIT` from an
untagged build all occur.
Parse the leading numeric components with an anchored regex, compare at most three, and
treat unparseable as unknown.
Do not feed the raw string to `packaging.Version`, which fails on the Apple and untagged
forms.

A floor of **Git 2.26** is the reasonable choice: it makes protocol v2 the default,
which materially reduces round trips for lazy fetches, and it is the first release where
`--sparse` works over URLs.
Below it, fall back to a full clone silently.
`git backfill` gates separately at **2.49** and should be treated as a pure optimization
wrapped in error handling — its own man page stamps it experimental, and its options
have shifted across 2.53 through 2.55.

### Cache layout and purge policy

Purging is the weakest area among the repo tools surveyed — `ghq rm --dry-run` is the
only prior art and it is entirely manual — so the language-ecosystem caches are the
better model. Worth correcting two widely-held beliefs: cargo has had automatic GC on
stable since 1.88 in June 2025, and Bazel’s disk cache has had GC since 7.4. What they
share is a shape worth copying: the cache is inspectable, prunable by an explicit
command, and never silently deleted underneath a running process.

The layout should follow the `ghq` convention, `<host>/<owner>/<repo>`, for three
reasons: it is predictable enough to type and to `cd` into, it makes an existing `ghq`
user’s checkouts trivially interoperable, and it keeps the path human-legible in the
Metabrowser title bar.
A content hash would dedupe better but is unreadable, and dedupe is not the pressing
problem. Segments still need sanitizing — case folding, Unicode normalization, Windows
reserved names, and `..` rejection — with a short hash of the canonical URL appended
whenever sanitizing changed the name, so the mapping stays injective.

Per-repo sidecar metadata is preferable to a central index: origin URL, clone strategy,
Git version, cloned/fetched/accessed timestamps, and byte size.
A central index is a second concurrency problem, since every process would
read-modify-write it, and a single point of corruption.
Sidecars make the cache self-describing and hand-purgeable, which matters for a
directory users will `du` and `rm -rf` themselves.
Place the sidecar and the lock file *beside* the repo directory rather than inside it,
so both survive the atomic swap and neither is ever served.

Atomicity is not optional, and the reason is concrete.
A clone killed with `SIGKILL` leaves a directory where
`git rev-parse --is-inside-work-tree` returns true but `rev-parse HEAD` fails — a corpse
that any naive `if (dir / ".git").exists()` check would happily serve.
Cloning into a temp directory and publishing with a rename makes that state unreachable
by construction, which is stronger than any validity check.
Two mechanical caveats: the temp directory must live inside the cache root so the rename
stays on one filesystem, and `os.replace` onto a non-empty directory fails with
`Errno 66`, so replacing an existing entry means renaming the old one aside first.
Git’s own failure on a duplicate destination is not a lock — it creates the directory
immediately, leaving a genuine race — so use `fcntl.flock` on a lock file next to the
repo, held for the clone and released before serving, with `backfill` and `fetch` taking
their own.

Freshness turns out to be cheaper and safer than expected, which softens the case for
avoiding it. A no-op `git fetch` on a blobless clone measured 0.45 s — *less* than the
`git ls-remote` probe at 0.68 s, since there are no blobs to negotiate — so there is no
point probing before fetching.
More importantly, `git fetch` does not touch the working tree: an uncommitted local edit
in a cached repo survived a fetch intact.
That gives a safe-by-construction policy: **fetch only, never `pull`, never
`reset --hard`, never `checkout`**, since those would clobber a user poking at the
cache. Serve cached state immediately and unconditionally, fetch in the background when
the last fetch is stale, record failures in the sidecar so an offline user is not
retried on every page load, and never auto-advance the checkout.
New commits then become visible to history browsing, which reads refs and objects,
without the worktree moving underneath anyone.

For eviction, repo entries differ from package entries in being large, few, and
individually expensive to re-obtain.
That argues for a **total-size cap as the primary control** with LRU by last access,
defaulting to something like 10 GiB, and a generous secondary age sweep at around 90
days — closer to Homebrew’s 120 than Go’s 5, because re-cloning costs minutes rather
than milliseconds. Run it opportunistically at most once a day, triggered by a command
already doing network work, with no daemon; skip it entirely when offline, following
cargo’s rule of never destroying a cache the user may be about to need without a network
to restore it. Never evict a repo under an active lock or one currently being served.
Two small details worth copying: Go coalesces last-access writes to at most once an hour
rather than trusting filesystem `atime`, which is often disabled by `noatime`; and
`rmtree` must tolerate `EACCES`, because Git writes read-only files into `.git/objects`
and purge would otherwise fail on exactly the repos most worth purging.
A `CACHEDIR.TAG` at the cache root is one line and makes restic, borg, and
`tar --exclude-caches` skip the whole thing.

### CLI surface: a ROOT that may be a URL, plus cache modes

The flat CLI already has the right shape for this.
`ROOT` is a single positional that serve mode interprets, and `main.py` keeps a
declarative `_MODE_OPTIONS` table that rejects options which do not apply to the
selected mode. Cache management is a natural new mode alongside `--plugins` and
`--doctor`, and it should reuse that table rather than growing a parallel mechanism.
The open bead to derive that metadata from one declarative table (`mb-1t99`) becomes
more valuable, not less, with another mode in play.

```shell
metab https://github.com/owner/repo              # clone if needed, then serve
metab https://github.com/owner/repo/tree/main/src # deep-link a subpath
metab git@github.com:owner/repo.git               # SSH form
metab --cache                                     # list cached repos with age and size
metab --cache-purge                               # prune, reporting before removing
```

**Git already accepts the URL, so there is much less parsing to do than it first
appears.** This is the single most useful simplification in the design, and it is worth
stating before any parser is specified.
Tested against live GitHub with `git ls-remote`:

| Input | Git accepts |
| --- | --- |
| `https://github.com/pallets/flask` | yes |
| `https://github.com/pallets/flask.git` | yes |
| trailing slash | yes |
| `https://github.com/PALLETS/FLASK` | yes — GitHub is case-insensitive |
| `git@github.com:pallets/flask.git` | yes — parsed fine; only auth failed in testing |
| `…/tree/main/src` | **no** |
| `…/blob/main/README.md` | **no** |
| `…?tab=readme-ov-file` | **no** |
| `…#readme` | **no** |
| `pallets/flask` | **no** |

For a plain repository URL, hand the string to `git clone` and do nothing else.
Parsing earns its place only for two separable jobs, and neither is a general URL
library.

The first is **computing the cache path**. Git needs no help cloning, but something has
to decide where the clone lands, and `<host>/<owner>/<repo>` requires decomposing the
URL. That is `urlsplit` plus a small regex for the SCP-like form.
The case row above is the concrete reason for sanitizing segments rather than a generic
tidiness argument: `PALLETS/FLASK` and `pallets/flask` are the same repository on
GitHub, so without lowercasing the cache would hold two entries for one repo.

The second is **surviving a paste from the address bar**, and it decomposes further by
value. Stripping the query and fragment is one line and fixes the most likely paste
failure, since GitHub’s address bar routinely carries `?tab=readme-ov-file`. Stripping
`/tree/<ref>/<path>` and `/blob/<ref>/<file>` is a separate increment whose payoff is
the deep link itself — landing on the file the user was looking at — rather than the
ability to clone at all.
The equivalents are `/-/tree/<ref>/<path>` on GitLab, where the `/-/` sentinel bounds an
arbitrarily nested group namespace, and `/src/branch/<branch>/<path>` on Codeberg,
Gitea, and Forgejo. A bare `owner/repo` slug is a third, optional increment, and it is
genuinely ambiguous with a real relative directory, so it should resolve to the local
path whenever one exists and only be treated as a remote when no such path exists,
printing what it resolved to.

Given that split, **no third-party URL library is warranted** — not primarily because of
supply-chain policy, but because once the deep-link strip is factored out there is
nothing left for a library to do that `urlsplit` does not already do.
The policy points the same way, and the candidates are poor regardless: `giturlparse`,
the best-maintained one, does not split ref from path at all (`…/tree/main/src/pkg`
yields `branch='main/src/pkg'`, an open issue since 2023 and intentional in the code)
and has no Gitea or Forgejo platform, so Codeberg URLs fall through to the GitLab regex
and silently produce the wrong owner and repo.
`git-url-parse` carries an unfixed ReDoS advisory (CVE-2023-32758) and last released in
2019\. And `parse-git-url`, published 2026-06-04, is a single unattributed release with
no author and the summary `"Add your description here"` reviving the name of the CVE’d
package — an automatic reject under the 14-day cool-off policy, worth flagging in case
anyone proposes it. For the SCP-like form, pip’s `_internal/vcs/git.py` is the
implementation to copy: linear-time, no ReDoS surface, and it correctly rejects Windows
drive letters.

One ambiguity is genuinely unresolvable at parse time: in `/tree/archive/esm/lib`, only
the server’s ref list decides whether the branch is `archive` or `archive/esm`. GitHub’s
own `gh` refuses to guess, erroring on more than two path segments and only ever
constructing deep links.
This design has a better option available — parse to an undecided form and resolve it
*after* cloning, offline, with `git show-ref`, taking the longest ref that prefixes the
string. Cloning first and disambiguating second is a real advantage of keeping a local
repository. Worth documenting one non-goal: `url.<base>.insteadOf` rewriting happens
inside Git before URL resolution, so the effective URL cannot be reproduced without
reading the user’s gitconfig, which affects cache-key correctness for users who rewrite
`https://` to `ssh://`.

For the skill, this is one routing line — “browse a repo the machine does not have: pass
the URL directly” — because the skill deliberately defers to `--help` as the source of
truth for arguments rather than restating the CLI. That is the whole agent-facing
surface: an agent asked to look at an unfamiliar repo runs one command and gets both a
served tree and a real clone on disk that it can also grep.

## Key Insights

**The fastest clone is the wrong clone.** `--depth=1` wins every clone benchmark and
loses the feature. The useful metric is time-to-first-render followed by
time-to-full-capability, and on that metric blobless-plus-backfill beats both full and
shallow: it renders 2.3–6.6x sooner than a full clone and, unlike shallow, arrives at a
complete repository without a 90-second repair step.

**This feature’s competition is a keystroke, not an app.** GitHub Desktop cannot browse
files at all, so it is not the bar.
github.dev is, and it is zero-install and instant.
Beating it requires leaning on what an API-backed viewer structurally cannot do: work
offline, ignore the 350 KiB and default-branch-only limits, need no login, and leave a
real repository on disk that history browsing, grep, and agents can all use.

**The agent use case is the one with no incumbent.** Humans have github.dev.
Agents currently choose between flatten-to-text tools that blow the context window on a
medium-sized repo and MCP servers that answer questions rather than provide source.
The `tbd checkout-third-party-repo` shortcut shows the workflow being hand-rolled.
A cached clone plus a served tree gives an agent both bulk access and selective reading.

**The feature is smaller than it looks, because Git already does the hard part.** Git
accepts `https://github.com/owner/repo` and the SCP-like form directly, so the baseline
is “hand the string to `git clone`.” What remains is deriving a cache path and stripping
the decorations a browser adds — query strings, fragments, and `/tree/<ref>/<path>`
segments.
Each is independently useful and independently shippable, which means a working
end-to-end version needs far less than a URL-parsing layer.

**Time-to-first-render is a design constraint the codebase already respects.** The
inventory walker streams entries so `/api/tree` answers from a partial index
immediately. Blobless-then-backfill is the same principle applied one layer down, and it
composes: the walker can begin indexing while blobs are still arriving.

## Comparison Matrix

| Criterion | Full clone | Blobless + backfill | Shallow (`--depth=1`) | Treeless | github.dev |
| --- | --- | --- | --- | --- | --- |
| Time to first render (django) | 108.9 s | **16.5 s** | 4.6 s | — | instant |
| Time to full history | 108.9 s | 115.8 s (backgrounded) | 94.6 s (+unshallow) | — | n/a |
| `git blame` works | yes | yes, after backfill | **wrong, exits 0** | **no** | via API |
| Browsing HEAD offline | yes | yes | yes | yes | **no** |
| Full history offline | yes | after backfill | **no** | **no** | **no** |
| Disk, django | 294 MB | 275 MB | 14 MB | — | 0 |
| All branches | yes | yes | **no** | yes | yes |

## Options Considered

### Option A: Blobless clone, background backfill, persistent cache *(recommended)*

**Description:** `metab <url>` clones with `--filter=blob:none` into
`~/.metabrowser/cache/repos/<host>/<owner>/<repo>`, serves as soon as the checkout
exists, and runs `git backfill` in the background.
The cache persists and is purged by an explicit command.

**Pros:**

- Best time-to-first-render among strategies that preserve history.
- Ends in a complete repository, so history browsing needs no URL-specific work.
- Reuses the Git subprocess adapter discipline the diff research already specifies.

**Cons:**

- Requires Git 2.49+ for `backfill`, which is recent and stamped experimental; needs a
  fallback path.
- Costs *more* total work than a full clone, so the backgrounding is load-bearing rather
  than an optimization.
- Background work introduces a state the UI must represent honestly.
- Partial clone has long network tails when connectivity is poor.

### Option B: Shallow clone, deepen on demand

**Description:** `--depth=1 --single-branch` for the fastest possible open; run
`git fetch --unshallow` only when the user opens a history view.

**Pros:**

- Fastest first render and by far the smallest disk footprint.
- Simple, and works on every Git version in circulation.

**Cons:**

- `git blame` exits 0 with a wrong answer before the deepen step, so a history UI built
  on it would display fabricated attribution rather than an error.
- The deepen step measured 90 s on django, landing entirely in the user’s way at the
  moment they ask for history.
- Single-branch hides branches the user may want.

### Option C: Throwaway clone per invocation

**Description:** Clone to a temp directory, serve, delete on exit — the gitingest model.

**Pros:**

- No cache management, no purge policy, no stale state.

**Cons:**

- Re-clones on every open, which is the entire cost, every time.
- Discards the reusable-bytes advantage that distinguishes this from an API viewer.

### Eliminated Options

- **Treeless clone (`--filter=tree:0`):** eliminated by measurement — 36.5 s for a
  path-limited log and blame fails.
- **Content-hash cache layout:** eliminated because unreadable paths cost more than
  dedupe saves for repo-scale entries.
- **Central cache index:** eliminated in favor of per-repo sidecars, which avoid lock
  contention between concurrent invocations.
- **`ls-remote` freshness probe before fetching:** eliminated by measurement — the probe
  (0.68 s) costs more than the no-op fetch it was meant to avoid (0.45 s).
- **`transfer.fsckObjects=true`:** eliminated because it fails to clone mainstream
  repos, Flask included.
- **Suppressing global gitconfig for sandboxing:** eliminated because it breaks every
  private-repo clone, and on macOS breaks credentials outright.
- **A third-party URL-parsing dependency:** eliminated because Git already accepts plain
  repository URLs, leaving only cache-path derivation, which `urlsplit` covers.
  The candidates are also poor: the maintained one cannot split ref from path and
  mis-parses Codeberg, and the alternatives carry an unfixed ReDoS advisory or no
  attribution.

## Recommendations

Build Option A, staged, and gated behind the untrusted-content profile.

1. **Do not ship before `mb-vib1`** (capability set and `--untrusted` profile).
   Serving a stranger’s repository without it means rendering untrusted HTML in a
   same-origin tab.
2. **Clone blobless, serve early, backfill in the background,** with a fallback to full
   clone below Git 2.49, below the 2.26 floor, or when the remote refuses partial clone.
   Consider a size threshold below which a plain full clone is simply better.
3. **Harden the clone with `-c` flags, never by suppressing config:**
   `core.symlinks=false`, `core.hooksPath` pinned empty, `gc.auto=0`,
   `fetch.recurseSubmodules=false`, `protocol.allow=never` with explicit `https` and
   `ssh` allowances, and `--` before the URL. Leave `transfer.fsckObjects` at its
   default.
4. **Never let Git prompt.** `GIT_TERMINAL_PROMPT=0` plus neutralized askpass variables,
   `SSH_ASKPASS_REQUIRE=never`, `GCM_INTERACTIVE=never`, SSH `BatchMode=yes`,
   `stdin=DEVNULL`, and a wall-clock timeout.
5. **Use `<host>/<owner>/<repo>` under a cache root,** clone to a temp sibling inside
   that root, publish by rename, guard with `flock`, and write per-repo sidecar metadata
   beside — not inside — the repo directory.
6. **Fetch, never pull.** Serve cached state immediately, background the fetch, show
   last-fetched age, and never auto-advance the checkout.
7. **Purge by explicit command,** size-capped LRU with a generous age sweep, `--dry-run`
   on every destructive path, and a `CACHEDIR.TAG` at the cache root.
8. **Pass plain URLs straight to Git and add parsing only where it pays.** Strip query
   and fragment, derive the cache path with `urlsplit` plus a small SCP-form regex, and
   lowercase path segments so one repo cannot occupy two cache entries.
   Treat deep-link stripping and `owner/repo` shorthand as separate later increments,
   resolving the ref/path split after cloning with `git show-ref`.
9. **Add one routing line to the skill** so an agent asked to look at a repo it does not
   have opens it directly.

## Next Steps

- [ ] Confirm the proposed Git floor of 2.26 against the platforms this project
  supports.
- [ ] Validate the purge defaults (10 GiB cap, 90-day sweep) against real cache growth.
- [ ] Decide whether a repo-size threshold should select full clone over blobless.
- [ ] Write the plan spec and file the implementation beads, sequenced after `mb-vib1`.

## Methodology

Clone and history benchmarks were run locally on macOS with Git 2.50.1 against
`pallets/flask` and `django/django`, timing `git clone`, `git backfill`,
`git fetch --unshallow`, `git log`, `git blame`, and `git show` with `/usr/bin/time`.
Each figure is a single sample; two `flask` blobless clones differed by nearly 2x (2.8 s
and 5.3 s), so clone times should be read as ratios.
Disk figures are `du -sm`. The hooks finding was verified by listing `.git/hooks` in a
fresh clone.

Findings were produced by two independent passes — one on the tool landscape, one on Git
mechanics — plus direct measurement here, with the passes cross-checked against each
other. Where they disagreed, measurement won: the landscape pass initially recommended
`--depth=1`, which the capability tests disqualified.
Several behavioral claims come from the mechanics pass rather than from runs in this
session, notably the depth-1 blame attribution defect, the 401-versus-404 distinction
over the git protocol, the `transfer.fsckObjects` clone failure, and the
`core.symlinks=false` mitigation; each was reported as directly tested, and the two that
matter most to the recommendation (shallow blame and treeless history) agree with the
independent measurements above.

The tool survey drew on repository metadata pulled from the GitHub API on 2026-08-11
plus official documentation.
Claims not confirmed, flagged rather than relied on: whether Sourcegraph’s free local
app was formally discontinued; a `uithub.com` request returning HTTP 401 that may be
network-specific; GitHub’s unauthenticated git-clone rate limit, for which no official
figure exists (the widely-cited 60/hour is the REST number and does not cover git
operations); and Windows-specific behavior throughout, which is documentation-only.
None affects the recommendation.

One item is unresolved rather than merely unverified: whether lenient fsck
(`fsck.<msgid>=warn`) can be made to work on the clone path.
The overrides did not take effect in testing.
It is currently moot, since the recommendation is to leave fsck at its default, but it
would need answering before anyone enables object verification.

## References

- [ghq](https://github.com/x-motemen/ghq) — the cache-layout convention this follows
- [klaus](https://github.com/jonashaag/klaus) and
  [git instaweb](https://git-scm.com/docs/git-instaweb) — prior art for local repo
  serving
- [gitingest](https://github.com/coderamp-labs/gitingest) and
  [Repomix](https://github.com/yamadashy/repomix) — URL-to-text, throwaway clones
- [desktop/desktop](https://github.com/desktop/desktop) — GitHub Desktop
- [github.dev docs](https://docs.github.com/en/codespaces/the-githubdev-web-based-editor)
- [GitHub code search limits](https://docs.github.com/en/search-github/github-code-search/using-github-code-search)
- [Get up to speed with partial clone and shallow clone](https://github.blog/open-source/git/get-up-to-speed-with-partial-clone-and-shallow-clone/)
- [git sparse-checkout](https://git-scm.com/docs/git-sparse-checkout)
- `research-2026-07-17-web-diff-viewer-architecture.md` — the Git subprocess adapter
  discipline this reuses

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
