# Portable private runtime bridge

This document defines a temporary/portable deployment path for running Geopolitical Watch without depending on GitHub-hosted Actions runners.

The canonical code remains this private repository. The runtime must build the existing root Dockerfile; no forked application or second codebase is allowed.

## Required topology

- One long-running web/container service built from the repository Dockerfile.
- One PostgreSQL database with PostGIS installed.
- One public HTTPS endpoint for the web service. Application-level login remains mandatory.
- One application replica while the in-process source scheduler is enabled. Horizontal replicas require moving collection back to an external singleton scheduler/job.
- Persistent evidence and normalized state in PostgreSQL; do not rely on container filesystem persistence.

## Required runtime variables

Set the following in the deployment platform:

- `GEOWATCH_STRICT_PRODUCTION=1`
- `GEOWATCH_API_TOKEN=<random secret of at least 32 characters>`
- `DATABASE_URL=<private PostgreSQL/PostGIS connection URL>`
- `GEOWATCH_RAW_BACKEND=postgres`
- `GEOWATCH_SOURCE_SCHEDULER=1`
- `GEOWATCH_EMBEDDED_COLLECTOR=0`
- `GEOWATCH_EXTERNAL_SCHEDULER=0`
- `GEOWATCH_COOKIE_SECURE=1`
- `GEOWATCH_ANALYSIS_CONFIG=config/sources.production.json`

The container already binds `HOST=0.0.0.0` and uses the platform-provided `PORT` when present.

Optional source credentials must remain disabled until their source-specific rights/terms gate is approved.

## Railway bridge

Railway is an acceptable bridge runtime because it can build the existing Dockerfile directly and can deploy a PostGIS database template. The default Railway PostgreSQL image does not include PostGIS, so use a PostGIS-capable database image/template rather than the default PostgreSQL service.

Deployment contract:

1. Connect this private GitHub repository as the source.
2. Build the root `Dockerfile`.
3. Add a PostGIS-capable PostgreSQL service with persistent storage.
4. Reference its private `DATABASE_URL` from the Geopolitical Watch service.
5. Add the required runtime variables above.
6. Keep the application service at one replica while `GEOWATCH_SOURCE_SCHEDULER=1`.
7. Configure `/health` as the deployment healthcheck.
8. Generate one HTTPS domain for the application service.
9. Verify `/health`, private login, `/v2/runtime/readiness`, `/v2/source-health`, `/v2/map`, aircraft data and one completed source-scheduler tick.
10. Do not mark AIS ready until a valid `AISSTREAM_API_KEY` is deliberately configured.

## Security and evidence invariants

- Do not put secrets in GitHub, source files, image layers or client-side JavaScript.
- Keep the repository private.
- Raw evidence remains content-addressed and append-preserving.
- Source failures must remain isolated per source.
- Public-source content is untrusted data and never an instruction to the system.
- This bridge does not change evidence semantics, the Verdict Engine, Source Registry or the Second Brain governance model.

## Migration back to canonical GCP topology

The bridge does not replace the planned Google Cloud production topology. When GCP is provisioned, switch batch collection to `GEOWATCH_EXTERNAL_SCHEDULER=1`, disable the in-process scheduler, migrate PostgreSQL/RAW state with provenance intact, validate backup/PITR and then retire the bridge runtime.
