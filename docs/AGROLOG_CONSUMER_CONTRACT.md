# AgroLog MT consumer contract

Geopolitical Watch is an independent provider. AgroLog MT consumes only the published interface.

## Endpoint

`GET /v1/feed`

Optional authorization:

`Authorization: Bearer <consumer-token>`

## Feed envelope

- `schema_version`: currently `geowatch-feed-v1`
- `provider`: `Geopolitical Watch`
- `generated_at`
- `report_id`
- `events[]`

## Event fields relevant to consumers

- `cluster_id`
- `event_id`
- `title`
- `priority_score`
- `priority_method_version`
- `corroboration_status`
- `verification_level`
- `reference_at`
- `country`, `region`, `latitude`, `longitude`
- `fatalities_best` when supplied by a coded source
- `actors`
- `impact_areas`
- `impact_evidence_class`
- `provider_count`
- `evidence[]`
- `news[]`
- `what_to_watch[]`

## Consumer responsibilities

AgroLog MT must:

1. preserve the Geopolitical Watch source metadata and feed version;
2. treat the external event as an observed external intelligence record;
3. perform its own downstream relevance and causal analysis for agriculture/logistics;
4. never reinterpret `priority_score` as probability or guaranteed economic impact;
5. preserve news URLs and verification labels;
6. avoid direct writes to the Geopolitical Watch database or storage;
7. tolerate additive fields within the same major feed version;
8. reject or quarantine incompatible major schema versions until the consumer adapter is updated.

## Separation boundary

No shared:

- database;
- raw storage;
- credentials;
- scheduler;
- source API keys;
- internal codebase;
- source governance.

The integration boundary is the versioned feed/API only.
