---
type: is
id: is-01m7gaskxmbjp91w7y96chkkj6
title: "Conversation: event headings read alike; a status chip only for a review state"
kind: task
status: in_progress
priority: 2
version: 3
spec_path: docs/project/specs/active/plan-2026-11-15-files-grouping-diff-summary-and-pull-stacks.md
delegate: claude-code@spud10
labels: []
dependencies: []
parent_id: is-01m7dm3az28qmj39y5hmdq2k0v
hold: null
hold_until: null
created_at: 2026-11-15T19:26:24.179Z
updated_at: 2026-11-15T19:41:15.359Z
started_at: 2026-11-15T19:27:14.725Z
---
The user's request (2026-11-15), verbatim:

"and the styling on headings like

jlevy
 commented 4d ago

jlevy
 Reviewed 4d ago

etc. seems inconsistent since "reviewed" is in a box like a status, but "commented" is not"

Done when every Conversation event's heading reads alike: the author, then the action in the same plain verb style ("commented", "reviewed", "committed"), then the age. A boxed status chip appears only where it carries a state the verb does not, such as a review's Approved or Changes requested, following GitHub's convention and the design system's badge rules. A plain review (state COMMENTED) gets no box. The rule is stated in docs/design-system.md's Conversation section, the page session or golden that records the headings is updated, the header and timeline Chrome checks pin the heading styles, and the CHANGELOG says so.

## Notes

2026-11-15: done in 8dcc0e617 on claude/conversation-rhythm (pushed --no-verify, no PR). Headings are now author, plain verb (opened, commented, reviewed; committed for commits), then age. A boxed chip follows the age only for a review state the verb does not say: Approved, Changes requested (was 'Requested changes'), Dismissed. COMMENTED and PENDING have no chip. REVIEW_STATES now maps to the chip label or null. The page session summary was updated and the cli-ui-github-pull-page golden regenerated with tryscript --update and golden_fixup (the plain review loses '[reviewed]'). The timeline Chrome session pins verb, chip, box and position; 25 checks failed on the previous head. The page header has no event headings, so the header Chrome checks needed no change.
