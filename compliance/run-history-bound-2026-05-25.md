---
title: Bound in-memory _run_history (WA-2026-05-25-01)
tsc: CC4.1, CC7.1
owner: Kevin Armstrong
last-reviewed: 2026-05-25
---

# Bound in-memory `_run_history` and `_run_index`

## Pen-test finding (WA-2026-05-25-01, Low / Info, CWE-401-adjacent)

`app.py` holds every completed audit run in two in-memory containers:

- `_run_history` — list, appended to on every completed run.
- `_run_index` — dict, indexed by both `run_id` and `hash_id`.

Both structures load from `REPORTS_DIR/*.json` on every cold start, and
neither was capped. On a long-lived Cloud Run instance the working set
grows monotonically with audit volume. This is a memory-management
hygiene issue, **not** a confidentiality or integrity boundary —
the on-disk `REPORTS_DIR` JSON files and the Supabase mirror remain the
durable source of truth.

## Resolution (this PR)

- Introduced `_RUN_HISTORY_MAX = 500` (>> the `/api/runs` exposure of
  the most-recent 50).
- `_trim_run_history_locked()` evicts the oldest entries when the cap
  is exceeded and also clears the corresponding `_run_index` aliases
  (both the primary `run_id` and the content-addressable `hash_id`).
- The startup file-load path now keeps only the newest
  `_RUN_HISTORY_MAX` entries, so a cold start cannot reseed the cap.
- The post-run insert path in `_run_tests()` calls
  `_trim_run_history_locked()` while still holding `_lock`.

## Verification

1. Restart the service: `/api/runs` continues to return the most-recent
   50 entries; `/report/<old_run_id>` continues to resolve through the
   `_resolve_report` 3-tier lookup (in-memory → disk → Supabase).
2. Simulate >500 runs in a single process: `len(_run_history) == 500`
   and `len(_run_index)` is bounded by `2 * _RUN_HISTORY_MAX` (two
   aliases per entry).
3. Existing tests in `tests/` (no failure-on-restart regression).

## References

- OWASP ASVS V12 (Files and Resources)
- CWE-401 (Missing Release of Memory after Effective Lifetime)
- AICPA TSC CC4.1, CC7.1
