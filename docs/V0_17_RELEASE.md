# Geopolitical Watch v0.17 operational hardening

Date: 2026-09-29

## Scope

This release hardens the existing v0.16 system instead of rebuilding it. It keeps PostgreSQL/PostGIS, immutable RAW evidence, source-specific collectors, the deterministic event/episode pipeline, the Verdict Engine, MapLibre, alerts and the existing full-project gate.

## Newly implemented

- Pydantic runtime settings with strict startup checks.
- Canonical Pydantic boundary contracts for Source, Observation, Evidence, Claim, Location, Actor, Event and Conflict.
- JSON Schema 2020-12 export.
- Project Registry with canonical repository, deployment target, services and release gates.
- Versioned migration runner and migration v5.
- Explicit Evidence Ledger linking preserved RAW/evidence/events.
- Claim revision history.
- Source operational states: HEALTHY, DEGRADED, BROKEN, BLOCKED, RETIRED.
- Per-source circuit breaker and PostgreSQL dead-letter queue.
- Scheduler tracing and optional OTLP/Phoenix export.
- Trafilatura, Crawl4AI, Scrapling, Playwright and Browsertrix governed adapters.
- Docling local-document parser.
- Language identification envelope that always preserves original text.
- Translation attachment contract that never overwrites source text.
- Controlled geolocation that never guesses unknown coordinates.
- URL/raw/text/near-text deduplication utilities.
- Explicit epistemic states and evidence-quality confidence proxy.
- Event taxonomy.
- STIX 2.1 import/export boundary.
- Entity dossiers covering actors, organizations, forces, countries, installations and chokepoints represented in the governed entity registry.
- Event API filters for region, actor, type, source, epistemic state, minimum evidence-quality proxy and time.
- Dashboard event timeline/filter controls.
- Optional deck.gl 9.4 density overlay above MapLibre for high-volume event sets.
- Promptfoo hostile-source and prompt-injection regression suite.
- Full-project gate extensions for JSON Schema, Project Registry, migration v5 and operational lineage tables.

## Existing capabilities reused

The release deliberately reuses the existing immutable RAW stores, SHA-256 content addressing, Source Registry, freshness/checkpoints, HTTP retry/backoff/jitter, entity resolver, event clustering, claim extraction/reconciliation, evidence strength, deterministic Verdict Engine, relationship graph, episode dossiers, alert outbox, MapLibre map, AIS/ADS-B separation rules and browser smoke test.

## Operational claims

This branch is not production-approved merely because the code exists. Production approval still requires the full gate to pass on the exact commit, including PostgreSQL/PostGIS, persistent RAW round-trip, security scans, Terraform validation, production container build and Chromium/MapLibre browser smoke.

GitHub-hosted workflow failures that occur before a runner starts are infrastructure evidence, not application-test failures. A green execution from the canonical Cloud Build path or another approved runner is still required before merge to protected main/deployment.

## External components

External adapters are optional and isolated. Browsertrix is pinned to 1.14.1. Crawl4AI and Scrapling are research extras, not unconditional production dependencies. Browser-agent execution remains an explicit isolated handoff instead of an implicit unrestricted browser action. Phoenix export is enabled only when an OTLP endpoint is configured. STIX validation requires the interoperability extra.

## Evidence semantics

An evidence-quality score is not a calibrated probability that a geopolitical claim is true. OBSERVADO, RELATADO, ESTIMADO, INFERIDO and NAO_CONFIRMADO remain explicit classifications, and the deterministic Verdict Engine remains the authority for stronger claim verdicts.
