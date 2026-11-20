# Vercel and Neon Deployment

This project can be deployed as a Vercel Python Function backed by Neon
PostgreSQL. The existing Render configuration remains in the repository for
reference and is not removed by this migration.

## Compatibility design

- `index.py` exports the existing `app.main:app` FastAPI application.
- `.python-version` pins the Vercel Python runtime to Python 3.14, matching
  the verified local environment.
- `vercel.json` configures the Python function and excludes tests,
  documentation, migrations, and local virtual-environment files from the
  function bundle.
- Static files and templates are resolved from the repository location rather
  than the current working directory.
- The local in-process waitlist scheduler continues to run outside Vercel.
- The scheduler is not started when Vercel sets `VERCEL=1`.
- Vercel or another external scheduler can call
  `POST /cron/waitlist-expiry` with a bearer token.

Vercel functions are not permanent processes. The external endpoint is
therefore the production mechanism for hourly expiry processing. Vercel Hobby
Cron is not configured here because its schedule is daily and would silently
change the existing hourly behaviour.

## Create the Neon database

1. Create a Neon project and select the intended region and PostgreSQL
   version.
2. Create a dedicated application role and database. Do not reuse a local
   development password.
3. Keep the Neon connection details private.
4. Confirm the target database is the Neon database before running any SQL.
5. Apply the existing schema using the project-approved schema source.
   The repository does not contain a complete bootstrap schema dump.
6. Inspect the target schema, constraints, and current records.
7. Apply `database/migrations/001_waitlist_idempotency.sql` only to the
   intended Neon database after review. Do not run it against local
   `eventsphere_db`, and do not run migrations automatically during a Vercel
   build or request.

## Vercel environment variables

Create these variables in the Vercel project settings for Preview and
Production as appropriate:

| Variable | Value |
| --- | --- |
| `PGHOST` | Neon pooled or direct hostname |
| `PGPORT` | `5432` |
| `PGDATABASE` | Neon database name |
| `PGUSER` | Dedicated Neon application role |
| `PGPASSWORD` | Neon role password |
| `PGSSLMODE` | `require` |
| `CRON_SECRET` | Long random secret used only by the expiry endpoint |
| `WAITLIST_EXPIRY_INTERVAL_SECONDS` | Used for local scheduling; not used by Vercel production |

Use Vercel's encrypted environment-variable settings. Never commit these
values, place them in a repository file, or paste them into logs or chat.
`PORT` is managed by Vercel and must not be hardcoded.

## Deploy the application

1. Push the reviewed Vercel compatibility changes to the GitHub `main`
   branch.
2. In Vercel, choose **Add New Project** and import
   `pavani2118/EventSphere`.
3. Select the `main` branch and the repository root as the project root.
4. Allow Vercel to detect the Python runtime from `requirements.txt`.
5. Add the environment variables above before the first production deploy.
6. Deploy without adding a database migration or build command that changes
   data.
7. Review the function build output and runtime logs for import, dependency,
   database, or missing-file errors.

## Verify the deployment

Replace the placeholder hostname locally; do not post private environment
values:

```powershell
curl.exe -fsS https://<vercel-project>.vercel.app/health
curl.exe -fsS https://<vercel-project>.vercel.app/
curl.exe -fsS https://<vercel-project>.vercel.app/ui/events
```

The health response should report:

```json
{
  "status": "healthy",
  "application": "EventSphere"
}
```

`/health` does not test the database. Verify `/db-health` privately after the
Neon variables and schema are configured. Do not publish its output if it
contains environment-specific information.

Test the protected expiry endpoint from a secure shell:

```powershell
curl.exe -i -X POST `
  -H "Authorization: Bearer <CRON_SECRET>" `
  https://<vercel-project>.vercel.app/cron/waitlist-expiry
```

Expected successful response fields include `status: "completed"` and an
`expired_count`. The endpoint is safe to invoke repeatedly because it reuses
the existing WaitlistAgent expiry operation, which only updates entries older
than the configured expiry threshold.

## External hourly scheduling

Configure an external scheduler that supports hourly authenticated HTTP
requests, such as an approved uptime/automation service or an organisation's
existing scheduler. Configure:

- method: `POST`;
- URL: `https://<vercel-project>.vercel.app/cron/waitlist-expiry`;
- header: `Authorization: Bearer <CRON_SECRET>`;
- interval: once per hour; and
- timeout/retry policy appropriate for the service.

Do not use an unauthenticated URL. Do not put the secret in a public URL,
repository, frontend JavaScript, or client-visible configuration.

## Limitations

- Vercel function instances are ephemeral; the application must not rely on
  in-process background tasks for production scheduling.
- Neon connectivity and schema preparation remain manual operations.
- The application has no automatic migration runner.
- The application writes operational state to PostgreSQL, not to the Vercel
  filesystem.
- Live Vercel deployment and Neon connectivity are not claimed until verified
  with a real deployment URL.
