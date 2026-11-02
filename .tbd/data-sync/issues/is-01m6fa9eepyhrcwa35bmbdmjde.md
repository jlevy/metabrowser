---
type: is
id: is-01m6fa9eepyhrcwa35bmbdmjde
title: A .env that is not text stopped metab with a traceback in every mode
kind: bug
status: closed
priority: 1
version: 2
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-02T23:42:38.037Z
updated_at: 2026-11-02T23:42:38.644Z
closed_at: 2026-11-02T23:42:38.643Z
close_reason: Fixed in 9430e3ac, on PR 280, with a CHANGELOG entry.
resolution: null
duplicate_of: null
---
dotenv_values raises UnicodeDecodeError on a non-text .env, and the chain walks up from the working directory, so a browsed repository could stop the command. v0.11.0 did the same. Fixed in 9430e3ac: the file is skipped with one warning. Test: test_a_file_that_is_not_text_does_not_stop_the_command, proved failing without the fix.
