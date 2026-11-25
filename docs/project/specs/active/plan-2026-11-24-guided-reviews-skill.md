# Feature: Guided Reviews in the Agent Skill

**Date:** 2026-11-24 (last updated 2026-11-24)

**Author:** Joshua Levy (github.com/jlevy) with LLM assistance

**Status:** Phase 1 in progress; bead `mb-uqwl`. The skill’s **Write a Guided Review**
section shipped in #785, with the block skeleton and the recipes to publish, confirm,
and refresh a guide; the check route and its recipes, the handoff line, and the
person-facing guide remain.
[Whole-Stack Review](plan-2026-11-24-stack-review.md) plans the section’s later changes:
shorter guides, Markdown notes, more reference kinds, and a stack’s guide
([What Other Plans Change](#what-other-plans-change)).

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
- **YAML.** An unquoted title such as `Evidence: the route` makes the whole block
  invalid YAML, and a folded note joins a list’s lines into one.
- **Checking before publishing.** The only check is the `guided-review` route, which
  reads the cached description, so a mistake is found after the description carries it.
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
`/api/plugin/github/guided-review-check` reads a draft guide from a file in the served
checkout, by a repository-relative path through the safe-path helpers and a bounded
read, and answers:

- the parse result, with the same refusal reasons the `guided-review` route gives
  (invalid YAML, another contract, a field that fails the schema);
- whether `merge_base` is the merge base of `head`, and whether `head` is the pull
  request’s current head when a pull request number is given;
- for each step, each reference’s state as the page would draw it (`ready`, or why not),
  from the local repository’s objects;
- the changed files no step cites, as information: a concise guide leaves files out on
  purpose, so the skill does not ask for the list to be empty.

It reads only local Git objects and the cached record, so it costs no GitHub request.
It arrives with its parity row and a golden on the GitHub stand-in
(`tests/github_pull_fixture.py` already builds guided records).

### The Skill

`skills/metabrowser/SKILL.md` gains a route in **Route the Task** (“opening or updating
a pull request: write or refresh its guided review”) and a section, **Write a Guided
Review**, with:

- when to write one: every pull request the agent opens, a one-file change included,
  unless the user says not to; a small change merges concerns but keeps its testing
  step, so even a one-file guide keeps what CI proves apart from what a person checks;
- the pins, computed with `git merge-base`, and why a stacked layer’s base is its base
  branch;
- what a guide covers, each concern a step or a run of steps of its own, in this order:
  keystone decisions; key documents; each area of change, in dependency or execution
  order; ambiguity and uncertainty a person should decide; testing and QA, split three
  ways into what automated checks cover, what the agent checked itself, and what still
  needs a person; and future work and further planning;
- a minimal block skeleton and the YAML rules (quote a title or note holding `: ` or
  ` #`, and write a note with a list as a literal block);
- the check, then `gh pr edit <n> --body-file`, replacing an existing block rather than
  adding a second;
- confirming it with the `guided-review` route, after refreshing the record it reads:
  `state` is `ready` and every reference is `ready`, step by step;
- refreshing after each push: read the stale answer, recheck only the steps it lists,
  move the pins, check again, and publish.

The skeleton is held to `parse_guide` by `tests/test_skill_commands.py`, so an agent can
write a guide from the section alone.
The format’s limits and full rules stay in
[Reviewing Pull Requests](../../../reviewing-pull-requests.md#guided-review); the skill
names the limits and links there rather than restating their values.
If the skill grows past a routing layer, the format summary moves to
`skills/metabrowser/references/guided-reviews.md`, once the skill installer is confirmed
to copy a skill’s subfolders.

Steps per concern make a guide the reviewer’s agenda rather than a tour of the diff: a
reviewer can stop at a keystone decision they reject, go straight to what is uncertain,
and tick off the person-only checks, and an agent’s claims about testing are kept apart
from what CI proves.
The owner set these concerns on 2026-11-24 after walking the first guides.

### What Other Plans Change

The section shipped asking that every changed file belong to some step.
The owner dropped that rule on 2026-11-24: it forces a file inventory, which the Changes
tab already is, and the coverage gap in [Background](#background) is answered by the
check’s list, not by a longer guide.
The skill’s later changes belong to the plans that make them:

| Section of the skill | Change | Plan |
| --- | --- | --- |
| **Write a Guided Review**: what a guide covers, and the refresh recipe | Concise guides: a summary of the end state opening the description, about eight steps or fewer, notes of one to three sentences, no every-file rule, a stacked layer’s place in one line (`mb-mxcm`) | [Whole-Stack Review](plan-2026-11-24-stack-review.md#phase-0-concise-guides-mb-mxcm-mb-kkib) |
| **Write a Guided Review**: the paragraph on plain text | Notes are Markdown, rendered inert; titles stay plain (`mb-kkib`) | The same phase |
| **Write a Guided Review**: the groups and the rationale step | On #807 (`mb-szxu`) | [Guided Review Groups](plan-2026-11-24-guided-review-groups.md) |
| **Write the Block**: the reference rules | A pull request, a file as a pull request changes it, and a commit (`mb-9dmv`) | [Whole-Stack Review](plan-2026-11-24-stack-review.md#phase-2-reference-kinds-mb-9dmv) |
| **Route the Task**, and a new **Write a Stack Guide** | A stack’s guide in a `stack-review` block, with its template and recipe (`mb-ri96`) | [Whole-Stack Review](plan-2026-11-24-stack-review.md#phase-3-the-stack-guide-mb-ri96) |

This plan keeps the check, its recipes, the person-facing guide, and the handoff line.

### This Repository’s Handoff

`AGENTS.md`’s handoff list gains “add or refresh the pull request’s guided review”, with
its reason: reviewers here read through Metabrowser, and a guide sets their order.
`tbd shortcut create-or-update-pr-simple` is first-party upstream; if it should name the
guide for every project, that change goes to tbd, not a local patch.

### Naming and the Format

The feature is **guided reviews**: the tab is **Guided Review**, and prose, the
changelog, the skill, and pull request titles use that name.
The identifiers follow it, renamed in #677 before any release reads them: the
description’s `guided-review` fence, the `github/guided-review` route,
`guided_review.py`, and `guided-review.js`.

A guided review wraps the general collection format
(`metabrowser.collection:Collection/v1`), which is not tied to pull requests or to
review ([Collection Format](../../architecture/arch-collection-format.md)). The skill
teaches guided reviews as the first use of that format: what belongs to the format
(items, notes, references) is written so that a later carrier, a review of a commit or a
branch comparison, or a reading list in a repository file, reuses it, and only what the
pull-request carrier adds (the pins, diff ranges, excerpt budgets, staleness) is
specific to the section.
The check is the guided-review carrier’s, as each carrier keeps its own route.

## Implementation Plan

### Phase 1: Check, Skill, and Handoff

- [ ] Add `/api/plugin/github/guided-review-check` with its parity row, the route map
  entry, and a golden on the GitHub stand-in.
- [x] Add **Write a Guided Review** to the skill, with the route in **Route the Task**
  and in the skill’s description: what a guide covers, the pins, the block skeleton and
  its YAML rules, publishing with `gh pr edit`, and confirming and refreshing it with
  the route after refreshing the record.
- [x] Hold the section’s recipes to the golden, its states and keys to
  `guided_review.py`, and its skeleton to `parse_guide`, each check proven by a
  mutation.
- [ ] Once the check route exists, add its recipes to the section and to
  `tests/golden/cli-skill-recipes.tryscript.md`.
- [ ] Repeat the person-facing part in `docs/working-with-agents.md` (“ask an agent to
  add a guided review”).
- [ ] Add the handoff line to `AGENTS.md`.
- [x] Changelog fragment.

## Testing Strategy

- The check’s golden covers a ready draft, each refusal, a range across a hunk boundary,
  a wrong merge base, a stale head, and uncited files, on the GitHub stand-in.
- `tests/test_skill_commands.py` already fails when the skill names a route `metab` does
  not register, and runs the skill’s recipes from the golden; the new recipes join it.
- A mutation of the new section (a wrong route name, a renamed state, a skeleton the
  page refuses) fails those checks, as each existing check is proven; once the check
  exists, a recipe that skips it must fail too.
- Dogfooding: the pull requests that implement this plan carry guides written by the
  skill’s own recipe.

## Rollout Plan

The check and the skill ship in the release after #677. The skill on `main` can name the
check before a release has it; the skill already says how to run a checkout’s `metab`
for an unreleased route.

## Open Questions

- Should the check take the draft as a path in the checkout, or as the pull request
  description file the agent will publish, so it also confirms there is exactly one
  block?
- Should the check also read a `stack-review` block, against the stack’s comparison,
  once [Whole-Stack Review](plan-2026-11-24-stack-review.md) builds one?

## References

- [Reviewing Pull Requests: Guided Review](../../../reviewing-pull-requests.md#guided-review)
- [The agent skill](../../../../skills/metabrowser/SKILL.md) and
  [Working With Agents](../../../working-with-agents.md)
- `src/metabrowser/builtin_plugins/github/guided_review.py` (`parse_guide`, `MAX_ITEMS`,
  `MAX_REFERENCES`)
- #677 (guided reviews) and #679 (the collection format’s research)
- [Whole-Stack Review](plan-2026-11-24-stack-review.md) and
  [Guided Review Groups](plan-2026-11-24-guided-review-groups.md)

<!-- This document follows common-doc-guidelines.md.
See github.com/jlevy/practical-prose and review guidelines before editing.
-->
