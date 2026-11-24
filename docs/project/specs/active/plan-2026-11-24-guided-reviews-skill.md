# Feature: Guided Reviews in the Agent Skill

**Date:** 2026-11-24 (last updated 2026-11-24)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Draft

## Overview

Guided reviews (#677) let a pull request’s description carry a guide: ordered review
steps, each a note on what to verify and the diff excerpts it is about, which the
**Guided Review** tab shows above the code.
Today an author writes a guide by hand from the format reference, and nothing checks it
until it is published.
This plan teaches the `metabrowser` agent skill to write, check, publish, and refresh a
guide whenever an agent opens or updates a pull request, and gives it a `metab` check to
run before publishing.

## Goals

- An agent with the skill installed adds a guided review to each pull request it opens
  and refreshes the guide on each push, without the format reference open beside it.
- An agent can check a draft guide against its comparison before the description carries
  it, with the same answers the page will give.
- The skill’s guide commands are held to the `metab` they run, as its other commands are
  (`tests/test_skill_commands.py`).
- This repository’s own pull requests carry guides, so the feature is used every day by
  the people building it.

## Non-Goals

- Writing the steps for the agent.
  Choosing an order and saying what to verify is the author’s judgment; the skill says
  how to make it, and the check says whether the result is well formed.
- Changing the guide format, `metabrowser.collection:Collection/v1`, beyond the naming
  decision below.
- Guides outside GitHub pull requests.
  The collection format is meant for reading lists and dashboards too, but those have
  their own plans.

## Background

Writing guides for #677 and the five newest pull requests in this repository by hand
showed what an agent gets wrong and what it needs:

- **Pins.** The guide pins `merge_base` and `head`. The merge base is
  `git merge-base origin/<base branch> <head>`, so for a stacked pull request it is the
  base layer’s branch, not `main`. Every push, including a merge of the base into the
  layer, makes the guide stale until its pins move.
- **Ranges.** A ranged reference must lie inside one hunk of the comparison’s diff, on
  the side it names. A range that crosses a hunk boundary is refused on the page, after
  publishing.
- **Coverage.** Nothing says which changed files no step cites.
  A guide written early in a pull request’s life silently drops the files added later;
  #677’s guide missed 34 of 58 until a script listed them.
- **YAML.** A title such as `Evidence: the route` is not valid YAML unquoted.
- **Checking before publishing.** The only check is the `guided-pr` route, which reads
  the cached description, so a mistake is found after the description carries it.
  A throwaway script (parse as `parse_guide` does, confirm the merge base, test each
  range against `git diff`, list uncited files) found every one of these before
  publishing, and is the model for the check below.
- **Refreshing.** A stale guide’s answer already lists the steps that cite a file
  changed since its pins, which is exactly what a refresh needs to recheck.

## Design

### Approach

Three parts, each small:

1. A **check** in `metab` that answers for a draft what the page would answer once
   published, without publishing.
2. A **section of the skill** that routes “open or update a pull request” to writing or
   refreshing a guide, with the recipe and the rules an author needs.
3. **This repository’s handoff** names the guide, so its own pull requests carry one.

### The Check

Prefer a route to a CLI mode (AGENTS.md, CLI and Functional UI Parity):
`/api/plugin/github/guided-pr-check` reads a draft guide from a file in the served
checkout, by a repository-relative path through the safe-path helpers and a bounded
read, and answers:

- the parse result, with the same refusal reasons the `guided-pr` route gives (invalid
  YAML, another contract, a field that fails the schema);
- whether `merge_base` is the merge base of `head`, and whether `head` is the pull
  request’s current head when a pull request number is given;
- for each step, each reference’s state as the page would draw it (`ready`, or why not),
  from the local repository’s objects;
- the changed files no step cites.

It reads only local Git objects and the cached record, so it costs no GitHub request.
It arrives with its parity row and a golden on the GitHub stand-in
(`tests/github_pull_fixture.py` already builds guided records).

### The Skill

`skills/metabrowser/SKILL.md` gains a route in **Route the Task** (“opening or updating
a pull request: write or refresh its guided review”) and a section, **Write a Guided
Review**, with:

- when to write one: every pull request the agent opens, unless the user says not to;
- the pins, computed with `git merge-base`, and why a stacked layer’s base is its base
  branch;
- how to choose and order steps: dependency or execution order, a note that says what to
  check, ranges for the lines that matter, a whole file for tests, goldens, and docs,
  and every changed file cited somewhere;
- the YAML shape and its traps (quote a title with a colon);
- the check, then `gh pr edit <n> --body-file`, replacing an existing block rather than
  adding a second;
- confirming it with the `guided-pr` route: `state` is `ready` and every reference is
  `ready`;
- refreshing after each push: read the stale answer, recheck only the steps it lists,
  move the pins, check again, and publish.

The format details stay in
[Reviewing Pull Requests](../../../reviewing-pull-requests.md#guided-review); the skill
links to it rather than restating it.
If the skill grows past a routing layer, the format summary moves to
`skills/metabrowser/references/guided-reviews.md`, once the skill installer is confirmed
to copy a skill’s subfolders.

### This Repository’s Handoff

`AGENTS.md`’s handoff list gains “add or refresh the pull request’s guided review”, with
its reason: reviewers here read through Metabrowser, and a guide sets their order.
`tbd shortcut create-or-update-pr-simple` is first-party upstream; if it should name the
guide for every project, that change goes to tbd, not a local patch.

### Naming

The feature is **guided reviews**: the tab is **Guided Review**, and prose, the
changelog, the skill, and pull request titles use that name, not “guided PR”. The
identifiers still say `guided-pr`: the description’s fence, the `github/guided-pr`
route, `guided_pr.py`, and `guided-pr.js`. The fence is the one that matters: once a
release reads it, every description that carries a guide is released data that cannot
update with the code, and renaming it then needs a compatibility layer.
Before the first release it is a rename in one commit.

## Implementation Plan

### Phase 1: Check, Skill, and Handoff

- [ ] Decide the identifiers’ name (Open Questions), and if they change, rename them in
  #677 before it merges.
- [ ] Add `/api/plugin/github/guided-pr-check` with its parity row, the route map entry,
  and a golden on the GitHub stand-in.
- [ ] Add **Write a Guided Review** to the skill, with the route in **Route the Task**,
  and its recipes to `tests/golden/cli-skill-recipes.tryscript.md`.
- [ ] Repeat the person-facing part in `docs/working-with-agents.md` (“ask an agent to
  add a guided review”).
- [ ] Add the handoff line to `AGENTS.md`.
- [ ] Changelog fragment.

## Testing Strategy

- The check’s golden covers a ready draft, each refusal, a range across a hunk boundary,
  a wrong merge base, a stale head, and uncited files, on the GitHub stand-in.
- `tests/test_skill_commands.py` already fails when the skill names a route `metab` does
  not register, and runs the skill’s recipes from the golden; the new recipes join it.
- A mutation of the new section (a wrong route name, a recipe that skips the check) must
  fail those checks, as each existing check is proven.
- Dogfooding: the pull requests that implement this plan carry guides written by the
  skill’s own recipe.

## Rollout Plan

The check and the skill ship in the release after #677. The skill on `main` can name the
check before a release has it; the skill already says how to run a checkout’s `metab`
for an unreleased route.

## Open Questions

- Rename the identifiers to match the feature’s name before the first release: the fence
  to `guided-review`, the route to `github/guided-review`, and the modules to match?
  Recommended, for the fence’s sake (Naming above).
- Should the check take the draft as a path in the checkout, or as the pull request
  description file the agent will publish, so it also confirms there is exactly one
  block?
- Should a pull request with only a few changed files skip the guide?
  The description alone may be the review for a one-file change.

## References

- [Reviewing Pull Requests: Guided Review](../../../reviewing-pull-requests.md#guided-review)
- [The agent skill](../../../../skills/metabrowser/SKILL.md) and
  [Working With Agents](../../../working-with-agents.md)
- `src/metabrowser/builtin_plugins/github/guided_pr.py` (`parse_guide`, `MAX_ITEMS`,
  `MAX_REFERENCES`)
- #677 (guided reviews) and #679 (the collection format’s research)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
