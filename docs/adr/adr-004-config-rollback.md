# ADR-004: Automatic backup before profile mutation

**Status:** Accepted
**Date:** 2026-07-11

## Context

Config profiles store production system settings. A bad tweak that causes
instability needs quick rollback. Without backups, users must manually recreate
previous configs or reinstall drivers.

## Decision

Every `ConfigManager.save()` call automatically creates a timestamped backup of
the existing profile before overwriting. Backups are stored in a dedicated
directory with the naming pattern `{profile_name}_{YYYYMMDD_HHMMSS}.json`.

Rollback is explicit via `ConfigManager.rollback(name, [timestamp])`:
- Without timestamp: restores the most recent non-deleted backup
- With timestamp: restores that specific backup version

Cleanup: maximum 10 backups retained per profile. Oldest purged automatically.
Deleted profiles get a terminal backup with `_DELETED_` marker.

## Options Considered

1. **No built-in backups** — Users responsible for versioning
   - Pro: Zero complexity
   - Con: Data loss risk, poor UX
2. **Git-based versioning** — Use git for config history
   - Pro: Full git history, diffable
   - Con: Requires git, overkill for config files
3. **Timestamped file backups** — Chosen
   - Pro: Simple, no dependencies, works everywhere
   - Con: Some disk usage (mitigated by 10-file limit)

## Consequences

- Every save is a safe operation; users can experiment freely
- Backup directory grows linearly but capped at 10 files per profile
- Rollback preserves version number semantics
- Deleted profiles recoverable from terminal backup
