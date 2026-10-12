# ZERO COST runtime policy

Updated: 2026-10-09

## Budget rule

The canonical Geopolitical-Watch deployment must cost **R$ 0 to implement and R$ 0/month to keep running** while it remains inside free-tier quotas.

The system must never upgrade a plan, enable paid capacity, or apply billable Google Cloud infrastructure automatically. If a free quota is exhausted, the correct failure mode is degradation or suspension, not automatic billing.

## Canonical topology

- Database: Neon Free, PostgreSQL 18 + PostGIS, São Paulo.
- RAW evidence: private Neon Object Storage bucket in a second Free project in us-east-1 because branchable Object Storage is not available in the São Paulo Neon region.
- Collection/analysis: bounded GitHub Actions schedule.
- Web/API/dashboard: Docker runtime on a free web host.
- Code/CI: GitHub.
- Paid GCP: retained only as a manually gated future migration path.

## Hard cost controls

The main Neon database project is on a Free organization and is configured below the published Free allowances:
- logical Postgres storage quota: 900 MiB;
- compute and active-time quota: 300,000 seconds;
- public transfer quota: 4 GiB;
- written-data quota: 4 GiB;
- history window: 6 hours.

The RAW Object Storage project is also Free. Its private bucket is subject to the provider's Free 5 GB/project Object Storage limit.

These controls intentionally prefer service interruption to paid expansion.

## Secret handling

Never commit database URLs, API tokens, access-key identifiers or secret keys. Runtime credentials must be injected by provider secret stores.

## Tradeoffs

The zero-cost profile has no uptime SLA. Web cold starts are acceptable, collection is best-effort rather than continuous, and the provider recovery window is shorter than the previous Cloud SQL design. The application-level immutable object_versions ledger remains the point-in-time knowledge history.

If any free quota is exhausted, the service must pause or degrade until the quota resets or the owner explicitly approves a different architecture.
