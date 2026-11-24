---
type: is
id: is-01m85d3c7tk76nr00chvnqcjkc
title: Measure whether macOS purgeable space makes the first-clone free-space check refuse what fits
kind: task
status: open
priority: 3
version: 1
labels: []
dependencies: []
parent_id: is-01m6f3n89kn7ztmfhrzswxnsgz
created_at: 2026-11-23T23:50:44.218Z
updated_at: 2026-11-23T23:50:44.218Z
---
From review A finding A6 (Low, uncertain) of https://github.com/jlevy/metabrowser/pull/768 (https://github.com/jlevy/metabrowser/pull/768#pullrequestreview-6031209981).

Since PR 768 the free space shutil.disk_usage reports for the cache's volume (volume_free_bytes in src/metabrowser/cache/free_space.py) refuses a first clone instead of only warning in metab --doctor. On macOS APFS, statvfs's free count leaves out purgeable space (local snapshots, optimized iCloud storage) that macOS frees on demand, so a clone that would fit may be refused with a free figure that contradicts Finder's Available. Not measurable on Linux.

Check to run on a Mac with purgeable space: compare 'df -k ~/Library/Caches' (Avail) with 'diskutil info /' (Container Free Space and purgeable figures) and Finder's Available, and with uv run python -c 'import shutil, pathlib; print(shutil.disk_usage(pathlib.Path.home() / "Library/Caches").free)'. If the gap is real and common, read the important-usage capacity (NSURLVolumeAvailableCapacityForImportantUsageKey) on macOS, or say in the refusal and in Large Repositories (docs/reviewing-pull-requests.md) that the figure leaves out purgeable space. Otherwise record the measurement and close.
