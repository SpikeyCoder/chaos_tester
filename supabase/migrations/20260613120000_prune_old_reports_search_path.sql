-- WA-2026-06-13-01: harden public.prune_old_reports() against
-- search_path hijacking.
--
-- Finding: Supabase security advisor (lint 0011 / function_search_path_mutable)
-- flagged that public.prune_old_reports() runs as a trigger function without
-- an explicit search_path. A role that can create objects in a schema earlier
-- on the session search_path could shadow public.reports with a malicious
-- view/function and influence the DELETE statement.
--
-- Fix: pin the function's search_path to `public, pg_temp` so its behaviour
-- no longer depends on the caller's session search_path. Function body is
-- unchanged; this is a defense-in-depth hardening.
--
-- CWE-426 (Untrusted Search Path). OWASP A05:2021 Security Misconfiguration.

ALTER FUNCTION public.prune_old_reports() SET search_path = public, pg_temp;
