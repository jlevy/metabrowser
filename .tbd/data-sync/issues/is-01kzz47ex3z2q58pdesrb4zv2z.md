---
type: is
id: is-01kzz47ex3z2q58pdesrb4zv2z
title: "PR #35 review R2: Shift+Tab is dead inside Quick File"
kind: bug
status: closed
priority: 2
version: 2
labels: []
dependencies: []
parent_id: is-01kzz46ttyre78pjmkxynpfh3z
created_at: 2026-08-14T03:14:39.650Z
updated_at: 2026-08-14T03:32:02.094Z
closed_at: 2026-08-14T03:32:02.094Z
close_reason: "Fixed in 78ee53e: removed handleInputKeydown so the shared modal trap owns Tab in both directions."
---
handleInputKeydown in src/metabrowser/static/search_palette.js:607-612 preventDefaults every Tab and refocuses the input. Backward Tab matches no branch in handleDialogKeydown (overlay_layer.js:343-350), so focus never reaches the Close button. The covering test passes only because the DOM stub does not bubble to ancestors.
