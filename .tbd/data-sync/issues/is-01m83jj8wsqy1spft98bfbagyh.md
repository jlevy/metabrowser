---
type: is
id: is-01m83jj8wsqy1spft98bfbagyh
title: "Untrusted-folder refusal test: a 0.2 s render deadline refuses a trivial real render at load ~340"
kind: bug
status: closed
priority: 3
version: 2
labels: []
dependencies: []
created_at: 2026-11-23T06:47:46.292Z
updated_at: 2026-11-23T06:56:40.416Z
closed_at: 2026-11-23T06:56:40.397Z
close_reason: "Fixed in #741: the page's-own-text render gets a 30 s deadline; the 0.2 s one was for the slow document and a heading render took 0.28 s at load 340."
resolution: null
duplicate_of: null
---
tests/test_inert_render_deadline.py::test_an_untrusted_folder_keeps_the_refusal_by_the_documents_text sets _RENDER_DEADLINE_S to 0.2 s and then expects the real child to render '# Sent' within it. At a load average of about 340 (2026-11-22, found while fixing mb-xmte) that render ran past the deadline: the log says 'Refused rendering slow.md (sha256:9d91da0e...) after 0.28 s: render_deadline' for the sent text, and the assertion 'sent.status_code == 200' failed with 422. Mechanism: the shortened deadline is a claim about a real KPress render on a freshly restarted child, and it does not hold under heavy load. Not caused by the start wait (both starts took 3.7 to 4.2 s, inside the old 5 s). A fix restores the default deadline for the sent text, or uses a document whose cost is seconds apart from the deadline in both directions.
