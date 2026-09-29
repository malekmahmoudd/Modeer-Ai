# Temporary Fareeq staging on Render

This setup is separate from production `fareeq.io`. It uses the confirmed
Render workspace **My Workspace**, a dedicated PostgreSQL database and
synthetic test accounts. Do not import personal conversations or production
backups. Resource creation/live verification is pending until the Blueprint is
applied in the Render dashboard; this file does not claim deployment success.

## Configuration

- Release branch: `codex/staging-readiness`; Blueprint: root `render.yaml`.
- Frontend: `fareeq-staging-20260929`; API: `fareeq-staging-api-20260929`.
- Database: `fareeq-staging-db-20260929`, PostgreSQL 16, database name
  `fareeq_staging`. The staging launcher refuses any other database name.
- All plans explicitly use `free`; automatic deployment is off. Free service
  sleep/resource limits mean this environment cannot prove production load
  capacity or continuously scheduled reminder delivery.
- Render generates separate `AUTH_SECRET` and `STAGING_ACCESS_KEY` values.
  The latter is the invitation key for the synthetic “Staging tester” account.
  Retrieve it privately from the backend's Render environment settings and use
  **Sign in → invitation key**. Never commit or post it in an issue.
- Public signup is disabled. Production authentication/HTTPS checks remain on.
- Supply a staging-only Groq key as `LLM_API_KEY` directly in Render. The service
  intentionally refuses to start with a missing key; mock mode is not a substitute
  for verifying real microphone transcription.
- The frontend build receives `BACKEND_URL`; it must be rebuilt if this changes.
  Verify the actual assigned Render URLs match the Blueprint values. If Render
  assigns a suffix, update backend `FRONTEND_URL` and frontend `BACKEND_URL`
  before verifying sign-in or deploying the frontend.

## Apply and verify

1. Publish the reviewed release branch and select it in Render's New Blueprint
   flow. Use `render.yaml`. Confirm all resources still show the free plan.
2. Add the staging-only Groq key when prompted. Apply the Blueprint and inspect
   build/runtime results. Backend startup applies migrations only to the
   dedicated staging database, seeds the synthetic tester, then starts the API.
3. Confirm backend health, frontend login, secure session cookies and served
   microphone policy. Backend and frontend must agree on the frontend origin.
4. Verify chat, uploads, voice, account isolation and logout with synthetic data.
5. On iPhone, open Account in Safari, add the app to the Home Screen, enable
   reminders, test microphone cancellation, and confirm reminders stop after
   sign-out and remote revocation. Android testing remains required separately.
6. Check migrations and restore against a disposable copy; inspect outbound
   Linux traffic with telemetry disabled. Do not enable telemetry just to create
   a positive control. No production readiness claim follows from local tests.

## Rollback and cleanup

Keep production untouched. If staging fails, inspect logs and deploy the last
verified staging commit; do not downgrade a populated database automatically.
Staging is disposable: after device verification, remove only these named
staging resources through Render, preserving any test evidence needed first.

References: [Render Blueprints](https://render.com/docs/blueprint-spec) and
[free instance limits](https://render.com/docs/free), checked 29 September 2026.

## Local verification for this release candidate

- Backend: 578 passed, 1 skipped; backend lint passed.
- Frontend: 29 unit tests passed, TypeScript and production build passed;
  lint had no errors and 22 warnings before the deployment-only additions.
- Self-contained CV browser script passed 4/4 on a fresh disposable database.
- Render Blueprint validated against the official JSON Schema (2020-12).
- WebKit completed Account, drawer and voice checks with service workers
  enabled, but its page-error assertion still reported access-control errors
  during navigation. This is unresolved, not a clean cross-browser pass.
- Earlier 74-check Chrome verification is recorded in ROLLOUT-0013.md; it does
  not verify the deployed Render service. Real Safari/iPhone, Android, outbound
  telemetry and the hosted migration/restore checks remain open.
