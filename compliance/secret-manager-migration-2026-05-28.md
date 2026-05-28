# Migrate Cloud Run secrets from `--set-env-vars` to Secret Manager (WA-2026-05-28-01)

## Background

`/.github/workflows/deploy-cloud-run.yml` previously fed 10 production
secrets to Cloud Run via `--set-env-vars` flags whose right-hand side
was the GitHub Actions `${{ secrets.* }}` expansion:

```
--set-env-vars "SUPABASE_SERVICE_KEY=${{ secrets.SUPABASE_SERVICE_KEY }},...
```

Once a `${{ secrets.* }}` reference is interpolated into a shell command
line, GitHub Actions can no longer mask the resulting value in run
logs. The cleartext value is also captured in the Google Cloud
**Audit Logs admin-activity stream** as part of the `gcloud run deploy`
admin-activity entry, where any principal with `logging.viewer` on the
project can read it. This violates SOC 2 CC6.1 (logical access) and
CC6.6 / C1.1 (confidentiality of secrets at rest and in transit).

## Change

Switched the deploy step to `--set-secrets`, which references named
versions in Google Secret Manager (`projects/$PROJECT_ID/secrets/<name>`).
Cloud Run mounts each secret as an env var at runtime; the deploy
command line and admin-activity log entry only contain the secret
*name + version*, never the resolved value.

CORS_ALLOWED_ORIGINS remains a plain `--update-env-vars` flag — it is
a routing/policy string, not a secret.

## Operator runbook

Before merging, create the Secret Manager entries with the existing
values (one-time):

```
for kv in \
  chaos-tester-supabase-service-key:SUPABASE_SERVICE_KEY \
  chaos-tester-perplexity-api-key:PERPLEXITY_API_KEY \
  chaos-tester-google-places-api-key:GOOGLE_PLACES_API_KEY \
  chaos-tester-google-psi-api-key:GOOGLE_PSI_API_KEY \
  chaos-tester-wa-shared-secret:WA_SHARED_SECRET \
  chaos-tester-flask-secret-key:CHAOS_TESTER_SECRET_KEY \
  chaos-tester-trello-api-key:TRELLO_API_KEY \
  chaos-tester-trello-token:TRELLO_TOKEN \
  chaos-tester-trello-list-id:TRELLO_LIST_ID \
  chaos-tester-supabase-anon-key:SUPABASE_ANON_KEY ; do
  secret=${kv%%:*}; gha=${kv##*:}
  printf '%s' "$(gh secret get "$gha" -R SpikeyCoder/chaos_tester)" | \
    gcloud secrets create "$secret" \
      --replication-policy=user-managed \
      --locations=us-central1 \
      --data-file=-
done
```

Grant the Cloud Run runtime service account `roles/secretmanager.secretAccessor`
on each secret (scoped, not project-wide).

After cutover, **delete the GitHub Actions secrets** that are now
duplicated in Secret Manager. Track rotation cadence in
`compliance/access-review-cadence.md`.

## Severity / mapping

| Field | Value |
|-------|-------|
| Finding | WA-2026-05-28-01 |
| Severity | Medium |
| CWE | CWE-532 (Insertion of Sensitive Information into Log File) |
| OWASP | A02:2021 — Cryptographic Failures / Sensitive Data Exposure |
| SOC 2 | CC6.1, CC6.6, CC7.2, C1.1 |

## Verification

1. After the first deploy on this branch:
   `gcloud run services describe chaos-tester --region us-central1 \
   --format='value(spec.template.spec.containers[0].env)'` — secret values
   must show as `secretKeyRef` references, not literal strings.
2. `gcloud logging read 'protoPayload.methodName="google.cloud.run.v2.Services.UpdateService"'
   --limit=1 --format=json` — admin-activity entries must contain
   `secretKeyRef` references, never the cleartext secret.
3. Trigger every endpoint that exercises a migrated secret
   (`/api/ai-query` → Perplexity, `/api/bug-report` → Trello,
   `/api/detect-business` → Google Places) and confirm 200 responses.
