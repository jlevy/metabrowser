---
type: is
id: is-01m6j9vp3ekq73em88zct143h2
title: Restore visible branch-row focus before dragging the pane splitter
kind: bug
status: closed
priority: 2
version: 3
spec_path: docs/design-system.md
labels: []
dependencies: []
parent_id: is-01m6j5ce0pgcr3zhv1w349e6bk
created_at: 2026-11-04T03:32:50.413Z
updated_at: 2026-11-04T17:14:29.990Z
closed_at: 2026-11-04T17:14:29.990Z
close_reason: "Scoped implementation independently reviewed and tested; owning feature PRs are actually merged. Final main https://github.com/jlevy/metabrowser/commit/db52ec09cf839269da3a56fd396e44f3092995a9 includes account fix https://github.com/jlevy/metabrowser/pull/297 and documentation https://github.com/jlevy/metabrowser/pull/298, with final manual acceptance and per-issue qualifications checked. Individual source, test, review and merge evidence: ACTION-PLAN.json SHA-256 d0867a696ee055cc27911e83c4f70744b419a3ca4a7a1218f0eeaf419dc37589. Future scope and historical dependency relationships remain open or preserved as recorded."
resolution: null
duplicate_of: null
---
Independent actualChrome diagnostic at immutableb85 uses exactproductionCSS/SDK/initPaneResize and realTab+CDPsplitterdrag600->360px. Focus stays on unhidden tabindex0head-copy atx427.64–443.64 while metadataends347; elementFromPointfalse because clipped. This is strandedinvisiblefocus, not proven wrongvisiblehit. Windowresizecontrolhideslayer/restoresprimary; dispose0layers. Smallestcausalfix active documentpointerdownoutsidehost invokesexistinghide/restore/dispose lifecycle; no newobserverframework. Fixupstackinsixthsharedviewlayer, retain exactred/recheckprobe. Evidence final-sixth-acceptance/pane-drag-diagnostic.json.

## Notes

Working sixthSDKviews override5738a3c4 recheckedwithsameactualChromeTab+600->360splitterinput: layerhides, primaryfocusrestored,0stalecontrols/0retainedlayers. Otherassetsimmutableb85; exactsourcehashstablethroughprobe. Existinglatecaptioncontrolnonvacuousfocus retained0movement; noadditionalfinding. Finalcommittedpin/wheelrecheckpending.
