# Runtime Example Data

This directory is reserved for sanitized runtime examples that are safe to keep
in Git.

Do not copy live files from `runtime/` or `data/` directly. Before adding an
example, replace device IDs, package names, LAN addresses, tokens, webhook
secrets, APK names, logs, and organization-specific report content with stable
fake values.

Use `tests/fixtures/` when the data is needed by automated tests. Use this
directory only for human-readable layout examples or documentation snippets.
