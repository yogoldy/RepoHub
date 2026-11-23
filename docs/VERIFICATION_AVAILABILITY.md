# Verification availability and repair policy

An inability to read a stored archive is not proof that its bytes are corrupt.
RepoHub distinguishes verification I/O failures from checksum or archive-format
failures before deciding whether to construct a replacement.

When existing verification raises `OSError`, the helper preserves the current archive,
reports the attempt as failed/deferred, and records `verification_deferred`. It waits
for verification to succeed on a later attempt. This conservative policy also defers
a changed source when the prior archive cannot currently be verified.

The diagnostic event includes run and repository references, a reference to the
previous archive, stage, POSIX error code, exception class and the archive's observed
dataless flag when available. Unsupported flag information is recorded as unknown.
Raw exception prose and file contents are excluded. The local diagnostic reader
includes these events in its lifecycle timeline.

Checksum and archive-format failures still permit replacement from the intact source.
Replacement creation, verification, publication and configured upload-gated retention
continue through the existing lifecycle.

Synthetic regression coverage in `tests/test_scoped_backups.py` verifies that an
unavailable unchanged archive is preserved, diagnostics exclude exception prose,
recovery reuses the unchanged archive, and a changed source receives its replacement
once verification becomes available. The existing corruption-repair checks remain
part of the suite. Concrete repository inputs and real diagnostic case reports belong
in private local storage, outside Git.
