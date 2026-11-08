---
type: is
id: is-01m6wq6jdpw2gshn84zxcr8ewd
title: Reconcile superseded presentation claims in the unreleased changelog
kind: task
status: closed
priority: 1
version: 5
spec_path: docs/project/specs/active/plan-2026-09-23-v012-thin-mirror.md
delegate: codex@spud10
labels: []
dependencies: []
parent_id: is-01m5wdbsy6z6d95sgg03kwmm76
hold: null
hold_until: null
created_at: 2026-11-08T04:38:22.901Z
updated_at: 2026-11-08T06:38:44.635Z
started_at: 2026-11-08T05:21:36.599Z
closed_at: 2026-11-08T06:38:44.626Z
close_reason: Documentation PR332 merged at240da85cbb45b72defed0084aadc99ee0be234ed after pinned independent senior review, exacthead fullmakeverify4917 tests/9expectedskips/385goldenchecks, audits/distribution/installedsmokes and all9PRCIjobs. Landed fulltree equals gatede204ce9b5 and retains it asancestor. Current userguides/design/plans/QA/behaviorrecord reconciled; publishinginstructions targetapprovedfullSHA with existingtagpreflight. Separate release acceptance/publication remainsopen.
resolution: null
duplicate_of: null
---
Release evidence audit found CHANGELOG.md around1237 still promises the distracting 50 of1,183 files loaded counter removed by current production and the top0.12 notes. The same long unreleased section contains intermediate implementation claims such as Conversation fetching Files changed on idle and five-part refresh details, which need checking against final progressive cache/details design. After the currently frozen519c full gate/stack landing, refresh the final release documentation in one coherent pass: keep user-visible final delta from0.11, remove contradictory superseded wording, preserve material limits/intentional behavior changes, update exact final acceptance and link evidence. Do not edit the source mid-gate or represent this as an application regression. Complete before requesting release publication approval; track under existing release-docs/QA coordination.

## Notes

November7 final documentation branch checkpoint:16MDfiles now reconcile current ChecksURL/Changeslabels, stackpositions/actorink/leadingbrand/loading/lookahead, centralQA andactiveplanstatus pointers, exact519installed55file equality/apply/browser results, anddatedbehaviorchangeaddendumincludingbackgroundGitHubpreparationandkeyboardfallback. Independentinitial10file andadditional6file reviews identified2Low wordingfindings: preserveexternalGitHub Fileschangedlabel andqualifyMacCommandchordswithplain1/2/3 fallback; bothcorrected. PublicationR1trackedseparatelymb-3r01: fullapprovedRELEASE_COMMITtarget, existingtagpreflightrefusal, resulttagverification documented. Sourceapplication/dependenciesunchanged. Fullverifyrunning; finaldocslintandnormalcommithooks/push/CI/reviewpublicationstillrequired. Futurechooseritzyremainspausedwithoutimplementation.

Independent docs audit at519c identified eight concrete corrections for the final release-doc pass: command-line guide says /pull/N/checks refused although URLparser accepts; PRguide/changelog promise visible stack numbers instead of Layers+position/contextualnumber; guide/changelog saygray usernames instead of bold normaltextink; guide says ViewonGitHub usesstateicon instead of leadingbrand; changelogpromises removed50ofNcounter; idlecomparison prefetch overpromises no request despite deferredfiles; nearest-toponly wording omits lookahead/explicitjump; currentliteral Git/Fileschanged tablabels shouldbe Commits/Changes. Concurrentfivepart refresh andportablemetadatawarming claims matchproduction. No behavioral gap found. Apply afterfrozenstack gate/landing, thenrequiredformat/hygiene/docschecks andpublishreviewedfollow-up.
