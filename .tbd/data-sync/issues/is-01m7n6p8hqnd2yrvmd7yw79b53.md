---
type: is
id: is-01m7n6p8hqnd2yrvmd7yw79b53
title: Order the pull, stacks and labels refresh answers as pull-files-refresh and pulls-refresh do
kind: bug
status: open
priority: 3
version: 2
labels: []
dependencies: []
parent_id: is-01m7wys8y3epj61gncgjakhsd0
created_at: 2026-11-17T16:50:52.086Z
updated_at: 2026-11-20T17:10:47.925Z
---
From review A on jlevy/metabrowser#513 (finding A5, Low).

PR #513 orders the answer of two refresh routes: pull-files-refresh and pulls-refresh read what the answer's envelope is built from before the start, so a job this request starts cannot show its own outcome in the 202 that starts it (mb-kq72, mb-7pu0), and read again after the start when no job runs, so an answer that says nothing is refreshing is read after nothing was, as the GET routes read (review A1).

Three refresh routes still read their answer only after the start, in src/metabrowser/builtin_plugins/github/sidekick.py:

- pull-refresh (pull_refresh_handler): pull_answer after start_refresh, and after the wait for the core when the body asks for it.
- stacks-refresh (stacks_refresh_handler): stack_envelope after start_refresh.
- labels-refresh (labels_refresh_handler): label_envelope after start_refresh.

The read retry in src/metabrowser/cache/atomic.py (mb-kq72) already removes their torn-read variant. A job that ends at once, as one with no gh does, can still show its own outcome in the answer that starts it. No flake has been seen on these three (mb-7pu0 notes).

Move each to the order the two routes keep, with the two tests those routes have: a job that writes its stamp as it starts (tests/test_cli_github_pulls_golden.py::test_a_started_refresh_answers_with_the_list_as_its_job_found_it) and another request's job that ends during the read (::test_an_answer_that_starts_no_job_is_read_after_the_one_that_ended). pull-refresh's wait for the core reads after the job has run on purpose; decide its order with that in view.
