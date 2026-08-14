---
type: is
id: is-01m014074qw2ph1mftxmtcj13p
title: Remove file-age markers and use text-only color
kind: bug
status: closed
priority: 1
version: 3
spec_path: docs/project/specs/active/plan-2026-07-20-folder-views-and-treemap-overview.md
labels:
  - browser
  - design-system
  - accessibility
dependencies: []
parent_id: is-01kxz2z9v1bbfcfmqstffkhvxp
created_at: 2026-08-14T21:49:11.190Z
updated_at: 2026-08-14T22:11:43.325Z
closed_at: 2026-08-14T22:11:43.324Z
close_reason: "Implemented and validated on PR #44: age is conveyed by accessible text-only OKLCH colors with markers removed, and Treemap pointer routing activates the deepest actionable full cell while preserving keyboard semantics. make verify and all GitHub CI checks pass."
---
Correction

File age must be encoded by the age text itself, without an adjacent dot, circuit, swatch, or other color marker anywhere in the interface. The marker added to preserve bright yellow on light surfaces is not part of the intended design. If a foreground is too light, darken and tune the foreground in OKLCH while preserving a clearly yellow hue and accessible contrast.

Implementation map

- src/metabrowser/static/styles.css, root and dark-theme file-age token families: simplify the shared age palette to text foreground and optional surface-fill tokens. Remove file-age accent, marker-size, and marker-gap tokens when no remaining non-marker use exists. Retune light-theme foreground lightness and chroma so each elapsed bucket is recognizably yellow-to-dark-neutral and meets WCAG AA on every supported surface; retain salmon text for Live and keep it distinct from destructive red.
- src/metabrowser/static/styles.css, shared .age-live and .age-* primitive: remove generated marker pseudo-elements, inline-flex marker spacing, and .file-age-marker styling. Keep only semantic foreground and weight selection. Remove the dot from .badge-live while retaining its Live foreground and subtle fill.
- src/metabrowser/static/filter_controls.js, renderMenu: stop emitting .file-age-marker markup for age options. Age rows receive the shared text class only; keep the fixed check column, label alignment, counts, focus, and selection behavior unchanged.
- src/metabrowser/static/app.js and plugin consumers: continue using only age-live and age bucket classes. Audit navigation rows, file and folder headers, recent-filter rows, Live badges, plugin labels, and Treemap-related age presentation to ensure none adds its own marker or compensating color literal.
- tests/test_file_age_palette.py: replace the foreground-plus-marker contract with text-only assertions. Check that every light and dark foreground is in gamut, meets WCAG AA on all supported surfaces, retains the intended Live salmon or elapsed yellow hue family, and decreases in chroma and prominence with age. Assert marker tokens, marker selectors, generated dots, and marker markup are absent.
- tests/test_browser_filter_ui.py and tests/dom/filter_controls_behavior.js: assert recent options use the shared age text classes with no marker element and preserve all current menu semantics.
- docs/design-system.md, File Age: define text color as the sole age hue signal, explain the accessible dark-yellow treatment on light surfaces, remove the marker-layer guidance, and retain centralized OKLCH maintenance rules.

Acceptance criteria

- No file age, date, recent-filter option, navigation row, header, plugin label, or Live badge displays an adjacent dot, circuit, marker, or swatch.
- The age text alone communicates the scale: Live is salmon; every elapsed age remains yellow or progressively darker and more neutral, without drifting pink or red.
- Light-theme age text is visibly yellow where appropriate and achieves at least 4.5:1 contrast on every surface where it is rendered; dark-theme text meets the same contrast floor.
- The semantic age classes and centralized tokens remain the only consumer API. Components and plugins do not introduce local corrections or literal colors.
- Automated palette and filter behavior coverage passes, make verify passes, and manual validation checks navigation, dropdown, headers, plugins, and Live state in light and dark themes.
