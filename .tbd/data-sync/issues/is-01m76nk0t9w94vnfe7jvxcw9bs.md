---
type: is
id: is-01m76nk0t9w94vnfe7jvxcw9bs
title: "PR #341: SpawnedProcess misses an exit when NOTE_EXIT arrives before the child is waitable"
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m76mgk23q075j4w3wjjg27a0
created_at: 2026-11-12T01:22:38.024Z
updated_at: 2026-11-12T01:31:25.016Z
closed_at: 2026-11-12T01:31:25.015Z
close_reason: "fixed in 685fe982 (pushed, head 358cebd5): the NOTE_EXIT handler waits for the child to become waitable; everyExitIsObservedWhileManyChildrenExit failed 2/3 before, passed 6/6 after. Listed in https://github.com/jlevy/metabrowser/pull/341#issuecomment-6811709019"
resolution: null
duplicate_of: null
---
Found while reproducing review D finding D1 on PR #341 (https://github.com/jlevy/metabrowser/pull/341); not a review finding. apps/macos/Sources/ShellCore/Supervision/ServerProcess.swift:210-221 (at bc6477a): the NOTE_EXIT event handler reads the exit with waitid(WEXITED|WNOHANG|WNOWAIT) and returns if the child is not yet waitable. Instrumented stress runs of 7,200 concurrent /usr/bin/true children missed 5, 9, and 11 exits: in every miss the event handler ran and found the child not yet waitable, the initial probe had run before the exit, and the child was an unreaped zombie seconds later. waitForExit() then never returns: a crash after ready goes unnoticed, a stop waits out its grace and kill wait, and the zombie is never reaped. Fix: the event handler waits (no WNOHANG) for the child to become waitable.
