---
type: is
id: is-01m87spm6xvwwr9gh2cs1mbh39
title: Pin /raw media types instead of the host's mimetypes database
kind: bug
status: open
priority: 3
version: 2
spec_path: docs/project/architecture/arch-threat-model.md
labels:
  - security
dependencies: []
parent_id: is-01m8898kcprj50strs0xfshvjn
created_at: 2026-11-24T22:09:26.748Z
updated_at: 2026-11-25T02:46:46.433Z
---
Threat model T2. raw_file and the pin raw route type a file by mimetypes.guess_type, which reads the host's mime.types files; nothing pins or overrides it. A host database can change what a name is served as. Use a fixed table for the types that matter (html, svg, pdf, images, script types) or mimetypes.MimeTypes(strict, files=[]) and pin it in tests/test_content_trust.py.
