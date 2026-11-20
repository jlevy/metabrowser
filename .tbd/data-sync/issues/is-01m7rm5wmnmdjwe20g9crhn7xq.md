---
type: is
id: is-01m7rm5wmnmdjwe20g9crhn7xq
title: "Flake: test_checkout_ref_selector_chrome loses its page (Inspected target navigated or closed)"
kind: bug
status: open
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01m2gb3gpn7vcsw0as4xa243tg
created_at: 2026-11-19T00:44:18.963Z
updated_at: 2026-11-20T17:19:40.002Z
---
chrome (3.13, 3/4) on jlevy/metabrowser#568, job 135237263900: tests/test_checkout_ref_selector_chrome.py:103 failed with 'Runtime.evaluate: Inspected target navigated or closed' from tests/dom/chrome-session.mjs:330. A different failure than mb-bio7 (closed). The change under test touched no browser code.
